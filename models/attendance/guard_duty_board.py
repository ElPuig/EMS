# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_list

from ..shared.schedule_report_mixin import HOUR_EPSILON
from .absence_coverage import (
    BREAK_CHANGES, CHANGE_SIDES, COMMUNICATED_NOTICE_STATES, NORMAL_CHANGE, WC_GUARD_CODE, overlaps,
)
from .arrangement_planner import ArrangementPlanner, schedule_shift

WEEKDAYS = ('0', '1', '2', '3', '4')
# Mirrors ems.group's own SHIFT_HOURS (models/contacts/group_schedule.py) — the guard duty board
# needs the same morning/afternoon split, but rendered as weekday x shift tables with one column
# per group rather than one column per weekday, so it can't reuse that method as-is.
SHIFT_HOURS = {
    'morning': (8, 15),
    'afternoon': (15, 22),
}

# Which absence requests are worth putting on the board, and how each one is reported to the
# screen. 'approved' is a fact to plan around; 'pending' is a warning that one may be coming -
# hr_holidays' two pre-approval states are deliberately collapsed into a single one here,
# because the difference between "waiting for the first approver" and "waiting for the second"
# changes nothing for whoever is assigning guards. Refused and cancelled requests are absent
# from this mapping entirely, which is what keeps them off the board.
ABSENCE_STATES = {
    'confirm': 'pending',
    'validate1': 'pending',
    'validate': 'approved',
}

# A whole-day absence, as an hour interval, so it can be compared against a schedule period the
# same way a partial one is - no special case anywhere downstream.
WHOLE_DAY = (0.0, 24.0)

# How many distinct colours the absences table pairs a guard with the classes they cover in
# (issue #571). Kept in step by hand with the o_guard_board_cover_N classes in
# static/src/css/backend/guard_duty_board.css and the gdb-cover-N ones in the PDF.
COVER_COLOR_COUNT = 8


def _period_contains(container, period):
    """True when 'period' (hour_from, hour_to) is fully covered by 'container' - same
    containment check '_merge_absorbed_periods' below needs inline, extracted so the level
    filter's guard/break folding can reuse it against a period that isn't
    necessarily a member of the same 'periods' list (see 'get_guard_duty_board_lines' docstring).
    Uses HOUR_EPSILON for the same float-noise reason as '_merge_absorbed_periods'."""
    return container[0] <= period[0] + HOUR_EPSILON and container[1] >= period[1] - HOUR_EPSILON


def _same_period(period, other):
    """Both periods cover the very same time, give or take HOUR_EPSILON."""
    return _period_contains(period, other) and _period_contains(other, period)


def _board_guard_covers(lines):
    """`{guard employee id: [(hour_from, hour_to, partial)]}` - what each guard covers on the board's
    `lines`, `partial` when it is only part of its class (issue #637)."""
    guard_covers = defaultdict(list)
    for line in lines:
        for row in line['absences']:
            for cover in row['covers']:
                guard_covers[cover.guard_employee_id.id].append((cover.hour_from, cover.hour_to, not _period_contains(
                    (cover.hour_from, cover.hour_to), (line['hour_from'], line['hour_to']))))
    return guard_covers


def _entries_by_group(entries):
    """`{group id: {(hour_from, hour_to): attendance recordset}}`, in one pass over `entries` and
    keeping their order: looking a cell up here instead of filtering every entry of the shift per
    cell (rows x groups x entries, ~14s on a real centre's timetable) is what keeps the board fast."""
    ids = defaultdict(lambda: defaultdict(list))
    for attendance in entries:
        for group_id in attendance.group_ids.ids:
            ids[group_id][(attendance.hour_from, attendance.hour_to)].append(attendance.id)
    # with_prefetch: a lookup's records still fetch their fields together with every other entry's,
    # in one query per field, instead of one small fetch per cell.
    return {group_id: {period: entries.browse(period_ids).with_prefetch(entries._prefetch_ids)
                       for period, period_ids in periods.items()}
            for group_id, periods in ids.items()}


def _uncovered_periods(period, pieces):
    """The parts of `period` none of `pieces` covers, in order (issue #637: a class covered by
    several guards, each for part of it)."""
    missing, start = [], period[0]
    for piece_start, piece_stop in sorted(pieces):
        if piece_start > start + HOUR_EPSILON:
            missing.append((start, min(piece_start, period[1])))
        start = max(start, piece_stop)
    if start < period[1] - HOUR_EPSILON:
        missing.append((start, period[1]))
    return missing


def _merge_absorbed_periods(periods, fixed=()):
    """Groups 'periods' (a list of distinct (hour_from, hour_to) tuples) into
    {period: [period, *periods absorbed into it]}, one entry per period that keeps its own row -
    an absorbed period is never a key of the returned dict.

    A period is absorbed into another one from the same list when its own hour range is fully
    contained in the other's (found 2026-09 as issue #410: a teacher's own personal schedule can
    end a guard-duty slot early - e.g. a shorter working day that block - while a colleague's
    guard for the same start time runs the full period; the same thing happens for any other
    non-teaching activity, like a 35-minute coordination duty sitting next to a 60-minute class.
    Before this, get_guard_duty_board_lines() rendered the short period as its own row, almost or
    entirely empty). If several periods could contain a given one, the smallest (shortest) is
    preferred, to avoid folding into an unnecessarily wide row should several levels of
    containment ever coexist.

    Uses HOUR_EPSILON (see its own NOTE) since two periods that are conceptually "the same" can
    still differ by a hair's-width float remainder depending on how each was computed.

    A period in 'fixed' is never absorbed (issue #637): those are the periods of a schedule
    framework (a lesson or a break of some level), a time block in its own right. Without this, a
    level's break (10:00-10:25) folded into another level's lesson running across it (10:00-11:00),
    and its break-time guards showed up as available for that lesson. Only a teacher's own,
    shortened period (the #410 case above) still folds into the block it belongs to."""
    containers = {}
    for period in periods:
        if any(_same_period(other, period) for other in fixed):
            continue
        candidates = [
            other for other in periods
            if other != period and _period_contains(other, period)
        ]
        if candidates:
            containers[period] = min(candidates, key=lambda other: other[1] - other[0])

    def root(period):
        # 'seen' guards against a cycle between two periods that both fall within HOUR_EPSILON of
        # each other in both bounds (so each looks like a - vanishingly narrow - "container" of
        # the other) - not a real containment relation, just float noise; without this a cycle
        # would loop root() forever instead of just resolving to whichever period was reached
        # first.
        seen = set()
        while period in containers and period not in seen:
            seen.add(period)
            period = containers[period]
        return period

    members = {}
    for period in periods:
        members.setdefault(root(period), []).append(period)
    return members


class BoardTimeGrid:
    """Both views of the board on a real time axis (issue #637). Each area keeps its own time
    framework (ESO has its break at 10:00, vocational training at 11:00), so the rows are the
    shortest stretches between every start and end time of the shift, and each lesson, absence,
    break or guard spans the stretches it lasts - never cut or stretched to fit another area's
    periods. Items of one column that overlap in time go side by side, one lane each.

    Built once on the server from the board's 'lines', and only rendered by the screen and the PDF:
    a slot refers to its line by index ('line'), plus whatever the view shows of it. A lane is a
    list with one entry per stretch: a slot dict where an item starts (with its 'rowspan'), COVERED
    under it, or None."""

    COVERED = 'covered'

    def __init__(self, lines, groups, areas, group_breaks, format_time):
        self.lines = lines
        self.groups = groups
        self.areas = areas
        self.group_breaks = group_breaks
        self.format_time = format_time
        bounds = []
        for line in lines:
            for hour in (line['hour_from'], line['hour_to']):
                if not any(abs(bound - hour) < HOUR_EPSILON for bound in bounds):
                    bounds.append(hour)
        self.bounds = sorted(bounds)
        self.segments = list(zip(self.bounds, self.bounds[1:]))

    def _index(self, hour):
        return next(i for i, bound in enumerate(self.bounds) if abs(bound - hour) < HOUR_EPSILON)

    def _label(self, hour_from, hour_to):
        return f"{self.format_time(hour_from)}-{self.format_time(hour_to)}"

    def _place(self, lane, start, end, slot):
        lane[start] = dict(slot, rowspan=end - start)
        for i in range(start + 1, end):
            lane[i] = self.COVERED

    def _lay_lanes(self, items, max_lanes=None):
        """'items': (line index, slot) pairs, laid out in as few lanes as needed. 'max_lanes' = 1
        keeps the first item and drops any overlapping one (a group has one lesson at a time)."""
        lanes = []
        for index, slot in items:
            line = self.lines[index]
            start, end = self._index(line['hour_from']), self._index(line['hour_to'])
            lane = next((lane for lane in lanes if not any(lane[start:end])), None)
            if lane is None:
                if max_lanes and len(lanes) >= max_lanes:
                    continue
                lane = [None] * len(self.segments)
                lanes.append(lane)
            self._place(lane, start, end, dict(slot, line=index, label=self._label(line['hour_from'], line['hour_to'])))
        return lanes or [[None] * len(self.segments)]

    def _lay_breaks(self, lanes, breaks):
        """The column's own breaks, where nothing else is scheduled in its first lane: one block per
        break, spanning its stretches and carrying its time, so the gap reads as "Patio"."""
        lane = lanes[0]
        for hour_from, hour_to in sorted(set(breaks)):
            inside = [i for i, segment in enumerate(self.segments) if _period_contains((hour_from, hour_to), segment)]
            if inside and not any(lane[i] for i in inside):
                self._place(lane, inside[0], inside[-1] + 1, {
                    'is_break': True, 'label': self._label(hour_from, hour_to)})
        return lanes

    def _guard_lanes(self, with_posts=False):
        items = []
        for index, line in enumerate(self.lines):
            if line['guards'] or line.get('stayed_guards'):
                slot = {'guards': True, 'is_break': line['is_break']}
                if with_posts:
                    # A fixed guard post (WC, break) whose teacher is away belongs to no group: it is
                    # covered from the guard column, under the guards of its own block.
                    slot['posts'] = [i for i, absence in enumerate(line['absences']) if not absence['group']]
                items.append((index, slot))
        return self._lay_lanes(items)

    def _area_headers(self):
        headers = []
        for group in self.groups:
            area = self.areas[group.id]
            if headers and headers[-1]['id'] == area.id:
                headers[-1]['groups'].append(group)
            else:
                headers.append({'id': area.id, 'name': area.name or '', 'groups': [group]})
        return headers

    def _rows(self, columns, guard_lanes):
        def cells(lanes, i):
            return [slot or {'empty': True} for slot in (lane[i] for lane in lanes) if slot != self.COVERED]

        return [{
            'label': self._label(hour_from, hour_to),
            # Where the screen draws its current-time line (issue #647).
            'hour_from': hour_from,
            'hour_to': hour_to,
            # Taller for a longer stretch, so the grid reads like a clock.
            'minutes': round((hour_to - hour_from) * 60),
            'cells': [slot for lanes in columns for slot in cells(lanes, i)],
            'guards': cells(guard_lanes, i),
        } for i, (hour_from, hour_to) in enumerate(self.segments)]

    def schedule(self):
        """One column per group, each lesson where it is."""
        columns = []
        for column, group in enumerate(self.groups):
            lanes = self._lay_lanes([
                (index, {'column': column}) for index, line in enumerate(self.lines) if line['cells'][column]['entries']
            ], max_lanes=1)
            columns.append(self._lay_breaks(lanes, self.group_breaks.get(group.id, ())))
        guard_lanes = self._guard_lanes()
        return {
            'areas': [dict(header, colspan=len(header['groups']), groups=[group.id for group in header['groups']])
                      for header in self._area_headers()],
            'lane_count': len(guard_lanes),
            'rows': self._rows(columns, guard_lanes),
        }

    def absences(self):
        """One column per area, with that area's absences (each line's own, by index)."""
        columns = []
        headers = self._area_headers()
        for header in headers:
            group_ids = {group.id for group in header['groups']}
            items = []
            for index, line in enumerate(self.lines):
                mine = [i for i, absence in enumerate(line['absences']) if absence['group'].id in group_ids]
                if mine:
                    items.append((index, {'absences': mine}))
            breaks = [period for group in header['groups'] for period in self.group_breaks.get(group.id, ())]
            columns.append(self._lay_breaks(self._lay_lanes(items), breaks))
        guard_lanes = self._guard_lanes(with_posts=True)
        return {
            'areas': [{'id': header['id'], 'name': header['name'], 'colspan': len(lanes)}
                      for header, lanes in zip(headers, columns)],
            'lane_count': len(guard_lanes),
            'rows': self._rows(columns, guard_lanes),
        }


class BoardBreakSide:
    """A break as a "side" of the group's day (like the start and the end): its key in the
    timetable-change states, and which notices are about it."""

    PREFIX = 'break@'

    @classmethod
    def key(cls, period):
        return f"{cls.PREFIX}{period[0]:.4f}-{period[1]:.4f}"

    @classmethod
    def period(cls, side):
        start, stop = side[len(cls.PREFIX):].split('-')
        return float(start), float(stop)

    @classmethod
    def is_break(cls, side):
        return side.startswith(cls.PREFIX)


class EmsCourseGuardDutyBoard(models.Model):
    # NOTE: extends 'ems.course' in place (not a new model) — a 2-item '_inherit' list without an
    # explicit '_name' would make Odoo's metaclass define a brand-new model instead (see MetaModel
    # in odoo/models.py). Same pattern as ems_working_schedule/resource.calendar and
    # ems_group_schedule/ems.group.
    #
    # This lives on 'ems.course' (a real, always-existing, already-readable-by-every-teacher
    # model — see security/ir.model.access.csv's ems.access_ems_course_teacher) rather than a
    # dedicated TransientModel wizard, deliberately: an earlier version used a TransientModel
    # opened via a dynamic ir.actions.server, which meant the URL bar showed a raw
    # "ems.guard_duty_board/<id>" instead of a stable "action-<xmlid>" like every other EMS
    # screen — Odoo can only put a real xmlid in the URL for a *statically declared* action, and
    # a server action that returns a dynamically-built act_window dict has no xmlid of its own to
    # show. Binding to 'ems.course' instead means the board's own screen is a plain
    # ir.actions.client (a real, static, URL-addressable action — see
    # views/attendance/guard_duty_board/menu.xml) with no per-visit record to create/open at all.
    _name = 'ems.course'
    _inherit = ['ems.course', 'ems.schedule_report_mixin']

    def _get_guard_duty_board_attendance_ids(self, domain=()):
        """Every real (non-framework) teacher's Mon-Fri attendance row, across every teacher —
        same aggregation idea as ems.group._compute_schedule_attendance_ids
        (models/contacts/group_schedule.py), generalized from "this group" to "the whole centre".
        Deliberately not filtered by 'calendar_id.course_id' — mirrors that same precedent, which
        aggregates the same way without a course filter either: a course-transitioned-out
        calendar/attendance row is archived (active=False, see
        ems_working_schedule_assignation.active's own NOTE), so this plain search() already only
        ever returns the current course's real, active schedules, and stays correct even for a
        legacy calendar whose 'course_id' was never backfilled (added 2026-08-06, not every
        pre-existing row necessarily has it set).

        The explicit 'calendar_id.active' check below is defense-in-depth, not redundant with the
        above: 'ems_working_schedule.action_archive()' now cascades to every remaining attendance
        row when a calendar itself is retired, but this search must not silently start trusting
        that invariant everywhere it's ever established - a calendar could in principle end up
        archived by some other path without its own attendance rows following (found 2026-09-01:
        before that cascade existed, a rolled-over teacher's ARCHIVED calendar kept showing
        active non-teaching rows here indefinitely, since a bare 'active=True' row search never
        looks at its own parent calendar's active state at all).

        'calendar_id.employee_id != False' excludes any calendar that isn't a specific teacher's
        own personal working schedule - concretely, Odoo's own generic default calendar (e.g.
        "Standard 40 hours/week", auto-created with its own Mon-Fri 8-12/13-17 attendance rows
        the first time anything needs 'res.company.resource_calendar_id' and nothing has been
        customized yet). That calendar is never itself is_framework=True, so the check above
        alone doesn't exclude it, and on a clean install with no real schedules configured yet
        it silently shows up here and corrupts period computation (found 2026-09-08 via CI: the
        generic 8-12 block contains/absorbs a real, narrower test period into itself).

        'domain' narrows the search further (a weekday, a shift, some groups): filtering in SQL
        rather than over the whole centre's rows in Python (issue #637, performance)."""
        return self.env['resource.calendar.attendance'].search([
            ('calendar_id.is_framework', '=', False),
            ('calendar_id.active', '=', True),
            ('calendar_id.employee_id', '!=', False),
            ('dayofweek', 'in', WEEKDAYS),
            *domain,
        ])

    def _get_guard_duty_absence_intervals(self, day, employees, unchecked=False):
        """`{employee.id: [(hour_from, hour_to, state)]}` - the absences covering `day`.

        `unchecked` (issue #692) also adds, for today only, the teachers who have not checked in:
        see _get_unchecked_intervals. Only the guard side of the board asks for it (its rows, who
        can be sent, whether a guard is still needed): a teacher who has not checked in may still
        be in the building, so nothing proposes telling the families or rearranging lessons.

        Resolved on demand rather than stored anywhere: an absence is an 'hr.leave' keyed to a
        real date, the board is keyed to a weekday, and nothing joins the two until a date is
        actually asked for. Returns `{}` for no date at all, which is what lets the PDF (and any
        other weekday-only caller) keep working unchanged.

        sudo() because a guard-duty absence is not private to its own approval chain: whoever
        reads this board legitimately needs to know that a colleague is not coming, which is
        exactly the same justification 'get_guard_sessions()' carries for reading schedules that
        are not the reader's own. Only the fact and the interval are ever exposed - never the
        absence type, its reason, or its attachments.
        """
        if not day or not employees:
            return {}
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('state', 'in', list(ABSENCE_STATES)),
            ('request_date_from', '<=', day),
            ('request_date_to', '>=', day),
        ])
        intervals = defaultdict(list)
        for leave in leaves:
            # 'request_unit_hours' rather than 'ems_full_day': it is the field that actually
            # decides whether request_hour_from/to carry anything (see hr.leave's own
            # _compute_request_unit_hours and EMS's override of it), and a multi-day request is
            # a whole day on each of its days regardless of how it was filled in.
            partial = leave.request_unit_hours and leave.request_date_from == leave.request_date_to
            hours = (leave.request_hour_from, leave.request_hour_to) if partial else WHOLE_DAY
            intervals[leave.employee_id.id].append((*hours, ABSENCE_STATES[leave.state]))
        # An absence the Head of Studies already knows about but the teacher has not filed yet
        # (issue #509) reads as a pending one. Once filed, the teacher's own request above is all
        # that counts, so a linked entry is left out whatever became of that request.
        pending = self.env['ems.absence_pending'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'pending'),
        ])
        for absence in pending:
            hours = absence._get_local_hours(day)
            if hours:
                intervals[absence.employee_id.id].append((*hours, 'pending'))
        if unchecked:
            for employee_id, interval in self._get_unchecked_intervals(day, employees).items():
                intervals[employee_id].append(interval)
        return intervals

    def _get_unchecked_intervals(self, day, employees):
        """`{employee.id: (now, arrival, 'unchecked')}` for `day` when it is today (issue #692):
        `now` the company's current hour, `arrival` the hour of the employee's first check-in that
        day (24.0 without one). A class counts as left without its teacher once it has started
        (hour_from <= now) unless they checked in before it ended (see _guard_duty_absence_state):
        checking in late clears the class in progress and the next ones, while those already over
        stay, so a guard sent to them is still the right one. The first check-in is read the same way
        the detected absences read it (hr.attendance._ems_first_check_in_hours, issue #696)."""
        utils = self.env['ems.datetime_utils']
        if not day or day != utils.get_local_today() or not employees:
            return {}
        arrivals = self.env['hr.attendance']._ems_first_check_in_hours(day, employees)
        now = self._board_day_hour(day)
        return {employee.id: (now, arrivals.get(employee.id, 24.0), 'unchecked') for employee in employees}

    @staticmethod
    def _guard_duty_absence_state(intervals, employees, hour_from, hour_to):
        """`{employee.id: 'approved'|'pending'|'unchecked'}` for those of `employees` absent in the
        period.

        An approved absence outranks a pending one when the same teacher has both overlapping
        the same period: the period is going to need covering either way, so reporting it as
        merely "requested" would understate it. Either outranks a missing check-in ('unchecked',
        issue #692), whose interval reads differently: `(now, arrival)`, the period counting once
        it has started and when the teacher had not arrived before it ended (see
        _get_unchecked_intervals).
        """
        states = {}
        for employee in employees:
            overlapping = {state for start, stop, state in intervals.get(employee.id, ())
                           if (hour_from <= start + HOUR_EPSILON and hour_to <= stop + HOUR_EPSILON
                               if state == 'unchecked' else start < hour_to and stop > hour_from)}
            for state in ('approved', 'pending', 'unchecked'):
                if state in overlapping:
                    states[employee.id] = state
                    break
        return states

    @staticmethod
    def _guard_duty_is_co_taught(cell_entries, teacher, absences):
        """Whether `teacher`'s class in this cell is still being taught by a co-teacher who is
        not away: the row stays on the absences table, so everyone knows who is missing, but
        nobody needs to cover it. Same room required, not just the same group and period: a
        group split between two rooms (each teacher with half of it) leaves the absent teacher's
        half uncovered even though the other half has its teacher."""
        rooms = cell_entries.filtered(lambda attendance: attendance.employee_id == teacher).space_id
        return any(
            attendance.employee_id != teacher and attendance.employee_id.id not in absences
            and attendance.space_id == rooms[:1]
            for attendance in cell_entries)

    # Absence management from the absences table (issues #539, #571, #581). See "Managing
    # absences from the board" in docs/en/developers/attendance/guard_duty_board.md.

    def _is_absence_manager(self, employee, group=None):
        """Whether the current user organises `employee`'s absence in a class of `group` (none
        for a guard duty of theirs, or their absences as a whole): whoever answers for the
        students who lose the class, or for the teacher who is away. Never every holder of a role
        centre-wide, and never the absent teacher themselves.

        - The students (issue #622): the chiefs of the departments that manage the group
          (ems.group.managing_department_ids, from its study) and whoever is above them
          (ems.group._absence_manager_users), so a teacher shared between departments is covered
          by each group's own.
        - The teacher: whoever is above them in the chain of command (their Seminar Chief or
          Department Chief, then up through the Head of Studies to the Director), the same chain
          'tutor_scope_user_ids' resolves for tutor-scoped rights. Or the Chiefs of the
          department the employee belongs to and the manager of the area it hangs from: the
          management team (e.g. the Secretary) reports to the Director, out of their department's
          chain (issue #604, the criterion of rule_absence_pending_hierarchy, issue #569). Or
          those of the departments named on the employee as also managing them
          (hr.employee.managing_department_ids, issue #622).

        The administrator always can."""
        user = self.env.user
        if self.env.su or user.has_group('base.group_system') or user.has_group('ems.group_academic_admin'):
            # The administrator sits above the whole hierarchy, Direction included, although they
            # are not a teacher and so appear nowhere in it.
            return True
        employee = employee.sudo()
        if user == employee.user_id:
            return False
        if group and user in group._absence_manager_users():
            return True
        if user in employee.tutor_scope_user_ids or user in employee.managing_department_ids._chief_users():
            return True
        chiefs = user.sudo().employee_ids
        departments = chiefs.headed_department_ids | chiefs.seminar_department_ids
        return bool(departments) and employee.department_id in departments.search([('id', 'child_of', departments.ids)])

    def _check_absence_manager(self, employee, group=None):
        if self._is_absence_manager(employee, group):
            return
        if group and group.sudo().managing_department_ids:
            raise AccessError(_(
                "Only the chiefs of the department that manages %(group)s (%(department)s), the department chief of "
                "%(teacher)s, or someone above them, can manage this absence.",
                group=group.name, department=", ".join(group.sudo().managing_department_ids.mapped('name')),
                teacher=employee.name))
        raise AccessError(_(
            "Only the department chief of %s, or someone above them, can manage their absences.", employee.name))

    @staticmethod
    def _freeing_move(covers, teacher, group, hour_from, hour_to):
        """The move made without telling the families (issue #645) that left `teacher`'s lesson of
        `group` in the period free, if any."""
        return covers.filtered(
            lambda cover: cover.state == 'assigned' and cover.cover_type == 'arrangement'
                and cover.arrangement_type == 'move' and not cover.notice_id and cover.guard_employee_id == teacher
                and cover.group_id == group and overlaps(cover.vacated_hour_from, cover.vacated_hour_to, hour_from, hour_to))[:1]

    def _original_absent(self, covers, teacher, group, hour_from, hour_to):
        """Whose absence a class left without anybody comes from: `teacher` themselves, or, when
        their lesson was moved to fill another gap (issue #645), the absent teacher whose class
        that move covered - along the whole chain. That is who decides who may organise it."""
        seen = set()
        move = self._freeing_move(covers, teacher, group, hour_from, hour_to) if group else None
        while move and teacher.id not in seen:
            seen.add(teacher.id)
            teacher, hour_from, hour_to = move.absent_employee_id, move.hour_from, move.hour_to
            move = self._freeing_move(covers, teacher, group, hour_from, hour_to)
        return teacher

    def _cover_original_absent(self, cover, covers=None):
        covers = covers if covers is not None else self._get_day_covers(cover.date)
        return self._original_absent(covers, cover.absent_employee_id, cover.group_id, cover.hour_from, cover.hour_to)

    def _check_cover_manager(self, day, absent, group, hour_from, hour_to):
        """_check_absence_manager for the class of `group` in the period, whoever's absence it
        really comes from (see _original_absent)."""
        self._check_absence_manager(
            self._original_absent(self._get_day_covers(day), absent, group, hour_from, hour_to), group)

    def _check_board_day_not_past(self, day):
        if day < self.env['ems.datetime_utils'].get_local_today():
            raise UserError(_("This day is already over."))

    # "The teacher is in the classroom" (issue #692): a class left on the table only because its
    # teacher has not checked in, which whoever is on guard or manages the absence can resolve by
    # checking them in.

    def _is_unchecked_in_progress(self, day, employee, hour_from, hour_to):
        """Whether `employee`'s class (or guard duty) in the period is going on right now and they
        have still not checked in. One already over stays on the table whatever is done now:
        checking them in at this hour would not take it off."""
        if day != self.env['ems.datetime_utils'].get_local_today() \
                or not self._in_progress(self._board_day_hour(day), hour_from, hour_to):
            return False
        if not self._get_guard_duty_board_attendance_ids([
                ('dayofweek', '=', str(day.weekday())), ('calendar_id.employee_id', '=', employee.id),
                ('hour_from', '<', hour_to), ('hour_to', '>', hour_from)]):
            return False
        intervals = self._get_guard_duty_absence_intervals(day, employee, unchecked=True)
        return self._guard_duty_absence_state(intervals, employee, hour_from, hour_to).get(employee.id) == 'unchecked'

    @staticmethod
    def _in_progress(now, hour_from, hour_to):
        """Whether the period is going on at `now` (a float hour, None for no clock)."""
        return now is not None and hour_from <= now + HOUR_EPSILON < hour_to

    def _is_on_guard(self, day, employee, hour_from, hour_to):
        """Whether `employee` has a guard duty (regular or not) overlapping the period on `day`."""
        return bool(employee) and bool(self._get_guard_duty_board_attendance_ids([
            ('dayofweek', '=', str(day.weekday())), ('calendar_id.employee_id', '=', employee.id),
            ('non_teaching_is_guard', '=', True), ('hour_from', '<', hour_to), ('hour_to', '>', hour_from)]))

    def _can_mark_present(self, day, employee, group, hour_from, hour_to):
        """Whether the current user may check `employee` in from the board: they are on guard then,
        or they manage the absence (_is_absence_manager: the chain of command, Direction and the
        administrator)."""
        return self._is_absence_manager(employee, group) \
            or self._is_on_guard(day, self.env.user.employee_id, hour_from, hour_to)

    def _get_group_day_blocks(self, day, groups):
        """`{group.id: [block, ...]}`: each group's own lessons on `day`, in chronological order,
        one block per period (a period absorbed by a longer one folds into it, same as the board's
        own rows). A block carries its attendance 'entries', its 'teachers', which of them are away
        ('absences', where a teacher whose lesson an arrangement moved elsewhere counts as away, and
        one who has not checked in today as 'unchecked', issue #692),
        the 'covers' already resolving it (a guard, or an internal arrangement in effect), and
        'empty' - true when every teacher of the block is away and nobody covers it, i.e. the group's students
        have nobody with them. The whole day, not one shift: a group starts its day at its first
        lesson and ends it at its last, whichever shift they fall in."""
        weekday = str(day.weekday())
        entries = self._get_guard_duty_board_attendance_ids([('dayofweek', '=', weekday), ('group_ids', 'in', groups.ids)])
        intervals = self._get_guard_duty_absence_intervals(day, entries.employee_id, unchecked=True)
        # An arrangement still waiting for its notice changes nothing yet (issue #605).
        covers = self.env['ems.absence_cover'].sudo().search([
            ('date', '=', day), ('state', '=', 'assigned'), ('group_id', 'in', groups.ids)]).filtered('is_effective')
        moves = covers.filtered(lambda cover: cover.cover_type == 'arrangement' and cover.vacated_hour_to)
        blocks_by_group = {}
        by_group = _entries_by_group(entries)
        empty = entries.browse()
        for group in groups:
            group_periods = by_group.get(group.id, {})
            members = _merge_absorbed_periods(sorted(group_periods))
            blocks = []
            for hour_from, hour_to in sorted(members):
                block_entries = empty.union(*(group_periods[period] for period in members[(hour_from, hour_to)]))
                teachers = block_entries.employee_id
                # The lesson an arrangement leaves free has nobody either: its teachers are with the
                # group at another time instead, or on guard if they could not follow it (issue #678).
                moved = {teacher.id: 'moved' for cover in moves
                         if cover.group_id == group and overlaps(cover.vacated_hour_from, cover.vacated_hour_to, hour_from, hour_to)
                         for teacher in (cover.guard_employee_id | cover.stayed_employee_ids) & teachers}
                absences = {**moved, **self._guard_duty_absence_state(intervals, teachers, hour_from, hour_to)}
                # In a swap the absent teacher takes over the other teacher's lesson: that block
                # has somebody too.
                block_covers = covers.filtered(
                    lambda cover, group=group, hour_from=hour_from, hour_to=hour_to:
                        cover.group_id == group and (
                            overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to)
                            or (cover.arrangement_type == 'swap'
                                and overlaps(cover.vacated_hour_from, cover.vacated_hour_to, hour_from, hour_to))))
                blocks.append({
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'entries': block_entries,
                    'teachers': teachers,
                    'absences': absences,
                    'covers': block_covers,
                    # A teacher who has not checked in (issue #692) may still be with the group:
                    # their class needs a guard, but never makes the group's day shorter.
                    'empty': bool(teachers) and all(absences.get(teacher.id, 'unchecked') != 'unchecked'
                                                    for teacher in teachers) and not block_covers,
                })
            blocks_by_group[group.id] = blocks
        return blocks_by_group

    def _enabled_absence_changes(self):
        """The change types the centre lets the board propose (issue #679, see the company's
        ems_absence_change_* settings): a day with no classes goes with coming in later, being
        the start of the day stretched over all of it."""
        company = self.env.company
        return frozenset(change_type for change_type, enabled in (
            ('late_entry', company.ems_absence_change_late_entry),
            ('no_classes', company.ems_absence_change_late_entry),
            ('early_leave', company.ems_absence_change_early_leave),
            ('long_break', company.ems_absence_change_long_break),
        ) if enabled)

    @classmethod
    def _allowed_absence_changes(cls, blocks, breaks, enabled):
        """`_all_absence_changes` without the change types the centre disabled (`enabled`, see
        _enabled_absence_changes)."""
        return {side: [option for option in options if option[0] in enabled]
                for side, options in cls._all_absence_changes(blocks, breaks).items()}

    @staticmethod
    def _all_absence_changes(blocks, breaks=()):
        """Every change the absences allow the group's day, per side and from the smallest to the
        largest: `{'entry': [...], 'leave': [...], break_side: [...]}`, a `(change_type, hour)`
        tuple each, or `('long_break', hour_from, hour_to)` for a break. Every option is offered,
        not only the largest one: whoever plans may tell the families about part of it and send a
        guard to the rest. A lesson with anybody in it - a co-teacher who is not away, the other
        half of a split group, an optional subject, a guard already sent - stops a run there.

        - Entry: the students can come in later when the first lessons of their day are empty - an
          hour later, two, as many as there are in a row; a day with every lesson empty can also
          have no classes at all.
        - Leave: they can leave earlier when the last lessons are empty.
        - Each of the level's `breaks` (`(hour_from, hour_to)`) that falls between two lessons can
          be made longer by the empty lessons right before and/or after it, in any combination -
          but only while there is a lesson with somebody in it further out on that side: a run of
          empty lessons that reaches the start (or the end) of the day is a late entry (or an
          early leave), never a longer break."""
        sides = {'entry': [], 'leave': []}
        sides.update({BoardBreakSide.key(period): [] for period in breaks})
        if not blocks:
            return sides
        if all(block['empty'] for block in blocks):
            sides['entry'] = [('late_entry', block['hour_from']) for block in blocks[1:]] + [('no_classes', 0.0)]
            return sides
        leading = next(index for index, block in enumerate(blocks) if not block['empty'])
        trailing = next(index for index, block in enumerate(reversed(blocks)) if not block['empty'])
        sides['entry'] = [('late_entry', blocks[index]['hour_from']) for index in range(1, leading + 1)]
        sides['leave'] = [('early_leave', blocks[-index - 1]['hour_to']) for index in range(1, trailing + 1)]
        for break_from, break_to in breaks:
            before = next((index for index in range(len(blocks) - 1)
                           if blocks[index]['hour_to'] <= break_from + HOUR_EPSILON
                           and blocks[index + 1]['hour_from'] >= break_to - HOUR_EPSILON), None)
            if before is None:
                continue  # the break is not between two of the group's lessons that day
            starts, index = [break_from], before
            while index >= 0 and blocks[index]['empty']:
                starts.append(blocks[index]['hour_from'])
                index -= 1
            if index < 0:
                starts = [break_from]  # reaches the start of the day: that is a late entry
            ends, index = [break_to], before + 1
            while index < len(blocks) and blocks[index]['empty']:
                ends.append(blocks[index]['hour_to'])
                index += 1
            if index == len(blocks):
                ends = [break_to]  # reaches the end of the day: that is an early leave
            options = [('long_break', start, end) for start in starts for end in ends
                       if (start, end) != (break_from, break_to)]
            sides[BoardBreakSide.key((break_from, break_to))] = sorted(
                options, key=lambda change: (change[2] - change[1], -change[1]))
        return sides

    @staticmethod
    def _same_change(change, other):
        if not change or not other:
            return change == other
        return (change[0] == other[0] and len(change) == len(other)
                and all(abs(value - other_value) < HOUR_EPSILON for value, other_value in zip(change[1:], other[1:])))

    @classmethod
    def _find_change_state(cls, states, change):
        """`(state, option)`: the state among `states` (one group's sides, see
        _get_absence_change_states) offering `change` - to propose or correct it, or to change
        what was told (issue #659) - and that option; `(None, None)` when no side offers it."""
        return next(((state, option) for state in states for option in state['options'] + state['change_options']
                     if cls._same_change(option, change)), (None, None))

    @staticmethod
    def _change_window_contains(change, hour_from, hour_to):
        """Whether a period falls inside the part of the day `change` frees the group from."""
        if not change:
            return False
        change_type, hour = change[:2]
        if change_type == 'no_classes':
            return True
        if change_type == 'late_entry':
            return hour_to <= hour + HOUR_EPSILON
        if change_type == 'early_leave':
            return hour_from >= hour - HOUR_EPSILON
        if change_type == 'long_break':
            return hour_from >= hour - HOUR_EPSILON and hour_to <= change[2] + HOUR_EPSILON
        return False

    @classmethod
    def _change_frees_guard(cls, change, hour_from, hour_to):
        """Whether `change` makes a guard unnecessary for the period: it frees the group from it,
        and the students are not in the centre - a longer break keeps them in, and the students
        under 18 cannot leave it, so it still needs a guard (issue #679)."""
        return bool(change) and change[0] != 'long_break' and cls._change_window_contains(change, hour_from, hour_to)

    @staticmethod
    def _notice_change(change):
        """The change a notice communicates on one side of the day; None for a rectification back
        to the usual timetable, which communicates that nothing changes."""
        if not change or change[0] in NORMAL_CHANGE.values():
            return None
        return change

    @staticmethod
    def _change_side(change, side):
        """Whether `change` (one of those a notice tells) is about that side of the day: the start,
        the end, or the break it overlaps."""
        if not BoardBreakSide.is_break(side):
            return CHANGE_SIDES[change[0]] == side
        return change[0] in BREAK_CHANGES and overlaps(change[1], change[2], *BoardBreakSide.period(side))

    def _board_day_hour(self, day):
        """How far into `day` the centre's clock is, as a float hour: None for a day still to come,
        past every lesson for a day already over."""
        utils = self.env['ems.datetime_utils']
        local_now = utils.get_local_datetime()
        if day > local_now.date():
            return None
        return utils.time_to_float(local_now) if day == local_now.date() else 24.0

    @staticmethod
    def _change_start(change, blocks):
        """The hour `change` takes effect on a group's day (`blocks`, see _get_group_day_blocks):
        the families must be told before it. A day without classes, or a start back at the usual
        time, takes effect with the first lesson; a leave back at the usual time, with the last."""
        if change[0] in ('no_classes', 'normal_entry'):
            return blocks[0]['hour_from'] if blocks else 0.0
        if change[0] == 'normal_leave':
            return blocks[-1]['hour_to'] if blocks else 24.0
        return change[1]

    def _get_absence_change_states(self, day, groups, blocks_by_group=None):
        """`{group.id: {'entry': state, 'leave': state, break_side: state...}}` - where each side
        of each group's day (its start, its end, and each of its level's breaks)
        stands between what its absences allow (`'options'`, see _allowed_absence_changes, and
        `'expected'`, the largest of them) and what its families have been told (`'communicated'`,
        the change told on that side by the latest notice about it that left the draft state - a
        notice can tell several sides at once, issue #652). `'status'`:
        - None: nothing to communicate, nothing communicated.
        - 'communicated': the families were told one of the allowed changes - the largest one or
          a smaller one the planner chose, with a guard for the rest: it is their decision, so a
          smaller one is never nagged about. Until its time comes they may still change it for
          another allowed one or the usual timetable, with one correction (`'change_options'`,
          issue #659).
        - 'proposal': nothing communicated yet, and the absences allow a change.
        - 'rectification': what was communicated is no longer allowed (the absence shrank, was
          refused or cancelled, or the timetable changed): a sent notice cannot be undone, so a
          correcting one is proposed, with going back to the usual timetable among its options.
        `'target'` is the option proposed by default, `'draft'` a draft notice already prepared for
        one of the options and `'draft_change'` that option, and `'teachers'` the absent teachers
        whose lessons the change concerns - any of their managers can act on it.

        A change whose time has already come (see _change_start) can no longer be communicated, so
        it is never offered, and one the families were told about that has already come is settled:
        correcting it would reach them too late (issue #599). `blocks_by_group`: the groups' days,
        when the caller already has them (see _get_group_day_blocks)."""
        blocks_by_group = blocks_by_group or self._get_group_day_blocks(day, groups)
        notices = self.env['ems.notice'].sudo().search([
            ('absence_date', '=', day), ('absence_group_id', 'in', groups.ids)], order='id')
        # Every change told, oldest notice first: `{group id: [(notice, change)]}`.
        told = defaultdict(list)
        for notice in notices:
            told[notice.absence_group_id.id] += [(notice, change) for change in notice._absence_change_tuples()]
        weekday = str(day.weekday())
        now_hour = self._board_day_hour(day)
        breaks_by_level = {}
        states = {}
        enabled = self._enabled_absence_changes()
        for group in groups:
            blocks = blocks_by_group[group.id]

            def is_past(change, blocks=blocks):
                return now_hour is not None and self._change_start(change, blocks) <= now_hour

            level = group.level_id.id
            if level not in breaks_by_level:
                breaks_by_level[level] = sorted(self._get_guard_duty_board_break_periods(
                    [level], weekday, 0, 24)) if level else []
            allowed = self._allowed_absence_changes(blocks, breaks_by_level[level], enabled)
            states[group.id] = {}
            for side in allowed:
                side_told = [(notice, change) for notice, change in told[group.id] if self._change_side(change, side)]
                communicated = self._notice_change(next((
                    change for notice, change in reversed(side_told) if notice.state in COMMUNICATED_NOTICE_STATES), None))
                options = [option for option in allowed[side] if not is_past(option)]
                expected = options[-1] if options else None
                normal = (('normal_break', *BoardBreakSide.period(side)) if BoardBreakSide.is_break(side)
                          else (NORMAL_CHANGE[side], 0.0))
                usual = [] if is_past(normal) else [normal]
                change_options = []
                if not communicated:
                    status = 'proposal' if options else None
                elif is_past(communicated):
                    status, options = 'communicated', []
                elif any(self._same_change(communicated, option) for option in options):
                    # Still true, but whoever organises it may change their mind (issue #659).
                    change_options = [option for option in options if not self._same_change(option, communicated)] + usual
                    status, options = 'communicated', []
                else:
                    options = options + usual
                    status = 'rectification' if options else None
                target = options[-2] if status == 'rectification' and len(options) > 1 else (options[-1] if options else None)
                draft, draft_change = next((
                    (notice, change) for notice, change in reversed(side_told) if notice.state == 'draft'
                    and any(self._same_change(change, option) for option in options + change_options)), (notices.browse(), None))
                window = [block for block in blocks if any(
                    self._change_window_contains(other, block['hour_from'], block['hour_to'])
                    for other in (expected, communicated))]
                teachers = self.env['hr.employee'].union(*(
                    block['teachers'].filtered(lambda teacher, block=block: teacher.id in block['absences'])
                    for block in window))
                states[group.id][side] = {
                    'allowed': allowed[side],
                    'expected': expected,
                    'communicated': communicated,
                    'status': status,
                    'options': options,
                    'change_options': change_options,
                    'target': target,
                    'draft': draft,
                    'draft_change': draft_change,
                    'teachers': teachers or self.env['hr.employee'].union(*(block['teachers'] for block in blocks)),
                }
        return states

    def _get_needed_absence_block(self, day, group, absent, hour_from, hour_to):
        """The block of `group`'s day where `absent`'s lesson in the period still needs a guard:
        the teacher is away then, no co-teacher is in the class, and the families have not been
        told the students can stay at home for it. None when it no longer does - which is how a
        guard assignment made earlier is found to be unnecessary, and what stops a new one."""
        blocks = self._get_group_day_blocks(day, group)[group.id]
        block = next((block for block in blocks
                      if overlaps(block['hour_from'], block['hour_to'], hour_from, hour_to)
                      and absent in block['teachers'] and absent.id in block['absences']), None)
        if not block or self._guard_duty_is_co_taught(block['entries'], absent, block['absences']):
            return None
        sides = self._get_absence_change_states(day, group)[group.id]
        # A side being changed (issue #659) frees nothing: its lessons are planned again.
        if any(self._change_frees_guard(sides[side]['communicated'], block['hour_from'], block['hour_to'])
               for side in sides if self._reopened_side() != (group.id, side)):
            return None
        return block

    def _guard_cover_counts(self, guards):
        """How many times each guard has been sent to cover during this course (issue #600), as
        {employee id: count}, so whoever plans the guards can share them out fairly. Only assigned
        covers count, the ones already planned for a coming day included: a released one was never
        done, and an assignment for tomorrow is work already given to that guard. Covers of the
        same guard in the same room in the same period count once (issue #629): two groups put
        together in one room are a single guard, while two groups in two rooms are two, and so are
        two periods in a row with the same group. A cover with no room (a guard duty, a class the
        timetable gives none) always counts by itself.

        sudo: a count everybody who opens the board sees, the Secretary included, who reads it
        without being a teacher (only teachers can read ems.absence_cover itself). Only the number
        leaves this method, like the board's other reads of covers (_get_day_covers)."""
        self.ensure_one()
        start, end = self.date_range()
        periods = self.env['ems.absence_cover'].sudo()._read_group(
            [('guard_employee_id', 'in', guards.ids), ('state', '=', 'assigned'),
             ('date', '>=', start), ('date', '<=', end)],
            ['guard_employee_id', 'date:day', 'space_id', 'hour_from', 'hour_to'], ['__count'])
        counts = defaultdict(int)
        for guard, _day, space, _hour_from, _hour_to, count in periods:
            counts[guard.id] += 1 if space else count
        return dict(counts)

    def _get_needed_duty_entry(self, day, duty, absent, hour_from, hour_to):
        """`absent`'s own guard duty `duty` in the period, while it still needs covering (issue
        #606): a duty that is not regular (WC, break...), on their timetable that day, and they are
        away then. An empty recordset when it no longer does, which is what finds a cover made
        earlier unnecessary and stops a new one."""
        weekday = str(day.weekday())
        entries = self._get_guard_duty_board_attendance_ids([('dayofweek', '=', weekday), ('non_teaching', '=', duty.id)]).filtered(
            lambda attendance: attendance.employee_id == absent and not duty.is_regular_guard
                and overlaps(attendance.hour_from, attendance.hour_to, hour_from, hour_to))
        intervals = self._get_guard_duty_absence_intervals(day, absent, unchecked=True)
        if not entries or absent.id not in self._guard_duty_absence_state(intervals, absent, hour_from, hour_to):
            return entries.browse()
        return entries[:1]

    def _guard_spans(self, guard_entries, intervals, covers, hour_from, hour_to):
        """`{guard employee: (hour_from, hour_to)}`: who can be sent to the class (or guard duty that
        is not regular) of the period, and for which part of it (issue #637) - their regular guard
        duty (`guard_entries`, issue #606: a WC or break guard is needed where they are) clipped to
        the period, consecutive duties joined, the longest piece if they are not consecutive. A
        guard away (`intervals`) or with a group through an internal arrangement (`covers`, issue
        #605) during their piece cannot. A co-teacher who could not follow a lesson an arrangement
        moved (issue #678) is on guard while it is gone, and so is a teacher who took their lesson to
        their own regular guard (issue #709, see _moved_guards). No query: the board calls it once per line
        with data it already holds, the board actions through _get_guard_candidates()."""
        pieces = defaultdict(list)
        for attendance in guard_entries:
            start, stop = max(attendance.hour_from, hour_from), min(attendance.hour_to, hour_to)
            if stop - start > HOUR_EPSILON:
                pieces[attendance.employee_id].append((start, stop))
        for teacher, (piece, _label) in self._moved_guards(covers, guard_entries, hour_from, hour_to).items():
            pieces[teacher].append(piece)
        spans = {}
        for guard, guard_pieces in pieces.items():
            merged = []
            for start, stop in sorted(guard_pieces):
                if merged and start <= merged[-1][1] + HOUR_EPSILON:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], stop))
                else:
                    merged.append((start, stop))
            start, stop = max(merged, key=lambda piece: piece[1] - piece[0])
            if self._guard_duty_absence_state(intervals, guard, start, stop) \
                    or guard.id in self._arrangement_busy(covers, start, stop):
                continue
            spans[guard] = (start, stop)
        return spans

    def _get_guard_candidates(self, day, hour_from, hour_to):
        """The guards who can be sent to cover a class, or a guard duty that is not regular, in the
        period, and for which part of it - see _guard_spans()."""
        # The whole day's: a guard an arrangement moved (issue #709) comes from another hour.
        guard_entries = self._get_guard_duty_board_attendance_ids([
            ('dayofweek', '=', str(day.weekday())), ('non_teaching.is_regular_guard', '=', True)])
        covers = self._get_day_covers(day)
        intervals = self._get_guard_duty_absence_intervals(
            day, guard_entries.employee_id | covers.stayed_employee_ids, unchecked=True)
        return self._guard_spans(guard_entries, intervals, covers, hour_from, hour_to)

    def _moved_guards(self, covers, regular_guards, hour_from, hour_to):
        """`{employee: ((hour_from, hour_to), label)}`: who is on guard in the period because an
        arrangement in effect moved a lesson, for which part of it (the lesson's usual time) and the
        tag saying why: a co-teacher who could not follow it (issue #678, "lesson moved"), and a
        teacher who took it to one of their own regular guards (`regular_guards`, the day's), which
        goes to the lesson's hour instead (issue #709, "guard moved from ..."); at the guard's own
        hour they are with the group, struck out (see _arrangement_busy). A meeting or any other
        duty swapped that way is not a guard: it shows nowhere."""
        moved = {}
        for cover in covers.filtered(lambda cover: cover.cover_type == 'arrangement' and cover.vacated_hour_to
                                     and cover.is_effective):
            start, stop = max(cover.vacated_hour_from, hour_from), min(cover.vacated_hour_to, hour_to)
            if stop - start <= HOUR_EPSILON:
                continue
            for teacher in cover.stayed_employee_ids:
                moved[teacher] = ((start, stop), _("lesson moved"))
            guard = regular_guards.filtered(
                lambda attendance, cover=cover: attendance.employee_id == cover.guard_employee_id
                and overlaps(attendance.hour_from, attendance.hour_to, cover.hour_from, cover.hour_to))[:1]
            if guard:
                moved[cover.guard_employee_id] = ((start, stop), _("guard moved from %s", self._format_report_time(guard.hour_from)))
        return moved

    def _get_day_covers(self, day):
        return self.env['ems.absence_cover'].sudo().search([('date', '=', day), ('state', '=', 'assigned')])

    @staticmethod
    def _arrangement_busy(covers, hour_from, hour_to):
        """`{employee.id: cover}`: the teachers an internal arrangement (issue #605) has with a
        group in the period - in effect or waiting for its notice, the planner has decided it -,
        who therefore cannot be asked to cover anything else then: whoever is with the group
        instead of the absent teacher, and in a swap the absent teacher too, at the lesson they
        take over."""
        busy = {}
        for cover in covers.filtered(lambda cover: cover.cover_type == 'arrangement'):
            if cover.guard_employee_id and overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to):
                busy[cover.guard_employee_id.id] = cover
            if cover.arrangement_type == 'swap' and overlaps(cover.vacated_hour_from, cover.vacated_hour_to, hour_from, hour_to):
                busy[cover.absent_employee_id.id] = cover
        return busy

    def _arrangement_context(self, day):
        """What detecting arrangements needs, read once per board load: the weekday's timetable
        (also indexed by teacher, so nothing filters the whole centre's timetable per question),
        everybody's absences that day, the covers already decided, and the plans of each set of
        linked groups (filled in lazily by _get_arrangement_plans)."""
        entries = self._get_guard_duty_board_attendance_ids([('dayofweek', '=', str(day.weekday()))])
        ids = defaultdict(list)
        for attendance in entries:
            ids[attendance.employee_id.id].append(attendance.id)
        return {
            'day': day,
            'entries': entries,
            'by_teacher': {teacher_id: entries.browse(attendance_ids).with_prefetch(entries._prefetch_ids)
                           for teacher_id, attendance_ids in ids.items()},
            'intervals': self._get_guard_duty_absence_intervals(day, entries.employee_id),
            'covers': self._get_day_covers(day),
            'plans': {},
        }

    def _is_free_for_arrangement(self, context, covers, teacher, hour_from, hour_to):
        """Whether `teacher` can be with a group in the period: in the centre and not away, no
        class of their own, no guard duty that is not regular (WC, break... needed where they are,
        issue #606), and not already covering anything else then. A regular guard duty does not stop them - they are struck out of the
        guard column instead."""
        if self._guard_duty_absence_state(context['intervals'], teacher, hour_from, hour_to):
            return False
        if any(overlaps(attendance.hour_from, attendance.hour_to, hour_from, hour_to)
               and (attendance.subject_id or attendance.group_ids
                    or (attendance.non_teaching.is_guard and not attendance.non_teaching.is_regular_guard))
               for attendance in context['by_teacher'].get(teacher.id, ())):
            return False
        if covers.filtered(lambda cover: cover.guard_employee_id == teacher
                           and overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to)):
            return False
        return teacher.id not in self._arrangement_busy(covers, hour_from, hour_to)

    def _schedule_shift(self, context, teacher, removed, added):
        """How `teacher`'s working day that day changes if they stop teaching the `removed` periods
        and teach the `added` ones instead; None when it would get longer (see
        arrangement_planner.schedule_shift)."""
        attendances = context['by_teacher'].get(teacher.id, ())
        return schedule_shift([(attendance.hour_from, attendance.hour_to) for attendance in attendances], removed, added,
                              self._duty_periods(attendances))

    @staticmethod
    def _duty_periods(attendances):
        """The periods of `attendances` (a teacher's day) with no class: guards, coordinations and
        any other non-teaching hour, which a lesson taken there swaps with (see schedule_shift)."""
        return [(attendance.hour_from, attendance.hour_to) for attendance in attendances
                if not attendance.subject_id and not attendance.group_ids]

    def _arrangement_shifts(self, context, arrangement_type, absent, teacher, hour_from, hour_to, lesson):
        """`[(teacher, kind, old, new)]`: the entry and exit times an arrangement changes, for
        every teacher it moves (in a swap both of them, in a moved lesson whoever moves it); None
        when it would lengthen somebody's day."""
        moves = [(teacher, lesson, (hour_from, hour_to))]
        if arrangement_type == 'swap':
            moves.append((absent, (hour_from, hour_to), lesson))
        shifts = []
        for employee, removed, added in moves:
            shift = self._schedule_shift(context, employee, [removed], [added])
            if shift is None:
                return None
            shifts += [(employee, *change) for change in shift]
        return shifts

    def _arrangement_sessions(self, context):
        """`[(lesson, frozenset(group ids), frozenset(teacher ids), frozenset(away ids))]`: the
        day's lessons, each with every teacher who gives it and those of them away then (issue
        #678). Co-teachers - several teachers with the same groups (or some of them) at the same
        time - are a pack: an arrangement moves the lesson with all of them. Computed once per
        board load (see _arrangement_context)."""
        if 'sessions' not in context:
            by_period = defaultdict(list)
            for attendance in context['entries']:
                if attendance.group_ids:
                    by_period[(attendance.hour_from, attendance.hour_to)].append(attendance)
            sessions = []
            for lesson, attendances in sorted(by_period.items()):
                # The lessons of this period sharing a group, directly or through another one.
                pending = [(frozenset(attendance.group_ids.ids), {attendance.employee_id.id}) for attendance in attendances]
                merged = []
                while pending:
                    group_ids, teacher_ids = pending.pop()
                    linked = [other for other in merged if other[0] & group_ids]
                    for other in linked:
                        merged.remove(other)
                        group_ids, teacher_ids = group_ids | other[0], teacher_ids | other[1]
                    merged.append((group_ids, teacher_ids))
                for group_ids, teacher_ids in merged:
                    away = self._guard_duty_absence_state(
                        context['intervals'], self.env['hr.employee'].browse(teacher_ids), *lesson)
                    sessions.append((lesson, group_ids, frozenset(teacher_ids), frozenset(away)))
            context['sessions'] = sessions
        return context['sessions']

    def _group_sessions(self, context, group_ids):
        """The sessions (see _arrangement_sessions) of any of `group_ids`, indexed by group once
        per board load."""
        if 'sessions_by_group' not in context:
            by_group = defaultdict(list)
            for session in self._arrangement_sessions(context):
                for group_id in session[1]:
                    by_group[group_id].append(session)
            context['sessions_by_group'] = by_group
        sessions = dict.fromkeys(session for group_id in group_ids for session in context['sessions_by_group'][group_id])
        return sorted(sessions, key=lambda session: (session[0], sorted(session[1]), sorted(session[2])))

    def _get_arrangement_options(self, day, group, absent, hour_from, hour_to, exclude=None, context=None):
        """The lesson swaps that would leave the class of `group` in the period, whose teachers
        `absent` are all away, without needing a guard (issue #605): another lesson of the group
        that day, its teachers free now teach now, and the absent teachers, all of them in and free
        at that other lesson, teach it. Nobody loses a lesson. Moved lessons are planned with the
        rest of the group's day instead (issue #645, see _get_arrangement_plans), which also scores
        these swaps.
        The teachers of a lesson are a pack (issue #678): they all come to the class; one who
        cannot (busy or away now, or their day would get longer) stays on guard at their own
        lesson instead, which the plan warns about. On the absent side all of them must make it.
        Nobody's working day may get longer (see _schedule_shift): whoever would come in earlier
        must leave earlier, and the other way round.
        Each option is `{'type': 'swap', 'teacher', 'stays', 'hour_from', 'hour_to', 'shifts'}`, the
        hours being the other lesson's, 'teacher' the teachers who come, 'stays' those who cannot,
        and 'shifts' the entry/exit times it changes (see _arrangement_shifts); those that change
        nobody's entry or exit first. Only within the group and the day: anything else is a manual
        arrangement. `exclude`: covers being replaced, ignored. A lesson shared with other groups is
        never swapped: their day would change too.
        """
        context = context or self._arrangement_context(day)
        covers = context['covers'] - (exclude or self.env['ems.absence_cover'])
        vacated = covers.filtered(lambda cover: cover.group_id == group and cover.vacated_hour_to)
        Employee = self.env['hr.employee']
        options = []
        for lesson, group_ids, pack, away in self._group_sessions(context, group.ids):
            if group_ids != {group.id} or overlaps(*lesson, hour_from, hour_to) or pack & set(absent.ids):
                continue
            if vacated.filtered(lambda cover, lesson=lesson: overlaps(cover.vacated_hour_from, cover.vacated_hour_to, *lesson)):
                continue  # that lesson is already part of another arrangement
            shifts = []
            for teacher in absent:
                shift = self._schedule_shift(context, teacher, [(hour_from, hour_to)], [lesson])
                if shift is None or not self._is_free_for_arrangement(context, covers, teacher, *lesson):
                    break
                shifts += [(teacher, *change) for change in shift]
            else:
                teachers = stays = Employee
                for teacher in Employee.browse(sorted(pack)).sorted('name'):
                    shift = self._schedule_shift(context, teacher, [lesson], [(hour_from, hour_to)])
                    if shift is None or not self._is_free_for_arrangement(context, covers, teacher, hour_from, hour_to):
                        if teacher.id not in away:
                            stays |= teacher  # in at their lesson: on guard while it is gone
                        continue
                    teachers |= teacher
                    shifts += [(teacher, *change) for change in shift]
                if teachers:
                    options.append({'type': 'swap', 'teacher': teachers, 'stays': stays, 'hour_from': lesson[0],
                                    'hour_to': lesson[1], 'shifts': shifts})
        return sorted(options, key=lambda option: (bool(option['shifts']), option['hour_from'], option['teacher'].mapped('name')))

    def _linked_groups(self, context, group):
        """`group` and every group sharing a lesson with it that day, directly or through another
        one: moving a shared lesson changes all of their days at once (issue #645). Also the other
        halves it could be joined with that day (issue #660, see _split_partners): a join changes
        the day of the half that moves and needs the other one's."""
        shared = context.setdefault('shared', context['entries'].filtered(lambda attendance: len(attendance.group_ids) > 1))
        partners = self._split_partners(context)
        Group = self.env['ems.group']
        linked = pending = group
        while pending:
            pending = (shared.filtered(lambda attendance: attendance.group_ids & pending).group_ids
                       | Group.browse(sorted({partner for group_id in pending.ids for partner in partners.get(group_id, ())}))) - linked
            linked |= pending
        return linked

    def _split_partners(self, context):
        """`{group id: frozenset(group ids)}`: the other halves each group could be joined with on
        the board's day (issue #660). Two groups are halves of the same one when their forms say so
        ('Joins with', issue #676: sharing a lesson is not enough), and they can be joined that day
        when a teacher teaches both the same subject at different hours. Read once per board load,
        and only when arrangements are planned."""
        if 'partners' not in context:
            halves = {group.id: frozenset(group.joinable_group_ids.ids)
                      for group in context['entries'].group_ids if group.joinable_group_ids}
            lessons = defaultdict(list)
            for attendance in context['entries']:
                if attendance.subject_id and halves.keys() & set(attendance.group_ids.ids):
                    lessons[(attendance.employee_id.id, attendance.subject_id.id)].append(attendance)
            partners = defaultdict(set)
            for same_subject in lessons.values():
                for first in same_subject:
                    for second in same_subject:
                        if overlaps(first.hour_from, first.hour_to, second.hour_from, second.hour_to):
                            continue
                        for group_id in first.group_ids.ids:
                            partners[group_id] |= halves.get(group_id, frozenset()) & set(second.group_ids.ids)
            context['partners'] = {group_id: frozenset(ids) for group_id, ids in partners.items() if ids}
        return context['partners']

    def _get_arrangement_plans(self, day, group, context=None):
        """The best internal arrangements (issues #605, #645) for `group`'s day and the days of the
        groups sharing lessons with it: chains of moved lessons, each teacher filling the gap the
        previous one left, until what is left free reaches the start or the end of the day (or a
        break) and the families are told; and swaps. See ArrangementPlanner for how they are found
        and ranked. Cached per set of linked groups in `context`, so a board load computes each one
        once whatever the number of its rows.

        Each plan is `{'key', 'groups', 'steps'}`, its steps in the order they apply and with the
        indexes of those each one needs ('depends'): `{'kind': 'move' | 'swap' | 'join', 'teacher',
        'lesson', 'target', 'groups', 'absent', 'joined', 'stays', 'stay_reasons', 'shifts',
        'depends'}` - the teachers' lesson (`lesson`) taught in the gap (`target`) for those groups,
        in a swap the `absent` teachers teaching that lesson, in a join the other halves it is
        taught together with (see ArrangementPlanner for the step kinds) - or `{'kind': 'notice' |
        'correction', 'groups', 'change', 'depends'}`, the same timetable change told to the
        families of every one of `groups`."""
        context = context or self._arrangement_context(day)
        groups = self._linked_groups(context, group).sorted('name')
        key = tuple(sorted(groups.ids))
        if key not in context['plans']:
            planner, states = self._arrangement_planner(context, groups)
            context['plans'][key] = [self._arrangement_plan_records(context, raw, groups, number, states) for number, raw
                                     in enumerate(planner.plans(), start=1)]
        return context['plans'][key]

    def _reopened_side(self):
        """`(group id, side)` whose communicated change is being changed (issue #659, the
        'ems_reopen_side' context key, see get_change_proposal_options), or None."""
        reopen = self.env.context.get('ems_reopen_side')
        return (reopen[0], reopen[1]) if reopen else None

    def _arrangement_planner(self, context, groups):
        """`(planner, states)`: an ArrangementPlanner over the day of `groups` (a set of linked
        groups, see _linked_groups), fed with what `context` already read, and the groups'
        timetable-change states it was built from (see _get_absence_change_states)."""
        day = context['day']
        covers = context['covers']
        blocks_by_group = self._get_group_day_blocks(day, groups)
        states = self._get_absence_change_states(day, groups, blocks_by_group)
        reopen = self._reopened_side()
        weekday = str(day.weekday())
        # An arrangement still waiting for its notice is decided: its class is not a gap to fill.
        pending = covers.filtered(lambda cover: cover.cover_type == 'arrangement' and not cover.is_effective)
        blocks, breaks, communicated, swaps = {}, {}, {}, []
        for group in groups:
            blocks[group.id] = [{
                'hour_from': block['hour_from'],
                'hour_to': block['hour_to'],
                'teachers': frozenset(block['teachers'].ids),
                # A teacher who has not checked in is no gap to fill (issue #692): only a guard.
                'away': frozenset(teacher_id for teacher_id, state in block['absences'].items() if state != 'unchecked'),
                'filled': bool(block['covers']) or any(
                    cover.group_id == group and overlaps(cover.hour_from, cover.hour_to, block['hour_from'], block['hour_to'])
                    for cover in pending),
            } for block in blocks_by_group[group.id]]
            breaks[group.id] = sorted(self._get_guard_duty_board_break_periods(
                [group.level_id.id], weekday, 0, 24)) if group.level_id else []
            # A side being changed (issue #659) is planned as if nothing had been told about it.
            communicated[group.id] = {side: None if reopen == (group.id, side) else state['communicated']
                                      for side, state in states[group.id].items()}
            for block, data in zip(blocks_by_group[group.id], blocks[group.id]):
                if not data['teachers'] <= data['away'] or data['filled']:
                    continue
                absents = self._block_absents(block)
                for option in self._get_arrangement_options(
                        day, group, absents, block['hour_from'], block['hour_to'], context=context):
                    swaps.append(('swap', frozenset(option['teacher'].ids), (option['hour_from'], option['hour_to']),
                                  (block['hour_from'], block['hour_to']), frozenset(group.ids), frozenset(absents.ids),
                                  frozenset(option['stays'].ids), frozenset()))
        sessions = self._group_sessions(context, groups.ids)
        vacated = covers.filtered(lambda cover: cover.group_id in groups and cover.vacated_hour_to)
        employees = context['entries'].filtered(lambda attendance: attendance.group_ids & groups).employee_id
        teachers = {teacher.id: {
            'lessons': sorted({((attendance.hour_from, attendance.hour_to), frozenset(attendance.group_ids.ids),
                                attendance.subject_id.id) for attendance in context['by_teacher'][teacher.id]
                               if attendance.group_ids & groups}),
            'periods': [(attendance.hour_from, attendance.hour_to) for attendance in context['by_teacher'][teacher.id]],
            'duties': self._duty_periods(context['by_teacher'][teacher.id]),
            'vacated': [(cover.vacated_hour_from, cover.vacated_hour_to) for cover in vacated
                        if teacher in cover.guard_employee_id | cover.stayed_employee_ids],
        } for teacher in employees}
        employees = {teacher.id: teacher for teacher in employees}
        free_cache = {}

        def free(teacher_id, hour_from, hour_to):
            if (teacher_id, hour_from, hour_to) not in free_cache:
                free_cache[teacher_id, hour_from, hour_to] = self._is_free_for_arrangement(
                    context, covers, employees[teacher_id], hour_from, hour_to)
            return free_cache[teacher_id, hour_from, hour_to]

        partners = {group_id: ids & frozenset(groups.ids) for group_id, ids in self._split_partners(context).items()
                    if group_id in groups.ids}
        return ArrangementPlanner(self, blocks, breaks, communicated, self._board_day_hour(day), teachers, sessions, free,
                                  swaps, partners=partners), states

    @staticmethod
    def _block_absents(block):
        """The teachers away from a class left empty (see _get_group_day_blocks): all of its
        teachers but those whose lesson an arrangement moved elsewhere."""
        return block['teachers'].filtered(lambda teacher: block['absences'].get(teacher.id) != 'moved')

    def _arrangement_plan_records(self, context, raw, groups, number, states):
        """A plan from ArrangementPlanner as records, its steps in the order they are shown and
        applied: by time, a step never before one it needs. A teacher's entry/exit change goes with
        their last step, and one notice step tells the same change to every group it applies to.

        The plan also corrects what the families of its groups were told (issue #659), so that each
        group gets one email and whoever only wants the correction unchecks the rest: 'correction'
        steps, after every other one, for each side of `states` (the groups' timetable-change
        states) whose communicated change no longer matches the absences (its correction as the
        correction alone would propose it), and for the side being changed (see _reopened_side):
        a notice of the plan on that side becomes its correction - or is dropped, if it repeats what
        was told - and without one the correction puts that side back to the usual timetable.
        A co-teacher who cannot follow their lesson (issue #678) comes in 'stays', with why in
        'stay_reasons' ('away', 'busy', 'apart' or 'day'), and what kind of move it is for each
        teacher in 'how' (issue #709, see _arrangement_step_how)."""
        Employee, Group = self.env['hr.employee'], self.env['ems.group']
        items = []
        for index, step in enumerate(raw['steps']):
            stays = Employee.browse(sorted(step[6])).sorted('name')
            items.append({
                'kind': step[0], 'teacher': Employee.browse(sorted(step[1])).sorted('name'), 'lesson': step[2],
                'target': step[3], 'groups': Group.browse(sorted(step[4])), 'absent': Employee.browse(sorted(step[5])),
                'joined': Group.browse(sorted(step[7])), 'stays': stays, 'stay_reasons': {
                    teacher: self._stay_reason(context, teacher, step, raw['steps'][:index]) for teacher in stays},
                'how': self._arrangement_step_how(context, step, raw['shifts']),
                'needs': set(raw['depends'][index]), 'time': step[3][0], 'source': index,
            })
        reopen = self._reopened_side()
        notices = {}

        def tell(kind, group_id, change, depends=()):
            notice = notices.setdefault((kind, change), {'kind': kind, 'groups': Group, 'change': change, 'needs': set(),
                                                         'time': 0.0 if change[0] == 'no_classes' else change[1], 'source': None})
            notice['groups'] |= Group.browse(group_id)
            notice['needs'] |= set(depends)

        for (group_id, side, change), depends in zip(raw['notices'], raw['notice_depends']):
            if reopen != (group_id, side):
                tell('notice', group_id, change, depends)
            elif not self._same_change(change, states[group_id][side]['communicated']):
                tell('correction', group_id, change, depends)
        for group in groups:
            for side, state in states[group.id].items():
                if state['status'] == 'rectification':
                    tell('correction', group.id, state['target'])
                elif reopen == (group.id, side) and state['change_options'] and not any(
                        notice_group == group.id and notice_side == side for notice_group, notice_side, _change in raw['notices']):
                    tell('correction', group.id, state['change_options'][-1])  # the usual timetable
        items += notices.values()
        ordered, placed, done = [], set(), set()
        while len(ordered) < len(items):
            item = min((item for item in items if id(item) not in done and item['needs'] <= placed),
                       key=lambda item: (item['kind'] == 'correction', item['time'], item['kind'] == 'notice',
                                         item['groups'].mapped('name'), item['source'] or 0))
            ordered.append(item)
            done.add(id(item))
            if item['source'] is not None:
                placed.add(item['source'])
        position = {item['source']: index for index, item in enumerate(ordered) if item['source'] is not None}
        last = {}
        for index, item in enumerate(ordered):
            if item['kind'] in ('move', 'swap', 'join'):
                for teacher in item['teacher'] | item['absent']:
                    last[teacher.id] = index
        steps = []
        for index, item in enumerate(ordered):
            step = {key: value for key, value in item.items() if key not in ('needs', 'time', 'source')}
            step['depends'] = sorted(position[need] for need in item['needs'])
            if item['kind'] in ('move', 'swap', 'join'):
                owners = (item['teacher'] | item['absent']).ids
                step['shifts'] = [(Employee.browse(owner), *change) for owner in owners if last.get(owner, index) == index
                                  for change in raw['shifts'].get(owner) or ()]
            steps.append(step)
        return {'key': f"{'-'.join(map(str, sorted(groups.ids)))}:{number}", 'number': number, 'groups': groups, 'steps': steps}

    def _stay_reason(self, context, teacher, step, earlier_steps):
        """Why `teacher` cannot follow their lesson into the gap of `step`: 'away' then, 'busy'
        (a class or a duty of theirs, or an earlier step of the plan takes them there), 'apart'
        (in a join, issue #660: they are not teaching the other half then) or 'day' (their working
        day would get longer)."""
        target = step[3]
        if self._guard_duty_absence_state(context['intervals'], teacher, *target):
            return 'away'
        if any(teacher.id in other[1] and overlaps(*other[3], *target) for other in earlier_steps):
            return 'busy'
        if step[0] == 'join':
            joined = step[7]
            with_half = any(set(attendance.group_ids.ids) & joined and overlaps(attendance.hour_from, attendance.hour_to, *target)
                            for attendance in context['by_teacher'].get(teacher.id, ()))
            return 'day' if with_half else 'apart'
        if not self._is_free_for_arrangement(context, context['covers'], teacher, *target):
            return 'busy'
        return 'day'

    def _arrangement_step_how(self, context, step, shifts):
        """`[(teacher, kind, duty name)]`: what a moved lesson, join or swap (a planner step) is for
        each teacher who takes their lesson to its gap (issue #709): 'join' (taught together with
        the other half), 'guard' or 'duty' (it swaps with a regular guard or another non-teaching
        hour of theirs, see schedule_shift), and in a move to an hour off their timetable 'shift'
        (their whole day moves: `shifts`, the plan's, change both their entry and exit) or 'free'
        (a free hour of theirs). Nothing for a swap's free hour: the swap says it all."""
        kind, teacher_ids, _lesson, target = step[:4]
        how = []
        for teacher in self.env['hr.employee'].browse(sorted(teacher_ids)).sorted('name'):
            if kind == 'join':
                how.append((teacher, 'join', False))
                continue
            duty = next((attendance for attendance in context['by_teacher'].get(teacher.id, ())
                         if not attendance.subject_id and not attendance.group_ids
                         and overlaps(attendance.hour_from, attendance.hour_to, *target)), None)
            if duty and duty.non_teaching.is_regular_guard:
                how.append((teacher, 'guard', False))
            elif duty:
                how.append((teacher, 'duty', duty.non_teaching.name or duty.name))
            elif kind == 'move':
                changes = {change[0] for change in shifts.get(teacher.id) or ()}
                how.append((teacher, 'shift' if changes == {'entry', 'exit'} else 'free', False))
        return how

    def _arrangement_step_details(self, step, values):
        """The lines under a step saying what kind of move it is (issue #709, see
        _arrangement_step_how): one per kind, naming the teachers only when they differ."""
        texts = {
            'guard': lambda _duty: _("swap with their guard, which moves to %s", values['lesson']),
            'duty': lambda duty: _("swap with their non-teaching hour (%s)", duty),
            'free': lambda _duty: _("to a free hour"),
            'shift': lambda _duty: _("working day shifted"),
            'join': lambda _duty: _("groups joined with %s", values['joined']),
        }
        icons = {'guard': 'fa-exchange', 'duty': 'fa-exchange', 'free': 'fa-circle-o', 'shift': 'fa-step-forward',
                 'join': 'fa-compress'}
        kinds = {}
        for teacher, kind, duty in step.get('how', ()):
            kinds.setdefault((kind, duty), self.env['hr.employee'])
            kinds[(kind, duty)] |= teacher
        details = []
        for (kind, duty), teachers in kinds.items():
            text = texts[kind](duty)
            if len(kinds) > 1:
                text = _("%(teacher)s: %(how)s", teacher=format_list(self.env, teachers.mapped('name')), how=text)
            details.append({'icon': icons[kind], 'text': text})
        return details

    @classmethod
    def _plan_resolves(cls, plan, group, hour_from, hour_to):
        """Whether `plan` resolves the class of `group` in the period: a step fills it, or one of
        its notices frees the group from it."""
        return any(
            group in step['groups'] and (
                cls._change_frees_guard(step['change'], hour_from, hour_to) if step['kind'] == 'notice'
                else overlaps(*step['target'], hour_from, hour_to))
            for step in plan['steps'] if step['kind'] != 'correction')

    @api.model
    def get_arrangement_candidates(self, day, hour_from, hour_to, absent_employee_id, group_id):
        """The teachers who can be named in a manual arrangement (issue #605) for the board's
        dialog: anybody with a timetable that day who is not away in the period. Unlike the
        detected arrangements, a class of their own does not rule them out: joining two groups for
        the same subject is precisely one of the things recorded by hand."""
        day = fields.Date.to_date(day)
        absent = self.env['hr.employee'].browse(absent_employee_id).exists()
        if not absent or not self.env['ems.group'].browse(group_id).exists():
            raise UserError(_("The class or the guard teacher no longer exists."))
        self._check_absence_manager(absent, self.env['ems.group'].browse(group_id))
        teachers = self._get_guard_duty_board_attendance_ids([('dayofweek', '=', str(day.weekday()))]).employee_id - absent
        away = self._guard_duty_absence_state(
            self._get_guard_duty_absence_intervals(day, teachers), teachers, hour_from, hour_to)
        return [{'id': teacher.id, 'name': teacher.display_name}
                for teacher in teachers.sorted('name') if teacher.id not in away]

    @api.model
    def get_change_proposal_options(self, day, group_id, side):
        """What the "Change proposal" dialog of a struck-out row offers (issue #659): the change
        the families were told on that `side` of the group's day ('told') and what it can still be
        changed for: another change the absences allow or the usual timetable ('options', each
        sent as one correction by ems.notice.board_send_absence_change), or an internal
        arrangement of the group's day ('plans', with the correction among its steps, applied by
        ems.absence_cover.board_apply_plan with 'reopen'). Only for whoever organises the absences
        it concerns, and only before its time comes."""
        day = fields.Date.to_date(day)
        group = self.env['ems.group'].browse(group_id).exists()
        if not group:
            raise UserError(_("This group no longer exists."))
        self._check_board_day_not_past(day)
        state = self._get_absence_change_states(day, group)[group.id].get(side)
        if not state or not state['change_options']:
            raise UserError(_("The absences of this group have changed since the board was loaded. Reload the board."))
        if not any(self._is_absence_manager(teacher, group) for teacher in state['teachers']):
            raise AccessError(_("Only whoever organises the absences of this group's classes can do this."))
        # The internal arrangements that could replace it, planned as if nothing had been told on
        # that side: each brings its correction along, so the families still get one email.
        reopened = self.with_context(ems_reopen_side=[group.id, side])
        plans = [plan for plan in reopened._get_arrangement_plans(day, group, context=reopened._arrangement_context(day))
                 if any(step['kind'] in ('move', 'swap', 'join') and group in step['groups'] for step in plan['steps'])]
        return {
            'group': group.name,
            'told': self._absence_change_label(state['communicated']),
            'options': [self._change_option_data(change) for change in state['change_options']],
            'plans': [reopened._arrangement_plan_data(plan) for plan in plans],
            'reopen': [group.id, side],
        }

    def _change_option_data(self, change):
        """JSON-safe version of one timetable change the planner can choose, as the board's
        selectors and ems.notice.board_send_absence_change take it."""
        return {'change_type': change[0], 'hour': change[1], 'hour_to': change[2] if len(change) > 2 else 0.0,
                'change': list(change), 'label': self._absence_change_label(change)}

    def get_guard_duty_board_lines(self, weekday, shift, area_ids=None, day=None):
        """Board rows for one weekday + shift: the group columns actually taught in that slot
        (grouped by area, then by name), one line per distinct time period (chronological), each
        with one cell per group (teacher(s) + room, or empty) plus the guard-duty teacher(s) for
        that period. A guard carries no group of its own (see 'non_teaching'), so it's reported
        separately from the group columns instead of as one more column. Both views of the board
        are also laid out here once, on a real time axis, for the screen and the PDF to render:
        'schedule_grid' and 'absence_grid' (see BoardTimeGrid).

        A period fully contained in another one never gets a line of its own - its cells and
        guards fold into the line of the period that contains it (_merge_absorbed_periods(), issue
        #410: a teacher's own shortened period) - unless it is a period of some schedule framework
        (a lesson or a break of some level): each area keeps its own time framework, and folding
        one area's break into another area's lesson offered its break guards for that lesson (issue
        #637). A period left with no teaching cell and no guard is dropped: a line with nothing in
        it but a time range adds no information.

        'area_ids' (issue #637, falsy/omitted = "All areas"): the areas (top-level departments,
        see _guard_duty_group_areas()) to narrow the board down to. When set:
        - groups and lines only ever come from the lessons of a group in those areas, a
          reinforcement group included (it follows its main groups' area).
        - A guard shows on whichever line its own period falls in, whatever the guard teaches:
          there is no way to know, and no need to know, which area a guard belongs to (developer
          feedback, 2026-09-07: "está de guardia y eso es lo que manda"). One on a period of
          another area's framework only (its break, say) is left out, rather than folded into
          one of this area's lines that merely spans it.
        - A guard on the selected areas' own break gets a "Patio" line of its own, since no lesson
          runs then (_get_guard_duty_board_break_lines()).
        Checking every area is the same as checking none.

        Every line is marked 'is_break' when its period falls inside some framework's break and no
        group has a class then - the "no class" half keeps it right when another area is
        teaching through that break.

        `day`, when given, is the concrete date the weekday stands for, and is what adds the
        absence information: every cell gains an 'absences' map of which of its own teachers are
        away, each line gains 'guard_absences' for the same question asked of the guard column,
        and 'absences' - the list of classes actually left without a teacher, which is what the
        absences table is built from. Without a date none of that can be resolved at all, so
        every one of those comes back empty and the board is the plain timetable."""
        self.ensure_one()
        if area_ids and set(area_ids) >= set(self._get_guard_duty_board_area_records().ids):
            area_ids = None
        day = fields.Date.to_date(day)
        shift_start, shift_end = SHIFT_HOURS[shift]
        entries = self._get_guard_duty_board_attendance_ids([
            ('dayofweek', '=', weekday), ('hour_from', '>=', shift_start), ('hour_to', '<=', shift_end)])
        teaching_entries = entries.filtered(lambda attendance: attendance.subject_id or attendance.group_ids)
        guard_entries = entries.filtered(lambda attendance: attendance.non_teaching_is_guard)
        intervals = self._get_guard_duty_absence_intervals(day, entries.employee_id, unchecked=True)

        areas = self._guard_duty_group_areas(teaching_entries.group_ids)
        level_ids = None
        if area_ids:
            groups = teaching_entries.group_ids.filtered(lambda group: areas[group.id].id in area_ids)
            teaching_entries = teaching_entries.filtered(lambda attendance: attendance.group_ids & groups)
            # The selected areas' own time frameworks: their breaks, and which periods are theirs.
            level_ids = groups.level_id.ids
            framework_periods = self._get_guard_duty_board_framework_periods(level_ids, weekday, shift_start, shift_end)
            periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in teaching_entries})
            # A guard on another area's period (its break, say) has no row here, and must not fold
            # into one of this area's rows that merely spans it (issue #637) - unless the period is
            # this area's too (both start their day at 8:00).
            own_periods = framework_periods | set(periods)
            other_periods = [
                period for period in self._get_guard_duty_board_framework_periods(None, weekday, shift_start, shift_end)
                if not any(_same_period(period, own) for own in own_periods)]
            guard_entries = guard_entries.filtered(lambda attendance: not any(
                _same_period(period, (attendance.hour_from, attendance.hour_to)) for period in other_periods))
        else:
            groups = teaching_entries.group_ids
            framework_periods = self._get_guard_duty_board_framework_periods(None, weekday, shift_start, shift_end)
            periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in entries})
        # Grouped by area (issue #637): each area's groups share a time framework, so its columns
        # read as one block under a common header.
        groups = groups.sorted(key=lambda group: (not areas[group.id], areas[group.id].name or '', group.name))
        period_members = _merge_absorbed_periods(periods, fixed=framework_periods)
        break_periods = self._get_guard_duty_board_break_periods(level_ids, weekday, shift_start, shift_end)
        management = self._get_board_absence_management(day, groups, shift_start, shift_end)
        regular_guards = entries.filtered(lambda attendance: attendance.non_teaching.is_regular_guard)

        dated_lines = []
        remaining_guards = guard_entries
        by_group = _entries_by_group(teaching_entries)
        no_entries = teaching_entries.browse()
        for hour_from, hour_to in periods:
            if (hour_from, hour_to) not in period_members:
                continue  # absorbed - already folded into its container's row below
            member_periods = period_members[(hour_from, hour_to)]
            cells = []
            covering = []
            for group in groups:
                group_periods = by_group.get(group.id, {})
                cell_entries = no_entries.union(*(group_periods[period] for period in member_periods if period in group_periods))
                # Every co-teacher for this cell, deduped (a plain recordset union already
                # does that) - a co-taught slot has one 'resource.calendar.attendance' row
                # per teacher, all sharing the same group/period, so 'entries' alone would
                # silently drop every name but the first one picked for display.
                cell_teachers = cell_entries.mapped('employee_id')
                cell_absences = self._guard_duty_absence_state(
                    intervals, cell_teachers, hour_from, hour_to)
                arrangements = self._board_cell_arrangements(management, group, cell_teachers, hour_from, hour_to)
                cells.append({
                    'group': group,
                    'entries': cell_entries,
                    'teachers': cell_teachers,
                    'absences': cell_absences,
                    **arrangements,
                })
                # A lesson an arrangement moved elsewhere without telling the families (issue #645)
                # leaves the group without anybody: one more class to cover, like an absence.
                row_absences = {**{teacher.id: 'moved' for teacher in arrangements['freed']}, **cell_absences}
                # One row per absent teacher AND per class of theirs in this period: a teacher
                # splitting the period across two groups leaves two classes uncovered, and each
                # one has to be assigned its own guard.
                first = cell_entries[:1]
                covering += [{
                    'teacher': teacher,
                    'state': row_absences[teacher.id],
                    'group': group,
                    'duty': self.env['ems.non_teaching_type'],
                    'label': group.name,
                    'subject': (cell_entries.filtered(lambda attendance, teacher=teacher: attendance.employee_id == teacher)[:1]
                                or first).subject_id,
                    'room': first.space_id,
                    'covered': self._guard_duty_is_co_taught(cell_entries, teacher, row_absences),
                    'moved_cover': arrangements['freed'].get(teacher, self.env['ems.absence_cover']),
                    **self._board_absence_row_management(management, teacher, group, hour_from, hour_to),
                } for teacher in cell_teachers if teacher.id in row_absences]
            for row in covering:
                row['arrangement_plans'] = self._board_row_arrangement_plans(management, day, row, hour_from, hour_to)
            if area_ids:
                # A guard's own period is no longer necessarily one of 'periods' above (those now
                # only come from teaching_entries) - fold it into whichever row's range genuinely
                # contains it, not just an exact-tuple match.
                guards = remaining_guards.filtered(
                    lambda attendance, hour_from=hour_from, hour_to=hour_to:
                        _period_contains((hour_from, hour_to), (attendance.hour_from, attendance.hour_to)))
            else:
                guards = guard_entries.filtered(
                    lambda attendance, member_periods=member_periods:
                        (attendance.hour_from, attendance.hour_to) in member_periods)
            remaining_guards -= guards
            moved_guards = self._moved_guards(management['covers'], regular_guards, hour_from, hour_to) if management else {}
            if not guards and not any(cell['entries'] for cell in cells):
                continue  # nothing scheduled anywhere in this period - no row worth showing
            # See this method's own docstring for why the "no cell has a real class" half of this
            # check is what keeps it safe under "All areas" (where several, differently-timed
            # break windows coexist) as well as under an area filter.
            is_break = not any(cell['entries'] for cell in cells) and any(
                _period_contains(break_period, (hour_from, hour_to)) for break_period in break_periods)
            # An absent regular guard has no class of their own for anyone to cover, they are simply
            # one fewer person available to cover somebody else's - a subtraction from the guard
            # column, not an addition to the work. A guard duty that is not regular (WC, break...)
            # is a post somebody has to be at, so its absent teacher's duty is one more row to
            # cover (issue #606).
            guard_absences = self._guard_duty_absence_state(
                intervals, guards.mapped('employee_id'), hour_from, hour_to)
            covering += self._board_duty_rows(guards, guard_absences, management, hour_from, hour_to)
            dated_lines.append((hour_from, hour_to, {
                'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
                'hour_from': hour_from,
                'hour_to': hour_to,
                'cells': cells,
                'guards': guards,
                # On guard because an arrangement moved a lesson (issues #678, #709), with why.
                'stayed_guards': self.env['hr.employee'].union(*moved_guards),
                'stayed_labels': {teacher.id: label for teacher, (_piece, label) in moved_guards.items()},
                'guard_absences': guard_absences,
                # Guards with a group through an internal arrangement (issue #605): struck out of
                # the guard column, nobody can ask them to cover anything else then.
                'guard_busy': self._arrangement_busy(management['covers'], hour_from, hour_to) if management else {},
                'absences': covering,
                'is_break': is_break,
            }))

        if area_ids:
            dated_lines += self._get_guard_duty_board_break_lines(
                level_ids, weekday, shift_start, shift_end, groups, remaining_guards, intervals, management)
            dated_lines.sort(key=lambda dated_line: (dated_line[0], dated_line[1]))
        lines = [line for _hour_from, _hour_to, line in dated_lines]
        # Colours for the whole shift, not per line: a guard can cover part of a class on another
        # line than their own guard block (issue #637), and both must share the colour.
        guard_covers = _board_guard_covers(lines)
        guard_colors = self._board_cover_colors(lines, guard_covers)
        # A guard's badge only takes it in the blocks where they cover something (issue #675), with a
        # dotted border where what they cover there is only part of a class (screen and PDF).
        for line in lines:
            line['cover_colors'] = guard_colors
            line['guard_colors'] = {}
            line['partial_guard_ids'] = set()
            for guard_id, covers in guard_covers.items():
                here = [partial for hour_from, hour_to, partial in covers
                        if overlaps(hour_from, hour_to, line['hour_from'], line['hour_to'])]
                if here:
                    line['guard_colors'][guard_id] = guard_colors[guard_id]
                    if any(here):
                        line['partial_guard_ids'].add(guard_id)
        # Who could be sent to each line's classes, and for which part (issue #637): every regular
        # guard of the shift, not only the line's own - one on a partly overlapping block covers
        # part of the class. Computed per line from data already loaded, no query.
        for line in lines:
            line['guard_spans'] = self._guard_spans(
                regular_guards, intervals, management['covers'], line['hour_from'], line['hour_to']) if management else {}
        breaks_by_level = {level: self._get_guard_duty_board_break_periods(level.ids, weekday, shift_start, shift_end)
                           for level in groups.level_id}
        grid = BoardTimeGrid(lines, groups, areas, {group.id: breaks_by_level.get(group.level_id, ()) for group in groups},
                             self._format_report_time)
        return {
            'groups': groups,
            'areas': areas,
            'lines': lines,
            'schedule_grid': grid.schedule(),
            'absence_grid': grid.absences(),
            'actions': self._board_action_sections(
                management, day, management['actions'] + self._arrangement_plan_actions(dated_lines)) if management else [],
        }

    def _board_cell_arrangements(self, management, group, teachers, hour_from, hour_to):
        """How the internal arrangements in effect (issue #605) change one timetable cell, so the
        timetable never reads as the usual one: 'substitutes', who is with the group instead of the
        absent teacher (or, in a swap, the absent teacher taking over the other lesson), 'moved',
        the teachers whose lesson there went elsewhere (with it, or on guard when they could not
        follow it, issue #678), 'freed', `{teacher: cover}` for those moved without telling the
        families (issue #645): nobody is with the group then, and 'joined', the other halves of a
        split group taught together with it then (issue #660)."""
        substitutes, moved, freed = self.env['hr.employee'], self.env['hr.employee'], {}
        joined = self.env['ems.group']
        if management:
            for cover in management['covers'].filtered(lambda cover: cover.cover_type == 'arrangement' and cover.is_effective
                                                       and cover.joined_group_ids and overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to)):
                if cover.group_id == group:
                    joined |= cover.joined_group_ids
                elif group in cover.joined_group_ids:
                    joined |= cover.group_id
            for cover in management['covers'].filtered(
                    lambda cover: cover.cover_type == 'arrangement' and cover.group_id == group and cover.is_effective):
                if overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to):
                    substitutes |= cover.guard_employee_id
                if cover.vacated_hour_to and overlaps(cover.vacated_hour_from, cover.vacated_hour_to, hour_from, hour_to):
                    moved |= (cover.guard_employee_id | cover.stayed_employee_ids) & teachers
                    if cover.arrangement_type == 'swap':
                        substitutes |= cover.absent_employee_id
                    elif not cover.notice_id and cover.guard_employee_id in teachers:
                        freed[cover.guard_employee_id] = cover
        return {'substitutes': substitutes, 'moved': moved, 'freed': freed, 'joined': joined}

    def _board_row_arrangement_plans(self, management, day, row, hour_from, hour_to):
        """The arrangements (issues #605, #645) that resolve one absences-table row: only for a
        class still left without anybody, and only for whoever may organise it - to anybody else
        they are noise."""
        if not management or not row['group'] or not row['can_manage'] or row['covered'] or row['covers'] \
                or row['arrangement'] or row['authorized'] or row['state'] == 'unchecked':
            return []
        if 'arrangement_context' not in management:
            management['arrangement_context'] = self._arrangement_context(day)
        plans = self._get_arrangement_plans(day, row['group'], context=management['arrangement_context'])
        return [plan for plan in plans if self._plan_resolves(plan, row['group'], hour_from, hour_to)]

    def _board_action_sections(self, management, day, actions):
        """`actions`, each with its 'section': the groups it is about together with those sharing
        lessons with them that day (see _linked_groups), so that everything proposed for the same
        groups - their arrangement plans, the timetable change alone, a correction, an arrangement
        waiting for its notice - is shown together, under one heading per set of groups (issue
        #645). A guard no longer needed has a box of its own and no section."""
        sectioned = [action for action in actions if action['type'] != 'obsolete_cover']
        if sectioned:
            if 'arrangement_context' not in management:
                management['arrangement_context'] = self._arrangement_context(day)
            context = management['arrangement_context']
            for action in sectioned:
                action['section'] = action['plan']['groups'] if action['type'] == 'arrangement_plan' \
                    else self._linked_groups(context, action['group']).sorted('name')
        return actions

    @staticmethod
    def _arrangement_plan_actions(dated_lines):
        """The day's detected arrangements as pending actions, one per plan whatever the number of
        rows it resolves: by groups, then in their own order (the best first)."""
        actions = {}
        for _hour_from, _hour_to, line in dated_lines:
            for row in line['absences']:
                for plan in row.get('arrangement_plans', []):
                    actions.setdefault(plan['key'], {
                        'type': 'arrangement_plan', 'plan': plan, 'group': plan['groups'][:1], 'can_manage': True})
        return sorted(actions.values(), key=lambda action: (action['plan']['groups'].mapped('name'), action['plan']['number']))

    def _get_board_absence_management(self, day, groups, shift_start, shift_end):
        """Everything the absences table needs to manage the day's absences, resolved once per
        board load: the guard covers assigned on `day`, each group's timetable-change states (see
        _get_absence_change_states), and the day's pending 'actions' - a timetable change to
        propose or rectify for one of `groups`, or a guard assignment in this shift that is no
        longer needed. None without a day, like every other absence structure of the board."""
        if not day:
            return None
        covers = self._get_day_covers(day)
        shift_covers = covers.filtered(
            lambda cover: cover.hour_from >= shift_start - HOUR_EPSILON and cover.hour_to <= shift_end + HOUR_EPSILON)
        states = self._get_absence_change_states(day, groups | shift_covers.group_id)
        editable = day >= self.env['ems.datetime_utils'].get_local_today()
        managers = {}

        def can_manage(teachers, group):
            # A day already over is read-only for everybody (see _check_board_day_not_past).
            return editable and any(
                managers.setdefault((teacher.id, group.id), self._is_absence_manager(teacher, group))
                for teacher in teachers)

        actions = []
        for group in groups:
            for side, state in states[group.id].items():
                if state['status'] in ('proposal', 'rectification'):
                    actions.append({
                        'type': state['status'],
                        'group': group,
                        'side': side,
                        'target': state['target'],
                        'options': state['options'],
                        'expected': state['expected'],
                        'communicated': state['communicated'],
                        'draft': state['draft'],
                        'draft_change': state['draft_change'],
                        'can_manage': can_manage(state['teachers'], group),
                    })
        for cover in shift_covers:
            if not self._is_cover_still_needed(day, cover):
                actions.append({
                    'type': 'obsolete_cover',
                    'cover': cover,
                    'group': cover.group_id,
                    'can_manage': can_manage(self._cover_original_absent(cover, covers), cover.group_id),
                })
            elif not cover.is_effective:
                # An arrangement waiting for its notice (issue #605): nothing changes until it is sent.
                actions.append({
                    'type': 'pending_arrangement',
                    'cover': cover,
                    'group': cover.group_id,
                    'can_manage': can_manage(self._cover_original_absent(cover, covers), cover.group_id),
                })
        return {'covers': covers, 'states': states, 'actions': actions, 'can_manage': can_manage}

    def _board_duty_rows(self, guards, guard_absences, management, hour_from, hour_to):
        """Absences-table rows for the guard duties that are not regular (WC, break...) left
        without their teacher in one board period (issue #606): one per absent guard, keyed by
        the duty instead of a group, with no subject or room and nothing a timetable change could
        make unnecessary - only a regular guard sent to it covers it."""
        rows = []
        for attendance in guards.filtered(
                lambda attendance: not attendance.non_teaching.is_regular_guard
                and attendance.employee_id.id in guard_absences):
            teacher, duty = attendance.employee_id, attendance.non_teaching
            if any(row['teacher'] == teacher and row['duty'] == duty for row in rows):
                continue
            rows.append({
                'teacher': teacher,
                'state': guard_absences[teacher.id],
                'group': self.env['ems.group'],
                'duty': duty,
                'label': duty.name,
                'subject': self.env['ems.subject'],
                'room': self.env['ems.space'],
                'covered': False,
                'moved_cover': self.env['ems.absence_cover'],
                'arrangement_plans': [],
                **self._board_absence_row_management(management, teacher, self.env['ems.group'], hour_from, hour_to, duty),
            })
        return rows

    def _is_cover_still_needed(self, day, cover):
        """Whether the class - or the guard duty (issue #606) - `cover` resolves still needs it
        and, for an internal arrangement, whether the teacher it relies on is still free to be
        with the group (issue #605)."""
        if cover.duty_id:
            return bool(self._get_needed_duty_entry(
                day, cover.duty_id, cover.absent_employee_id, cover.hour_from, cover.hour_to))
        if not self._get_needed_absence_block(day, cover.group_id, cover.absent_employee_id, cover.hour_from, cover.hour_to):
            return False
        if cover.cover_type != 'arrangement':
            return True
        teachers = cover.guard_employee_id | cover.absent_employee_id
        intervals = self._get_guard_duty_absence_intervals(day, teachers)
        if cover.guard_employee_id and self._guard_duty_absence_state(
                intervals, cover.guard_employee_id, cover.hour_from, cover.hour_to):
            return False
        # A shared lesson moves for all its groups or for none (issue #645): one of them taken back
        # leaves the others wrong.
        if cover.arrangement_type == 'move':
            lesson = self._get_guard_duty_board_attendance_ids([
                ('dayofweek', '=', str(day.weekday())), ('calendar_id.employee_id', '=', cover.guard_employee_id.id),
                ('hour_from', '<', cover.vacated_hour_to), ('hour_to', '>', cover.vacated_hour_from)])
            if lesson.group_ids - cover._with_siblings().group_id:
                return False
        # In a swap, the absent teacher must still be in for the lesson they take over.
        return not (cover.arrangement_type == 'swap' and self._guard_duty_absence_state(
            intervals, cover.absent_employee_id, cover.vacated_hour_from, cover.vacated_hour_to))

    def _board_absence_row_management(self, management, teacher, group, hour_from, hour_to, duty=None):
        """The management part of one absences-table row - a class of `group`, or the teacher's
        guard duty `duty` (issue #606): the guard 'covers' assigned to it (see below), the timetable change already communicated for its period ('authorized', which
        makes a guard unnecessary and strikes the row out; a longer break, which still needs one,
        comes as 'break_change' instead, issue #679) or one the absences allow but nobody
        has communicated yet ('proposed') - neither of which ever applies to a guard duty - and
        whether the current user may act on it ('can_manage'). An internal arrangement (issue
        #605), which only a class can have, comes as 'arrangement' instead of 'cover', in effect
        or still waiting for its notice; 'arrangement_change' is the timetable change the families
        were told because of it (the lesson it moved here is one the group no longer has: it
        comes in later or leaves earlier), shown next to it so the row says both (issue #623).
        'covers' are the guard covers of the row - several when each covers part of the class
        (issue #637) - and 'missing' the parts none covers yet (empty without any cover).
        'change_side' is the side of the group's day whose communicated change strikes the row out
        (or, a longer break, tags it: 'break_change'), while it can still be changed (issue #659,
        see get_change_proposal_options), else False."""
        duty = duty or self.env['ems.non_teaching_type']
        no_cover = self.env['ems.absence_cover']
        if not management:
            return {'covers': no_cover, 'missing': [], 'arrangement': no_cover, 'arrangement_change': None,
                    'authorized': None, 'break_change': None, 'change_side': False, 'proposed': None, 'can_manage': False}
        resolved = management['covers'].filtered(
            lambda cover: cover.absent_employee_id == teacher and cover.group_id == group and cover.duty_id == duty
                and overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to))
        # Several guards can each cover part of the class (issue #637); it is only resolved once
        # their parts add up to all of it - 'missing' is what is still left.
        covers = resolved.filtered(lambda cover: cover.cover_type == 'guard').sorted('hour_from')
        arrangement = (resolved - covers)[:1]
        missing = _uncovered_periods((hour_from, hour_to), [(cover.hour_from, cover.hour_to) for cover in covers]) if covers else []
        moved = arrangement.filtered(lambda cover: cover.arrangement_type == 'move' and cover.is_effective)
        authorized = proposed = arrangement_change = break_change = None
        change_side = False
        for side, state in management['states'].get(group.id, {}).items() if group else ():
            if moved and self._change_window_contains(state['communicated'], moved.vacated_hour_from, moved.vacated_hour_to):
                arrangement_change = state['communicated']
            if self._change_frees_guard(state['communicated'], hour_from, hour_to):
                authorized = state['communicated']
                change_side = side if state['change_options'] else False
            elif self._change_window_contains(state['communicated'], hour_from, hour_to):
                break_change = state['communicated']
                change_side = side if state['change_options'] else False
            elif state['status'] == 'proposal' and self._change_window_contains(state['expected'], hour_from, hour_to):
                proposed = state['expected']
        return {
            'covers': covers,
            'missing': missing,
            'arrangement': arrangement,
            'arrangement_change': arrangement_change,
            'authorized': authorized,
            'break_change': break_change,
            'change_side': change_side,
            'proposed': proposed,
            'can_manage': management['can_manage'](
                self._original_absent(management['covers'], teacher, group, hour_from, hour_to), group),
        }

    @staticmethod
    def _board_cover_colors(lines, guard_covers):
        """`{guard employee id: colour index}` for the shift (issue #637). The colour belongs to the
        class covered: every guard covering one class shares its colour - and a guard covering
        several classes joins them under one colour, since their badge can only have one. Two such
        groups that overlap in time (their classes, or the guard blocks their badges show in) never
        share a colour; one that overlaps nobody may reuse one, so the palette only runs short with
        more groups at the same time than colours."""
        parent = {}

        def root(node):
            while parent.setdefault(node, node) != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        periods = defaultdict(list)
        for line_index, line in enumerate(lines):
            for row_index, row in enumerate(line['absences']):
                if not row['covers']:
                    continue
                node = ('row', line_index, row_index)
                for guard in row['covers'].guard_employee_id:
                    parent[root(('guard', guard.id))] = root(node)
                periods[node].append((line['hour_from'], line['hour_to']))
        # A guard's own block counts too where their badge shows the colour (where they cover
        # something, issue #675): next to everybody on guard then. `guard_covers`: see
        # _board_guard_covers().
        for line in lines:
            for guard in line['guards'].employee_id:
                if any(overlaps(hour_from, hour_to, line['hour_from'], line['hour_to'])
                       for hour_from, hour_to, _partial in guard_covers.get(guard.id, ())):
                    periods[('guard', guard.id)].append((line['hour_from'], line['hour_to']))
        groups = defaultdict(list)
        for node, node_periods in periods.items():
            groups[root(node)] += node_periods
        colors = {}
        for group, group_periods in sorted(groups.items(), key=lambda item: min(item[1])):
            taken = {colors[other] for other, other_periods in groups.items() if other in colors and any(
                overlaps(start, stop, other_start, other_stop)
                for start, stop in group_periods for other_start, other_stop in other_periods)}
            colors[group] = next(color for color in range(len(groups) + 1) if color not in taken) % COVER_COLOR_COUNT
        return {node[1]: colors[root(node)] for node in list(parent) if node[0] == 'guard'}

    def _guard_duty_group_areas(self, groups):
        """{group id: its area} - the top-level department above the department that manages
        the group's study (or its main groups' studies, for a reinforcement group), empty when none
        does. An area's groups share a time framework (issue #637)."""
        return {group.id: group.sudo().managing_department_ids[:1]._top_level_department() for group in groups}

    def _get_guard_duty_board_break_periods(self, level_ids, weekday, shift_start, shift_end):
        return self._get_guard_duty_board_framework_periods(level_ids, weekday, shift_start, shift_end, breaks_only=True)

    def _get_guard_duty_board_framework_periods(self, level_ids, weekday, shift_start, shift_end, breaks_only=False):
        """Distinct (hour_from, hour_to) periods of the schedule frameworks of 'level_ids' (every
        framework, centre-wide, when falsy) in this weekday and shift: their lessons and breaks,
        or only their breaks with 'breaks_only'."""
        domain = [('is_framework', '=', True)]
        if level_ids:
            domain.append(('level_id', 'in', level_ids))
        frameworks = self.env['resource.calendar'].search(domain)
        if not frameworks:
            return set()
        return {
            (attendance.hour_from, attendance.hour_to)
            for attendance in self.env['resource.calendar.attendance'].search([
                ('calendar_id', 'in', frameworks.ids),
                ('dayofweek', '=', weekday),
                ('hour_from', '>=', shift_start), ('hour_to', '<=', shift_end),
            ] + ([('non_teaching_is_break', '=', True)] if breaks_only else []))
        }

    def _get_guard_duty_board_break_lines(self, level_ids, weekday, shift_start, shift_end, groups, unmatched_guards, intervals,
                                          management=None):
        """Once an area filter is active, its levels' own break ("Patio") period has no real
        teaching entry of its own to build a row from (a teacher's own calendar spans one
        continuous block across it - see hr.employee._get_derived_break_entries' own docstring),
        so a guard duty scheduled specifically for a break would otherwise simply disappear once
        'get_guard_duty_board_lines' restricts its rows to the filtered level's teaching periods
        only. Any leftover 'unmatched_guards' entry (any guard not already folded into a row
        above - see the caller, which no longer derives a guard's own level at all) that falls
        inside one of that level's own framework(s)' break periods gets a dedicated row instead -
        marked 'is_break' for the client to label distinctly. A
        break period with no guard inside it renders nothing, same "nothing to show" rule every
        other row already follows. Only ever called once an area filter is active (see the
        caller) - under "All areas" a break-time guard already gets its 'is_break' flag directly
        on its normal row instead, via the main loop's own use of
        '_get_guard_duty_board_break_periods' (no synthetic row needed there, since "All areas"
        never restricts which periods get a row in the first place).

        'intervals' is forwarded straight from the caller so a guard's own absence still shows up
        on their dedicated break row exactly like it would on any other row - see
        get_guard_duty_board_lines()'s own 'guard_absences' - and an absent break guard's duty is
        a row to cover there too (issue #606), with 'management' forwarded the same way."""
        break_periods = sorted(self._get_guard_duty_board_break_periods(level_ids, weekday, shift_start, shift_end))
        if not break_periods:
            return []
        empty_entries = self.env['resource.calendar.attendance']
        dated_lines = []
        for hour_from, hour_to in break_periods:
            guards = unmatched_guards.filtered(
                lambda attendance, hour_from=hour_from, hour_to=hour_to:
                    _period_contains((hour_from, hour_to), (attendance.hour_from, attendance.hour_to)))
            if not guards:
                continue  # nothing to show for this break slot
            unmatched_guards -= guards
            guard_absences = self._guard_duty_absence_state(intervals, guards.mapped('employee_id'), hour_from, hour_to)
            covering = self._board_duty_rows(guards, guard_absences, management, hour_from, hour_to)
            dated_lines.append((hour_from, hour_to, {
                'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
                'hour_from': hour_from,
                'hour_to': hour_to,
                'cells': [{
                    'group': group, 'entries': empty_entries, 'teachers': empty_entries.employee_id, 'absences': {},
                } for group in groups],
                'guards': guards,
                'guard_absences': guard_absences,
                'guard_busy': {},
                'absences': covering,
                'is_break': True,
            }))
        return dated_lines

    @api.model
    def get_guard_duty_board_data(self, weekday, shift, area_ids=None, day=None):
        """JSON-safe wrapper around get_guard_duty_board_lines(), for the guard duty board client
        action's own RPC call (static/src/js/backend/guard_duty_board.js). @api.model: resolves
        "the current course" itself (env.company.current_course_id), so the JS side never needs
        to know or pass a specific ems.course id — matches how the aggregation itself is scoped
        (see _get_guard_duty_board_attendance_ids' own NOTE: not actually course-filtered).
        'area_ids' (issue #637) and 'day' are forwarded as-is - see get_guard_duty_board_lines()'s
        own docstring. Every teacher is reported as {'name', 'absence', 'is_wc'} rather than a bare
        name, so both of the screen's tabs read absences (and, for the guard column, the WC flag)
        the same way, off the same payload, instead of the client having to match names back
        against a separate list."""
        course = self.env.company.get_current_course_or_raise()
        data = course.get_guard_duty_board_lines(weekday, shift, area_ids=area_ids, day=day)
        groups = [{'id': group.id, 'name': group.name, 'area_id': data['areas'][group.id].id} for group in data['groups']]
        cover_counts = course._guard_cover_counts(self.env['hr.employee'].union(
            *(line['guards'].employee_id for line in data['lines']),
            *(self.env['hr.employee'].union(*line['guard_spans']) for line in data['lines'])))
        # A teacher on guard duty may take a free class themselves (issue #601) - from today on,
        # like every other board action (see _check_board_day_not_past).
        editable = bool(day) and fields.Date.to_date(day) >= self.env['ems.datetime_utils'].get_local_today()
        me = self.env.user.employee_id
        # "The teacher is in the classroom" (issue #692): only on today's classes in progress.
        today = bool(day) and fields.Date.to_date(day) == self.env['ems.datetime_utils'].get_local_today()
        now = course._board_day_hour(fields.Date.to_date(day)) if today else None
        # Every name on the board read in one batch: reading them cell by cell fetched each
        # employee on its own, every fetch paying hr.employee's per-read field access check.
        self.env['hr.employee'].union(*(
            cell['teachers'] for line in data['lines'] for cell in line['cells']
        ), *(line['guards'].employee_id | line.get('stayed_guards', line['guards'].employee_id) for line in data['lines'])).mapped('display_name')
        lines = []
        for line in data['lines']:
            cells = []
            for cell in line['cells']:
                first = cell['entries'][:1]
                # 'acronym' (e.g. "MP 0440"), not 'display_name' (which also spells out the full
                # subject name) - the cell is tight on space, the full name is one click away on
                # the teacher's own schedule.
                cells.append({
                    'group_id': cell['group'].id,
                    'subject': first.subject_id.acronym if first else False,
                    'teachers': self._guard_duty_teacher_data(cell['teachers'], cell['absences'], moved=cell.get('moved', ())),
                    'substitutes': [teacher.name for teacher in cell.get('substitutes', [])],
                    'joined': cell['joined'].mapped('name') if cell.get('joined') else [],
                    'room': first.space_id.display_name if first and first.space_id else False,
                })
            wc_employee_ids = set(line['guards'].filtered(
                lambda attendance: attendance.non_teaching.code == WC_GUARD_CODE).mapped('employee_id').ids)
            guards = self._guard_duty_teacher_data(
                line['guards'].mapped('employee_id'), line['guard_absences'], wc_employee_ids)
            stayed = self._guard_duty_teacher_data(
                line.get('stayed_guards', line['guards'].employee_id) - line['guards'].employee_id, {})
            for guard in stayed:
                guard['stayed'] = line['stayed_labels'][guard['id']]
            guards += stayed
            for guard in guards:
                guard['color'] = line['guard_colors'].get(guard['id'], False)
                guard['partial'] = guard['id'] in line['partial_guard_ids']
                guard['cover_count'] = cover_counts.get(guard['id'], 0)
                busy = line['guard_busy'].get(guard['id'])
                guard['busy'] = _("With %(group)s: %(arrangement)s", group=busy.group_id.name,
                                  arrangement=busy._arrangement_label()) if busy else False
            # Who can be sent to one of this line's classes, and for which part of it (issue #637):
            # those covering all of it first, then the partial ones by time - see _guard_spans().
            spans = sorted(line['guard_spans'].items(), key=lambda item: (
                item[1] != (line['hour_from'], line['hour_to']), item[1], item[0].name))
            my_span = line['guard_spans'].get(me) if editable else None
            in_progress = course._in_progress(now, line['hour_from'], line['hour_to'])
            on_guard_here = in_progress and me in line['guards'].employee_id
            lines.append({
                'time_label': line['time_label'],
                'hour_from': line['hour_from'],
                'hour_to': line['hour_to'],
                'cells': cells,
                'guards': guards,
                'guard_candidates': [{
                    'id': guard.id, 'name': guard.name, 'cover_count': cover_counts.get(guard.id, 0),
                    'label': self._period_label(*span),
                    'partial': span != (line['hour_from'], line['hour_to']),
                } for guard, span in spans],
                'absences': [{
                    'teacher': row['teacher'].display_name,
                    'teacher_id': row['teacher'].id,
                    'state': row['state'],
                    'group': row['label'],
                    'group_id': row['group'].id,
                    'duty_id': row['duty'].id,
                    'subject': row['subject'].acronym if row['subject'] else False,
                    'room': row['room'].display_name if row['room'] else False,
                    'covered': row['covered'],
                    'covers': [{
                        'id': cover.id,
                        'guard_id': cover.guard_employee_id.id,
                        'guard': cover.guard_employee_id.name,
                        'message': cover.message or '',
                        'color': line['cover_colors'].get(cover.guard_employee_id.id, 0),
                        'label': self._period_label(cover.hour_from, cover.hour_to),
                        'partial': not _period_contains((cover.hour_from, cover.hour_to), (line['hour_from'], line['hour_to'])),
                    } for cover in row['covers']],
                    'missing': [self._missing_label(period) for period in row['missing']],
                    'arrangement': {
                        'id': row['arrangement'].id,
                        'type': row['arrangement'].arrangement_type,
                        'teacher_id': row['arrangement'].guard_employee_id.id,
                        'teacher': row['arrangement'].guard_employee_id.name or '',
                        'note': row['arrangement'].message or '',
                        'label': row['arrangement']._arrangement_label(),
                        'pending': not row['arrangement'].is_effective,
                        'notice_id': row['arrangement'].notice_id.id,
                        'change': self._absence_change_label(row['arrangement_change']),
                    } if row['arrangement'] else False,
                    'arrangement_plans': [self._arrangement_plan_data(plan) for plan in row['arrangement_plans']],
                    # The lesson a move left free (issue #645): where it went.
                    'moved': self._moved_label(row['moved_cover']),
                    'authorized': self._absence_change_label(row['authorized']),
                    'break_change': self._absence_change_label(row['break_change']),
                    'change_side': editable and row['change_side'],
                    'proposed': self._absence_change_label(row['proposed'], proposed=True),
                    'can_manage': row['can_manage'],
                    # A guard takes their own part of a class (issue #637) while nobody covers it yet.
                    'can_self_assign': bool(my_span) and not (row['arrangement'] or row['covered'] or row['authorized'])
                        and not any(overlaps(cover.hour_from, cover.hour_to, *my_span) for cover in row['covers']),
                    'self_label': self._period_label(*my_span) if my_span else False,
                    'self_cover_id': editable and row['covers'].filtered(
                        lambda cover: cover.is_self_assigned and cover.assigned_by_id == self.env.user)[:1].id,
                    'can_mark_present': in_progress and row['state'] == 'unchecked'
                        and (row['can_manage'] or on_guard_here),
                } for row in line['absences']],
                'is_break': line.get('is_break', False),
            })
        return {'groups': groups, 'lines': lines,
                'schedule_grid': data['schedule_grid'], 'absence_grid': data['absence_grid'],
                # Only whoever may act on them sees the day's pending decisions: to everybody else
                # they are noise, and the struck-out rows already say what was decided.
                'actions': [self._board_action_data(action) for action in data['actions'] if action['can_manage']],
                # Whether anybody can still act on this day (from today on): the board then explains
                # every line still to be covered, also to whoever cannot cover it.
                'editable': editable}

    def _arrangement_plan_data(self, plan):
        """JSON-safe version of a detected arrangement plan (see _get_arrangement_plans): its
        number among its groups' proposals, and one sentence per step, with the entry/exit changes
        it brings, the steps it needs and what the server needs to apply it (`payload`)."""
        steps = []
        for step in plan['steps']:
            groups = format_list(self.env, step['groups'].mapped('name'))
            if step['kind'] in ('notice', 'correction'):
                values = {'groups': groups, 'change': self._absence_change_label(step['change'])}
                # A longer break is only the students' business (issue #679).
                if self.env['ems.notice']._absence_change_students_only([step['change']]):
                    label = (_("Notice to the students of %(groups)s: %(change)s.", **values) if step['kind'] == 'notice'
                             else _("Correction to the students of %(groups)s: %(change)s.", **values))
                else:
                    label = (_("Notice to the families of %(groups)s: %(change)s.", **values) if step['kind'] == 'notice'
                             else _("Correction to the families of %(groups)s: %(change)s.", **values))
                payload = {'kind': step['kind'], 'group_ids': step['groups'].ids, 'change': list(step['change'])}
                details = []
            else:
                values = {'teacher': format_list(self.env, step['teacher'].mapped('name')),
                          'absent': format_list(self.env, step['absent'].mapped('name')), 'groups': groups,
                          'lesson': self._format_report_time(step['lesson'][0]),
                          'target': self._format_report_time(step['target'][0])}
                values['joined'] = format_list(self.env, step['joined'].mapped('name'))
                values['teachers'] = format_list(self.env, (step['teacher'] | step['absent']).mapped('name'))
                label = self._arrangement_step_label(step['kind'], values)
                details = self._arrangement_step_details(step, values)
                payload = {'kind': step['kind'], 'teacher_ids': step['teacher'].ids, 'absent_ids': step['absent'].ids,
                           'stay_ids': step['stays'].ids, 'lesson': list(step['lesson']), 'target': list(step['target']),
                           'group_ids': step['groups'].ids, 'joined_group_ids': step['joined'].ids}
            steps.append({
                'kind': step['kind'],
                'label': label,
                # What kind of move it is (issue #709), a line each under the step.
                'details': details,
                'depends': step['depends'],
                'schedule_changes': self._schedule_shift_labels(step.get('shifts', [])),
                # Whoever's entry or exit it changes, to ask before applying it (issue #709).
                'schedule_teachers': sorted({teacher.name for teacher, *_change in step.get('shifts', [])}),
                'warnings': [self._stay_warning(teacher, reason, step['lesson'][0])
                             for teacher, reason in step.get('stay_reasons', {}).items()],
                'payload': payload,
            })
        return {
            'key': plan['key'],
            'title': _("Proposal %s:", plan['number']),
            'groups': format_list(self.env, plan['groups'].mapped('name')),
            'steps': steps,
        }

    def _arrangement_step_label(self, kind, values):
        """One moved lesson, join or swap in one short line (issue #709): who, which lesson goes
        where, and for which groups; what kind of move it is goes under it (see
        _arrangement_step_details). `values` names the teachers who move it ('teacher', several when
        co-teachers move together, issue #678), the 'absent' ones in a swap, the 'groups' and the
        'lesson' and 'target' times."""
        if kind == 'swap':
            return _("%(teachers)s swap their %(target)s and %(lesson)s lessons (%(groups)s)",
                     teachers=values['teachers'], target=values['target'], lesson=values['lesson'], groups=values['groups'])
        return _("%(teacher)s: %(lesson)s lesson → %(target)s (%(groups)s)", **values)

    def _stay_warning(self, teacher, reason, hour):
        """The warning of a co-teacher who cannot follow their lesson (issue #678): why, and that
        they are on guard at its usual time instead."""
        reasons = {
            'away': _("away then"),
            'busy': _("busy then"),
            'apart': _("not with the other half then"),
            'day': _("their working day would get longer"),
        }
        return _("%(teacher)s cannot follow the lesson (%(reason)s): on guard at %(time)s instead.",
                 teacher=teacher.name, reason=reasons[reason], time=self._format_report_time(hour))

    def _moved_label(self, cover):
        """The tag of a lesson an arrangement moved elsewhere without telling the families
        (issue #645): the group has nobody then."""
        return _("Lesson moved to %s", self._format_report_time(cover.hour_from)) if cover else False

    def _cover_schedule_changes(self, cover):
        """The entry/exit sentences of an arrangement already applied, for its notifications: in a
        moved lesson, the teacher's whole day with every lesson of theirs moved that day (issue
        #645: a plan can move several)."""
        if cover.arrangement_type not in ('swap', 'move'):
            return []
        context = self._arrangement_context(cover.date)
        if cover.arrangement_type == 'swap':
            shifts = self._arrangement_shifts(
                context, 'swap', cover.absent_employee_id, cover.guard_employee_id, cover.hour_from, cover.hour_to,
                (cover.vacated_hour_from, cover.vacated_hour_to))
        else:
            moves = context['covers'].filtered(
                lambda other: other.arrangement_type == 'move' and other.guard_employee_id == cover.guard_employee_id)
            periods = {((other.vacated_hour_from, other.vacated_hour_to), (other.hour_from, other.hour_to)) for other in moves | cover}
            shift = self._schedule_shift(context, cover.guard_employee_id, [vacated for vacated, _target in periods],
                                         [target for _vacated, target in periods])
            shifts = [(cover.guard_employee_id, *change) for change in shift or ()]
        return self._schedule_shift_labels(shifts or [])

    def _schedule_shift_labels(self, shifts):
        """One sentence per entry or exit time an arrangement changes (see _arrangement_shifts)."""
        labels = []
        for teacher, kind, old, new in shifts:
            values = {'teacher': teacher.name, 'new': self._format_report_time(new), 'old': self._format_report_time(old)}
            if kind == 'entry':
                labels.append(_("%(teacher)s comes in at %(new)s instead of %(old)s.", **values))
            else:
                labels.append(_("%(teacher)s leaves at %(new)s instead of %(old)s.", **values))
        return labels

    def _absence_change_label(self, change, proposed=False):
        """Short wording of a timetable change, for a row tag or an action: what the families
        were told, or (`proposed`) what the absences would allow them to be told."""
        if not change:
            return False
        change_type = change[0]
        hour = self._format_report_time(change[1])
        if change_type == 'long_break':
            span = {'start': hour, 'end': self._format_report_time(change[2])}
            return (_("Could have a break from %(start)s to %(end)s", **span) if proposed
                    else _("Break from %(start)s to %(end)s", **span))
        if change_type == 'normal_break':
            return _("Usual break")
        if proposed:
            labels = {
                'late_entry': _("Could start at %s", hour),
                'early_leave': _("Could leave at %s", hour),
                'no_classes': _("Could have no classes"),
            }
        else:
            labels = {
                'late_entry': _("Starts at %s", hour),
                'early_leave': _("Leaves at %s", hour),
                'no_classes': _("No classes"),
            }
        return labels.get(change_type, _("Usual timetable"))

    def _absence_changes_label(self, changes):
        """Every change a notice tells (see _absence_change_label), in one line."""
        return format_list(self.env, [self._absence_change_label(change) for change in changes]) or False

    def _board_action_data(self, action):
        """JSON-safe version of one of the day's pending actions (see
        _get_board_absence_management), with the sentence the absences table shows for it."""
        data = {'type': action['type'], 'group_id': action['group'].id, 'can_manage': action['can_manage']}
        if action.get('section'):
            data.update(section_key='-'.join(map(str, sorted(action['section'].ids))),
                        section_title=format_list(self.env, action['section'].mapped('name')))
        values = {'group': action['cover'].display_name if action.get('cover') else action['group'].name}
        if action['type'] == 'arrangement_plan':
            data.update(plan=self._arrangement_plan_data(action['plan']))
            return data
        if action['type'] in ('obsolete_cover', 'pending_arrangement'):
            cover = action['cover']
            values.update(guard=cover.guard_employee_id.name, time=cover._time_label(), teacher=cover.absent_employee_id.name)
            data.update(cover_id=cover.id, cover_type=cover.cover_type, notice_id=cover.notice_id.id)
            if action['type'] == 'pending_arrangement':
                # Shown with the proposals, as a draft to open and send: same box, same button.
                data.update(draft_id=cover.notice_id.id, options=[], draft_label=cover.notice_id.absence_change_label)
                data['label'] = _("%(group)s at %(time)s (%(teacher)s): the arrangement with %(guard)s only counts "
                                  "once its notice to the families is sent.", **values)
            elif cover.cover_type == 'arrangement':
                data['label'] = _("The arrangement with %(guard)s for %(group)s at %(time)s (%(teacher)s) no longer "
                                  "applies.", **values)
            else:
                data['label'] = _("%(guard)s no longer needs to cover %(group)s at %(time)s (%(teacher)s).", **values)
            return data
        # Only the students hear about a break (issue #679).
        students_only = BoardBreakSide.is_break(action['side'])
        if action['type'] == 'proposal':
            values['change'] = self._absence_change_label(action['expected'], proposed=True)
            label = _("%(group)s: %(change)s.", **values)
        else:
            # Nothing allowed any more: the usual timetable, always the last option then.
            values['change'] = self._absence_change_label(action['expected'] or action['options'][-1])
            values['told'] = self._absence_change_label(action['communicated'])
            if students_only:
                label = _("%(group)s: the students were told \"%(told)s\", which no longer matches the absences "
                          "(now: %(change)s).", **values)
            else:
                label = _("%(group)s: the families were told \"%(told)s\", which no longer matches the absences "
                          "(now: %(change)s).", **values)
        # Every change that can be communicated, from the smallest to the largest: the planner may
        # tell the families about part of the empty lessons and send a guard to the rest.
        options = [self._change_option_data(change) for change in action['options']]
        draft = action['draft']
        data.update(label=label, options=options, default=action['options'].index(action['target']), students_only=students_only,
                    draft_id=draft.id or False, draft_label=self._absence_change_label(action['draft_change']))
        return data

    def _period_label(self, hour_from, hour_to):
        return f"{self._format_report_time(hour_from)}-{self._format_report_time(hour_to)}"

    def _missing_label(self, period):
        """The tag of a part of a class no guard covers yet (issue #637), on screen and on paper."""
        return _("Missing %s", self._period_label(*period))

    @staticmethod
    def _guard_duty_teacher_data(teachers, absences, wc_employee_ids=(), moved=()):
        """Teachers as `[{'name', 'absence', 'is_wc'}]` - 'absence' being False, 'approved' or
        'pending'; 'is_wc' flags a 'Guard (WC)' duty specifically (developer request, 2026-09-11)
        - the one guard subtype that, unlike 'Guard (Break)' (always patio time, already covered
        by 'is_break' on the line itself), can fall at any time of day, so it's worth calling out
        next to the teacher's own name. Always False for a teaching cell's own teachers, which
        never pass 'wc_employee_ids' - only the guard column cares about this distinction."""
        return [{'id': teacher.id, 'name': teacher.display_name, 'absence': absences.get(teacher.id, False),
                 'is_wc': teacher.id in wc_employee_ids, 'moved': teacher in moved}
                for teacher in teachers]

    @api.model
    def _get_guard_duty_board_area_records(self):
        """The areas the board can be narrowed down to (issue #637): every top-level department
        that manages some study, itself or through one of its departments - ASP manages none."""
        managing = self.env['ems.study'].sudo().search([('managing_department_id', '!=', False)]).managing_department_id
        return self.env['hr.department'].sudo().union(*(department._top_level_department() for department in managing)).sorted('name')

    @api.model
    def get_guard_duty_board_areas(self):
        """Id/name of every area, for the board's own area filter."""
        return [{'id': area.id, 'name': area.name} for area in self._get_guard_duty_board_area_records()]

    @api.model
    def get_current_course_data(self):
        """Small helper for the guard duty board's client action: the page has no bound record of
        its own to read 'the current course' from (see the class docstring above for why), so it
        asks for it explicitly instead — used both to label the page and to supply the PDF
        button's own 'active_ids'."""
        course = self.env.company.get_current_course_or_raise()
        return {'id': course.id, 'name': course.name}
