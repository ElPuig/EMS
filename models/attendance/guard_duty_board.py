# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..shared.schedule_report_mixin import HOUR_EPSILON
from .absence_coverage import (
    BREAK_CHANGES, CHANGE_SIDES, COMMUNICATED_NOTICE_STATES, NORMAL_CHANGE, WC_GUARD_CODE, overlaps,
)

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
    filter's guard/break folding (issue #390) can reuse it against a period that isn't
    necessarily a member of the same 'periods' list (see 'get_guard_duty_board_lines' docstring).
    Uses HOUR_EPSILON for the same float-noise reason as '_merge_absorbed_periods'."""
    return container[0] <= period[0] + HOUR_EPSILON and container[1] >= period[1] - HOUR_EPSILON


def _merge_absorbed_periods(periods):
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
    still differ by a hair's-width float remainder depending on how each was computed."""
    containers = {}
    for period in periods:
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

    def _get_guard_duty_board_attendance_ids(self):
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
        generic 8-12 block contains/absorbs a real, narrower test period into itself)."""
        return self.env['resource.calendar.attendance'].search([
            ('calendar_id.is_framework', '=', False),
            ('calendar_id.active', '=', True),
            ('calendar_id.employee_id', '!=', False),
            ('dayofweek', 'in', WEEKDAYS),
        ])

    def _get_guard_duty_absence_intervals(self, day, employees):
        """`{employee.id: [(hour_from, hour_to, state)]}` - the absences covering `day`.

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
        return intervals

    @staticmethod
    def _guard_duty_absence_state(intervals, employees, hour_from, hour_to):
        """`{employee.id: 'approved'|'pending'}` for those of `employees` absent in the period.

        An approved absence outranks a pending one when the same teacher has both overlapping
        the same period: the period is going to need covering either way, so reporting it as
        merely "requested" would understate it.
        """
        states = {}
        for employee in employees:
            overlapping = {state for start, stop, state in intervals.get(employee.id, ())
                           if start < hour_to and stop > hour_from}
            if overlapping:
                states[employee.id] = 'approved' if 'approved' in overlapping else 'pending'
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

    def _is_absence_manager(self, employee):
        """Whether the current user organises `employee`'s absences: whoever is above them in the
        chain of command (their Seminar Chief or Department Chief, then up through the Head of
        Studies to the Director), never every holder of those roles centre-wide, and never the
        absent teacher themselves. Same chain 'tutor_scope_user_ids' already resolves for
        tutor-scoped rights, minus the employee's own user. The administrator always can."""
        user = self.env.user
        if self.env.su or user.has_group('base.group_system') or user.has_group('ems.group_academic_admin'):
            # The administrator sits above the whole hierarchy, Direction included, although they
            # are not a teacher and so appear nowhere in it.
            return True
        employee = employee.sudo()
        return self.env.user in employee.tutor_scope_user_ids - employee.user_id

    def _check_absence_manager(self, employee):
        if not self._is_absence_manager(employee):
            raise AccessError(_(
                "Only the department chief of %s, or someone above them, can manage their absences.", employee.name))

    def _check_board_day_not_past(self, day):
        if day < self.env['ems.datetime_utils'].get_local_today():
            raise UserError(_("This day is already over."))

    def _get_group_day_blocks(self, day, groups):
        """`{group.id: [block, ...]}`: each group's own lessons on `day`, in chronological order,
        one block per period (a period absorbed by a longer one folds into it, same as the board's
        own rows). A block carries its attendance 'entries', its 'teachers', which of them are away
        ('absences'), the guard 'covers' already assigned to it, and 'empty' - true when every
        teacher of the block is away and nobody was sent to cover it, i.e. the group's students
        have nobody with them. The whole day, not one shift: a group starts its day at its first
        lesson and ends it at its last, whichever shift they fall in."""
        weekday = str(day.weekday())
        entries = self._get_guard_duty_board_attendance_ids().filtered(
            lambda attendance: attendance.dayofweek == weekday and attendance.group_ids & groups)
        intervals = self._get_guard_duty_absence_intervals(day, entries.employee_id)
        covers = self.env['ems.absence_cover'].sudo().search([
            ('date', '=', day), ('state', '=', 'assigned'), ('group_id', 'in', groups.ids)])
        blocks_by_group = {}
        for group in groups:
            group_entries = entries.filtered(lambda attendance, group=group: group in attendance.group_ids)
            members = _merge_absorbed_periods(sorted({
                (attendance.hour_from, attendance.hour_to) for attendance in group_entries}))
            blocks = []
            for hour_from, hour_to in sorted(members):
                block_entries = group_entries.filtered(
                    lambda attendance, periods=members[(hour_from, hour_to)]:
                        (attendance.hour_from, attendance.hour_to) in periods)
                teachers = block_entries.employee_id
                absences = self._guard_duty_absence_state(intervals, teachers, hour_from, hour_to)
                block_covers = covers.filtered(
                    lambda cover, group=group, hour_from=hour_from, hour_to=hour_to:
                        cover.group_id == group and overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to))
                blocks.append({
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'entries': block_entries,
                    'teachers': teachers,
                    'absences': absences,
                    'covers': block_covers,
                    'empty': bool(teachers) and all(teacher.id in absences for teacher in teachers) and not block_covers,
                })
            blocks_by_group[group.id] = blocks
        return blocks_by_group

    @staticmethod
    def _allowed_absence_changes(blocks, breaks=()):
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

    @staticmethod
    def _notice_tuple(notice):
        """The change a notice is about, as the same tuple the options use."""
        if notice.absence_change_type in BREAK_CHANGES:
            return (notice.absence_change_type, notice.absence_change_hour, notice.absence_change_hour_to)
        return (notice.absence_change_type, notice.absence_change_hour)

    @classmethod
    def _notice_change(cls, notice):
        """The change a notice communicates; None for a rectification back to the usual
        timetable, which communicates that nothing changes."""
        if not notice or notice.absence_change_type in NORMAL_CHANGE.values():
            return None
        return cls._notice_tuple(notice)

    @staticmethod
    def _notice_side(notice, side):
        """Whether `notice` is about that side of the day: the start, the end, or the break it
        overlaps."""
        if not BoardBreakSide.is_break(side):
            return CHANGE_SIDES[notice.absence_change_type] == side
        return notice.absence_change_type in BREAK_CHANGES and overlaps(
            notice.absence_change_hour, notice.absence_change_hour_to, *BoardBreakSide.period(side))

    def _get_absence_change_states(self, day, groups):
        """`{group.id: {'entry': state, 'leave': state, break_side: state...}}` - where each side
        of each group's day (its start, its end, and each of its level's breaks)
        stands between what its absences allow (`'options'`, see _allowed_absence_changes, and
        `'expected'`, the largest of them) and what its families have been told (`'communicated'`,
        the latest notice on that side that left the draft state). `'status'`:
        - None: nothing to communicate, nothing communicated.
        - 'communicated': the families were told one of the allowed changes - the largest one or
          a smaller one the planner chose, with a guard for the rest: it is their decision, so a
          smaller one is never nagged about.
        - 'proposal': nothing communicated yet, and the absences allow a change.
        - 'rectification': what was communicated is no longer allowed (the absence shrank, was
          refused or cancelled, or the timetable changed): a sent notice cannot be undone, so a
          correcting one is proposed, with going back to the usual timetable among its options.
        `'target'` is the option proposed by default, `'draft'` a draft notice already prepared for
        one of the options, and `'teachers'` the absent teachers whose lessons the change concerns -
        any of their managers can act on it."""
        blocks_by_group = self._get_group_day_blocks(day, groups)
        notices = self.env['ems.notice'].sudo().search([
            ('absence_date', '=', day), ('absence_group_id', 'in', groups.ids)], order='id')
        weekday = str(day.weekday())
        breaks_by_level = {}
        states = {}
        for group in groups:
            blocks = blocks_by_group[group.id]
            level = group.level_id.id
            if level not in breaks_by_level:
                breaks_by_level[level] = sorted(self._get_guard_duty_board_break_periods(
                    [level], weekday, 0, 24)) if level else []
            allowed = self._allowed_absence_changes(blocks, breaks_by_level[level])
            group_notices = notices.filtered(lambda notice, group=group: notice.absence_group_id == group)
            states[group.id] = {}
            for side in allowed:
                side_notices = group_notices.filtered(
                    lambda notice, side=side: self._notice_side(notice, side))
                communicated = self._notice_change(
                    side_notices.filtered(lambda notice: notice.state in COMMUNICATED_NOTICE_STATES)[-1:])
                options = allowed[side]
                expected = options[-1] if options else None
                if not communicated:
                    status = 'proposal' if options else None
                elif any(self._same_change(communicated, option) for option in options):
                    status, options = 'communicated', []
                else:
                    normal = (('normal_break', *BoardBreakSide.period(side)) if BoardBreakSide.is_break(side)
                              else (NORMAL_CHANGE[side], 0.0))
                    status, options = 'rectification', options + [normal]
                target = options[-2] if status == 'rectification' and len(options) > 1 else (options[-1] if options else None)
                draft = side_notices.filtered(
                    lambda notice, options=options: notice.state == 'draft' and any(self._same_change(
                        self._notice_tuple(notice), option) for option in options))[-1:]
                window = [block for block in blocks if any(
                    self._change_window_contains(other, block['hour_from'], block['hour_to'])
                    for other in (expected, communicated))]
                teachers = self.env['hr.employee'].union(*(
                    block['teachers'].filtered(lambda teacher, block=block: teacher.id in block['absences'])
                    for block in window))
                states[group.id][side] = {
                    'expected': expected,
                    'communicated': communicated,
                    'status': status,
                    'options': options,
                    'target': target,
                    'draft': draft,
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
        if any(self._change_window_contains(sides[side]['communicated'], block['hour_from'], block['hour_to'])
               for side in sides):
            return None
        return block

    def _get_guard_candidates(self, day, hour_from, hour_to):
        """The teachers who can be sent to cover a class in the period: on guard duty then (a WC
        guard excluded - they are needed where they are) and not away themselves."""
        weekday = str(day.weekday())
        guards = self._get_guard_duty_board_attendance_ids().filtered(
            lambda attendance: attendance.dayofweek == weekday and attendance.non_teaching_is_guard
                and attendance.non_teaching.code != WC_GUARD_CODE
                and overlaps(attendance.hour_from, attendance.hour_to, hour_from, hour_to)).employee_id
        intervals = self._get_guard_duty_absence_intervals(day, guards)
        absent = self._guard_duty_absence_state(intervals, guards, hour_from, hour_to)
        return guards.filtered(lambda guard: guard.id not in absent)

    def get_guard_duty_board_lines(self, weekday, shift, level_ids=None, day=None):
        """Board rows for one weekday + shift: the ordered list of group columns actually taught in
        that slot, one row per distinct time period (chronological), each with one cell per group
        (teacher(s) + room, or empty) plus the guard-duty teacher(s) for that period. A guard row
        carries no group of its own (see 'non_teaching'), so it's reported separately from the
        group columns instead of as one more column. No per-subject colour is computed here (an
        earlier version reused ems.schedule_report_mixin's REPORT_COLOR_PALETTE the same way the
        teacher/group schedule PDFs do) - removed per developer feedback (2026-09-01): with every
        group already its own column and the subject spelled out as a short acronym in the cell,
        a colour-per-subject wash added visual noise without adding information a plain table
        didn't already convey.

        A period whose hour range is fully absorbed by another period starting at the same time
        (or earlier) never gets a row of its own - see _merge_absorbed_periods() - its cells/
        guards are folded into the row of the period that contains it instead (issue #410).

        A period left with no teaching cell AND no guard after that merge (e.g. a coordination
        duty/meeting nobody's actual class or guard shift overlaps) is dropped entirely - a row
        with nothing in it but a time range adds no information (developer follow-up on #410,
        2026-09-07).

        'level_ids' (issue #390, falsy/omitted = "All levels", the previous, still-default
        behaviour): a list of 'ems.level' ids to narrow the board down to. See "Level filter" in
        docs/en/developers/attendance/guard_duty_board.md for the full design. When set:
        - 'teaching_entries'/'groups'/'periods' only ever come from a group whose own 'level_id'
          (see ems.group's own field) is in 'level_ids' - a "reinforcement" group (no level_id by
          design) can never match. This is the only thing the filter actually controls: which
          time blocks (rows) exist at all.
        - A guard is shown on whichever ROW its own period overlaps, full stop - there is no way
          to know, and no need to know, which level a guard-duty teacher "belongs" to (developer
          feedback, 2026-09-07, after an earlier version tried deriving it from the teacher's own
          other classes that day and got it backwards for a guard who simply doesn't teach
          anything that day - see [[project_guard_duty_board_level_filter]] in memory): once a
          time block is visible for this level (because some class of it runs then), every guard
          on duty then is relevant, regardless of what they otherwise teach.
        - A guard whose own period isn't covered by any of the rows above still gets a shot at a
          dedicated "Patio" row if it falls inside that level's own break period - see
          _get_guard_duty_board_break_lines(). One left over after that simply has no visible
          block to attach to under this level and isn't shown (still visible under "All levels").

        Every row (filtered or not) also gets marked 'is_break' when its own period falls inside
        SOME level's own framework break period AND no group has a real class then (developer
        request, 2026-09-11: make a patio guard visually obvious even under "All levels", not
        only once a level filter is active). The "no real class" half of that check is what keeps
        this safe under "All levels" despite different levels having different break windows
        (confirmed against this dev DB: ESO/BTX break 10:00-10:25 + 12:25-12:40, ciclos break
        11:00-11:25 + 18:00-18:20) - a period that coincides with one level's break clock time
        while another level is genuinely teaching then already has a non-empty cell, so it's never
        mislabelled "Patio" just because some other level happens to be on a break at that hour.

        Checking every existing level in the client's own filter dropdown is normalized to the
        same "All levels" (falsy) path below, not treated as a real filter: even with the guard
        rule above, a level-filtered view only ever builds rows from teaching entries (never from
        a guard-only or "reinforcement"-group period the way the unfiltered path's own 'entries'-
        wide 'periods' does) - checking literally every level is meant to mean "show everything",
        indistinguishable from checking none at all.

        `day`, when given, is the concrete date the weekday stands for, and is what adds the
        absence information: every cell gains an 'absences' map of which of its own teachers are
        away, each row gains 'guard_absences' for the same question asked of the guard column,
        and 'absences' - the list of classes actually left without a teacher, which is what the
        board's second tab is built from. Without a date none of that can be resolved at all, so
        every one of those comes back empty and the board is the plain timetable it was before."""
        self.ensure_one()
        if level_ids and set(level_ids) >= set(self.env['ems.level'].search([]).ids):
            level_ids = None
        day = fields.Date.to_date(day)
        shift_start, shift_end = SHIFT_HOURS[shift]
        entries = self._get_guard_duty_board_attendance_ids().filtered(
            lambda attendance: attendance.dayofweek == weekday
                and attendance.hour_from >= shift_start and attendance.hour_to <= shift_end)
        teaching_entries = entries.filtered(lambda attendance: attendance.subject_id or attendance.group_ids)
        guard_entries = entries.filtered(lambda attendance: attendance.non_teaching_is_guard)
        intervals = self._get_guard_duty_absence_intervals(day, entries.employee_id)

        if level_ids:
            teaching_entries = teaching_entries.filtered(
                lambda attendance: attendance.group_ids.filtered(lambda group: group.level_id.id in level_ids))
            groups = teaching_entries.group_ids.filtered(lambda group: group.level_id.id in level_ids).sorted(key=lambda group: group.name)
            periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in teaching_entries})
        else:
            groups = teaching_entries.group_ids.sorted(key=lambda group: group.name)
            periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in entries})
        period_members = _merge_absorbed_periods(periods)
        break_periods = self._get_guard_duty_board_break_periods(level_ids, weekday, shift_start, shift_end)
        management = self._get_board_absence_management(day, groups, shift_start, shift_end)

        dated_lines = []
        remaining_guards = guard_entries
        for hour_from, hour_to in periods:
            if (hour_from, hour_to) not in period_members:
                continue  # absorbed - already folded into its container's row below
            member_periods = period_members[(hour_from, hour_to)]
            cells = []
            covering = []
            for group in groups:
                cell_entries = teaching_entries.filtered(
                    lambda attendance, group=group, member_periods=member_periods:
                        group in attendance.group_ids and (attendance.hour_from, attendance.hour_to) in member_periods
                )
                # Every co-teacher for this cell, deduped (a plain recordset union already
                # does that) - a co-taught slot has one 'resource.calendar.attendance' row
                # per teacher, all sharing the same group/period, so 'entries' alone would
                # silently drop every name but the first one picked for display.
                cell_teachers = cell_entries.mapped('employee_id')
                cell_absences = self._guard_duty_absence_state(
                    intervals, cell_teachers, hour_from, hour_to)
                cells.append({
                    'group': group,
                    'entries': cell_entries,
                    'teachers': cell_teachers,
                    'absences': cell_absences,
                })
                # One row per absent teacher AND per class of theirs in this period: a teacher
                # splitting the period across two groups leaves two classes uncovered, and each
                # one has to be assigned its own guard.
                first = cell_entries[:1]
                covering += [{
                    'teacher': teacher,
                    'state': cell_absences[teacher.id],
                    'group': group,
                    'subject': first.subject_id,
                    'room': first.space_id,
                    'covered': self._guard_duty_is_co_taught(cell_entries, teacher, cell_absences),
                    **self._board_absence_row_management(management, teacher, group, hour_from, hour_to),
                } for teacher in cell_teachers if teacher.id in cell_absences]
            if level_ids:
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
            if not guards and not any(cell['entries'] for cell in cells):
                continue  # nothing scheduled anywhere in this period - no row worth showing
            # See this method's own docstring for why the "no cell has a real class" half of this
            # check is what keeps it safe under "All levels" (where several, differently-timed
            # break windows coexist) as well as under a level filter.
            is_break = not any(cell['entries'] for cell in cells) and any(
                _period_contains(break_period, (hour_from, hour_to)) for break_period in break_periods)
            dated_lines.append((hour_from, hour_to, {
                'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
                'hour_from': hour_from,
                'hour_to': hour_to,
                'cells': cells,
                'guards': guards,
                'guard_colors': self._board_cover_colors(covering),
                # Not folded into 'absences' below: an absent guard has no class of their own for
                # anyone to cover, they are simply one fewer person available to cover somebody
                # else's - a subtraction from the guard column, not an addition to the work.
                'guard_absences': self._guard_duty_absence_state(
                    intervals, guards.mapped('employee_id'), hour_from, hour_to),
                'absences': covering,
                'is_break': is_break,
            }))

        if level_ids:
            dated_lines += self._get_guard_duty_board_break_lines(
                level_ids, weekday, shift_start, shift_end, groups, remaining_guards, intervals)
            dated_lines.sort(key=lambda dated_line: (dated_line[0], dated_line[1]))
        return {
            'groups': groups,
            'lines': [line for _hour_from, _hour_to, line in dated_lines],
            'actions': management['actions'] if management else [],
        }

    def _get_board_absence_management(self, day, groups, shift_start, shift_end):
        """Everything the absences table needs to manage the day's absences, resolved once per
        board load: the guard covers assigned on `day`, each group's timetable-change states (see
        _get_absence_change_states), and the day's pending 'actions' - a timetable change to
        propose or rectify for one of `groups`, or a guard assignment in this shift that is no
        longer needed. None without a day, like every other absence structure of the board."""
        if not day:
            return None
        covers = self.env['ems.absence_cover'].sudo().search([('date', '=', day), ('state', '=', 'assigned')])
        shift_covers = covers.filtered(
            lambda cover: cover.hour_from >= shift_start - HOUR_EPSILON and cover.hour_to <= shift_end + HOUR_EPSILON)
        states = self._get_absence_change_states(day, groups | shift_covers.group_id)
        editable = day >= self.env['ems.datetime_utils'].get_local_today()
        managers = {}

        def can_manage(teachers):
            # A day already over is read-only for everybody (see _check_board_day_not_past).
            return editable and any(
                managers.setdefault(teacher.id, self._is_absence_manager(teacher)) for teacher in teachers)

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
                        'can_manage': can_manage(state['teachers']),
                    })
        for cover in shift_covers:
            if not self._get_needed_absence_block(day, cover.group_id, cover.absent_employee_id, cover.hour_from, cover.hour_to):
                actions.append({
                    'type': 'obsolete_cover',
                    'cover': cover,
                    'group': cover.group_id,
                    'can_manage': can_manage(cover.absent_employee_id),
                })
        return {'covers': covers, 'states': states, 'actions': actions, 'can_manage': can_manage}

    def _board_absence_row_management(self, management, teacher, group, hour_from, hour_to):
        """The management part of one absences-table row: the guard 'cover' assigned to it (an
        empty recordset if none), the timetable change already communicated for its period
        ('authorized', which makes a guard unnecessary and strikes the row out) or one the
        absences allow but nobody has communicated yet ('proposed'), and whether the current user
        may act on it ('can_manage')."""
        if not management:
            return {'cover': self.env['ems.absence_cover'], 'authorized': None, 'proposed': None, 'can_manage': False}
        cover = management['covers'].filtered(
            lambda cover: cover.absent_employee_id == teacher and cover.group_id == group
                and overlaps(cover.hour_from, cover.hour_to, hour_from, hour_to))[:1]
        authorized = proposed = None
        for state in management['states'].get(group.id, {}).values():
            if self._change_window_contains(state['communicated'], hour_from, hour_to):
                authorized = state['communicated']
            elif state['status'] == 'proposal' and self._change_window_contains(state['expected'], hour_from, hour_to):
                proposed = state['expected']
        return {
            'cover': cover,
            'authorized': authorized,
            'proposed': proposed,
            'can_manage': management['can_manage'](teacher),
        }

    @staticmethod
    def _board_cover_colors(rows):
        """`{guard employee id: colour index}` for the guards covering classes in one row: each
        guard gets their own colour, shared with every class they cover in that row, so the table
        pairs them at a glance even when several guards cover several classes at once."""
        guards = sorted({row['cover'].guard_employee_id for row in rows if row['cover']}, key=lambda guard: guard.name)
        return {guard.id: index % COVER_COLOR_COUNT for index, guard in enumerate(guards)}

    def _get_guard_duty_board_break_periods(self, level_ids, weekday, shift_start, shift_end):
        """Distinct (hour_from, hour_to) break periods from the relevant level(s)' own schedule
        framework(s) - every framework, centre-wide, when 'level_ids' is falsy ("All levels"),
        only the selected one(s) otherwise. Shared by the main per-period loop above (which only
        ever marks a period 'is_break' when it ALSO has no real class in it - see that method's
        own docstring for why that keeps this safe centre-wide despite different levels having
        different break windows) and by '_get_guard_duty_board_break_lines' below (which still
        needs a level filter active, since it builds a whole synthetic row rather than just
        flagging an existing one)."""
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
                ('non_teaching_is_break', '=', True),
                ('hour_from', '>=', shift_start), ('hour_to', '<=', shift_end),
            ])
        }

    def _get_guard_duty_board_break_lines(self, level_ids, weekday, shift_start, shift_end, groups, unmatched_guards, intervals):
        """Once a level filter is active, that level's own break ("Patio") period has no real
        teaching entry of its own to build a row from (a teacher's own calendar spans one
        continuous block across it - see hr.employee._get_derived_break_entries' own docstring),
        so a guard duty scheduled specifically for a break would otherwise simply disappear once
        'get_guard_duty_board_lines' restricts its rows to the filtered level's teaching periods
        only. Any leftover 'unmatched_guards' entry (any guard not already folded into a row
        above - see the caller, which no longer derives a guard's own level at all) that falls
        inside one of that level's own framework(s)' break periods gets a dedicated row instead -
        marked 'is_break' for the client to label distinctly. A
        break period with no guard inside it renders nothing, same "nothing to show" rule every
        other row already follows. Only ever called once a level filter is active (see the
        caller) - under "All levels" a break-time guard already gets its 'is_break' flag directly
        on its normal row instead, via the main loop's own use of
        '_get_guard_duty_board_break_periods' (no synthetic row needed there, since "All levels"
        never restricts which periods get a row in the first place).

        'intervals' is forwarded straight from the caller so a guard's own absence still shows up
        on their dedicated break row exactly like it would on any other row - see
        get_guard_duty_board_lines()'s own 'guard_absences'."""
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
            dated_lines.append((hour_from, hour_to, {
                'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
                'hour_from': hour_from,
                'hour_to': hour_to,
                'guard_colors': {},
                'cells': [{
                    'group': group, 'entries': empty_entries, 'teachers': empty_entries.employee_id, 'absences': {},
                } for group in groups],
                'guards': guards,
                'guard_absences': self._guard_duty_absence_state(
                    intervals, guards.mapped('employee_id'), hour_from, hour_to),
                'absences': [],
                'is_break': True,
            }))
        return dated_lines

    @api.model
    def get_guard_duty_board_data(self, weekday, shift, level_ids=None, day=None):
        """JSON-safe wrapper around get_guard_duty_board_lines(), for the guard duty board client
        action's own RPC call (static/src/js/backend/guard_duty_board.js). @api.model: resolves
        "the current course" itself (env.company.current_course_id), so the JS side never needs
        to know or pass a specific ems.course id — matches how the aggregation itself is scoped
        (see _get_guard_duty_board_attendance_ids' own NOTE: not actually course-filtered).
        'level_ids' (issue #390) and 'day' are forwarded as-is - see get_guard_duty_board_lines()'s
        own docstring. Every teacher is reported as {'name', 'absence', 'is_wc'} rather than a bare
        name, so both of the screen's tabs read absences (and, for the guard column, the WC flag)
        the same way, off the same payload, instead of the client having to match names back
        against a separate list."""
        course = self.env.company.get_current_course_or_raise()
        data = course.get_guard_duty_board_lines(weekday, shift, level_ids=level_ids, day=day)
        groups = [{'id': group.id, 'name': group.name} for group in data['groups']]
        # A teacher on guard duty may take a free class themselves (issue #601) - from today on,
        # like every other board action (see _check_board_day_not_past).
        editable = bool(day) and fields.Date.to_date(day) >= self.env['ems.datetime_utils'].get_local_today()
        me = self.env.user.employee_id
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
                    'teachers': self._guard_duty_teacher_data(cell['teachers'], cell['absences']),
                    'room': first.space_id.display_name if first and first.space_id else False,
                })
            wc_employee_ids = set(line['guards'].filtered(
                lambda attendance: attendance.non_teaching.code == WC_GUARD_CODE).mapped('employee_id').ids)
            guards = self._guard_duty_teacher_data(
                line['guards'].mapped('employee_id'), line['guard_absences'], wc_employee_ids)
            for guard in guards:
                guard['color'] = line['guard_colors'].get(guard['id'], False)
            candidate_ids = {guard['id'] for guard in guards if not guard['is_wc'] and not guard['absence']}
            on_guard = editable and me.id in candidate_ids
            lines.append({
                'time_label': line['time_label'],
                'hour_from': line['hour_from'],
                'hour_to': line['hour_to'],
                'cells': cells,
                'guards': guards,
                # Who can be sent to one of this row's classes - see _get_guard_candidates().
                'guard_candidates': [{'id': guard['id'], 'name': guard['name']} for guard in guards
                                     if guard['id'] in candidate_ids],
                'absences': [{
                    'teacher': row['teacher'].display_name,
                    'teacher_id': row['teacher'].id,
                    'state': row['state'],
                    'group': row['group'].name,
                    'group_id': row['group'].id,
                    'subject': row['subject'].acronym if row['subject'] else False,
                    'room': row['room'].display_name if row['room'] else False,
                    'covered': row['covered'],
                    'cover': {
                        'id': row['cover'].id,
                        'guard_id': row['cover'].guard_employee_id.id,
                        'guard': row['cover'].guard_employee_id.name,
                        'message': row['cover'].message or '',
                        'color': line['guard_colors'].get(row['cover'].guard_employee_id.id, 0),
                    } if row['cover'] else False,
                    'authorized': self._absence_change_label(row['authorized']),
                    'proposed': self._absence_change_label(row['proposed'], proposed=True),
                    'can_manage': row['can_manage'],
                    'can_self_assign': on_guard and not (row['cover'] or row['covered'] or row['authorized']),
                    'can_self_release': editable and bool(row['cover']) and row['cover'].is_self_assigned
                        and row['cover'].assigned_by_id == self.env.user,
                } for row in line['absences']],
                'is_break': line.get('is_break', False),
            })
        return {'groups': groups, 'lines': lines,
                # Only whoever may act on them sees the day's pending decisions: to everybody else
                # they are noise, and the struck-out rows already say what was decided.
                'actions': [self._board_action_data(action) for action in data['actions'] if action['can_manage']]}

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

    def _board_action_data(self, action):
        """JSON-safe version of one of the day's pending actions (see
        _get_board_absence_management), with the sentence the absences table shows for it."""
        data = {'type': action['type'], 'group_id': action['group'].id, 'can_manage': action['can_manage']}
        values = {'group': action['group'].name}
        if action['type'] == 'obsolete_cover':
            cover = action['cover']
            values.update(guard=cover.guard_employee_id.name, time=cover._time_label(), teacher=cover.absent_employee_id.name)
            data.update(cover_id=cover.id, label=_(
                "%(guard)s no longer needs to cover %(group)s at %(time)s (%(teacher)s).", **values))
            return data
        if action['type'] == 'proposal':
            values['change'] = self._absence_change_label(action['expected'], proposed=True)
            label = _("%(group)s: %(change)s.", **values)
        else:
            values['change'] = self._absence_change_label(action['expected'])
            values['told'] = self._absence_change_label(action['communicated'])
            label = _("%(group)s: the families were told \"%(told)s\", which no longer matches the absences "
                      "(now: %(change)s).", **values)
        # Every change that can be communicated, from the smallest to the largest: the planner may
        # tell the families about part of the empty lessons and send a guard to the rest.
        options = [{'change_type': change[0], 'hour': change[1], 'hour_to': change[2] if len(change) > 2 else 0.0,
                    'label': self._absence_change_label(change)}
                   for change in action['options']]
        draft = action['draft']
        draft_change = self._notice_tuple(draft) if draft else None
        data.update(label=label, options=options, default=action['options'].index(action['target']),
                    draft_id=draft.id or False,
                    draft_label=self._absence_change_label(draft_change) if draft_change else False)
        return data

    @staticmethod
    def _guard_duty_teacher_data(teachers, absences, wc_employee_ids=()):
        """Teachers as `[{'name', 'absence', 'is_wc'}]` - 'absence' being False, 'approved' or
        'pending'; 'is_wc' flags a 'Guard (WC)' duty specifically (developer request, 2026-09-11)
        - the one guard subtype that, unlike 'Guard (Break)' (always patio time, already covered
        by 'is_break' on the line itself), can fall at any time of day, so it's worth calling out
        next to the teacher's own name. Always False for a teaching cell's own teachers, which
        never pass 'wc_employee_ids' - only the guard column cares about this distinction."""
        return [{'id': teacher.id, 'name': teacher.display_name, 'absence': absences.get(teacher.id, False),
                 'is_wc': teacher.id in wc_employee_ids}
                for teacher in teachers]

    @api.model
    def get_guard_duty_board_levels(self):
        """Every 'ems.level', for the guard duty board's own level filter (issue #390) - plain
        id/name pairs, JSON-safe like get_guard_duty_board_data(). No course scoping: a level is
        centre-wide curriculum data, not tied to any one ems.course."""
        return [{'id': level.id, 'name': level.name} for level in self.env['ems.level'].search([])]

    @api.model
    def get_current_course_data(self):
        """Small helper for the guard duty board's client action: the page has no bound record of
        its own to read 'the current course' from (see the class docstring above for why), so it
        asks for it explicitly instead — used both to label the page and to supply the PDF
        button's own 'active_ids'."""
        course = self.env.company.get_current_course_or_raise()
        return {'id': course.id, 'name': course.name}
