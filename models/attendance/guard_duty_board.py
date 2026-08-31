# -*- coding: utf-8 -*-

from odoo import api, models

WEEKDAYS = ('0', '1', '2', '3', '4')
# Mirrors ems.group's own SHIFT_HOURS (models/contacts/group_schedule.py) — the guard duty board
# needs the same morning/afternoon split, but rendered as weekday x shift tables with one column
# per group rather than one column per weekday, so it can't reuse that method as-is.
SHIFT_HOURS = {
    'morning': (8, 15),
    'afternoon': (15, 22),
}


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
        pre-existing row necessarily has it set)."""
        return self.env['resource.calendar.attendance'].search([
            ('calendar_id.is_framework', '=', False),
            ('dayofweek', 'in', WEEKDAYS),
        ])

    def get_guard_duty_board_lines(self, weekday, shift):
        """Board rows for one weekday + shift: the ordered list of group columns actually taught in
        that slot, one row per distinct time period (chronological), each with one cell per group
        (teacher(s) + room, or empty) plus the guard-duty teacher(s) for that period. A guard row
        carries no group of its own (see 'non_teaching'), so it's reported separately from the
        group columns instead of as one more column."""
        self.ensure_one()
        shift_start, shift_end = SHIFT_HOURS[shift]
        entries = self._get_guard_duty_board_attendance_ids().filtered(
            lambda attendance: attendance.dayofweek == weekday
                and attendance.hour_from >= shift_start and attendance.hour_to <= shift_end)
        teaching_entries = entries.filtered(lambda attendance: attendance.subject_id or attendance.group_ids)
        guard_entries = entries.filtered(lambda attendance: attendance.non_teaching_is_guard)

        groups = teaching_entries.group_ids.sorted(key=lambda group: group.name)
        periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in entries})

        color_by_key = {}
        for attendance in teaching_entries.sorted(key=lambda attendance: attendance.hour_from):
            key = self._report_color_key(attendance)
            color_by_key.setdefault(key, self.REPORT_COLOR_PALETTE[len(color_by_key) % len(self.REPORT_COLOR_PALETTE)])

        lines = []
        for hour_from, hour_to in periods:
            cells = []
            for group in groups:
                cell_entries = teaching_entries.filtered(
                    lambda attendance, group=group, hour_from=hour_from, hour_to=hour_to:
                        group in attendance.group_ids and attendance.hour_from == hour_from and attendance.hour_to == hour_to
                )
                cells.append({
                    'group': group,
                    'entries': cell_entries,
                    # Every co-teacher for this cell, deduped (a plain recordset union already
                    # does that) - a co-taught slot has one 'resource.calendar.attendance' row
                    # per teacher, all sharing the same group/period, so 'entries' alone would
                    # silently drop every name but the first one picked for display.
                    'teachers': cell_entries.mapped('employee_id'),
                    'color': color_by_key.get(self._report_color_key(cell_entries[:1])) if cell_entries else False,
                })
            guards = guard_entries.filtered(
                lambda attendance, hour_from=hour_from, hour_to=hour_to:
                    attendance.hour_from == hour_from and attendance.hour_to == hour_to)
            lines.append({
                'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
                'cells': cells,
                'guards': guards,
            })
        return {'groups': groups, 'lines': lines}

    @api.model
    def get_guard_duty_board_data(self, weekday, shift):
        """JSON-safe wrapper around get_guard_duty_board_lines(), for the guard duty board client
        action's own RPC call (static/src/js/backend/guard_duty_board.js). @api.model: resolves
        "the current course" itself (env.company.current_course_id), so the JS side never needs
        to know or pass a specific ems.course id — matches how the aggregation itself is scoped
        (see _get_guard_duty_board_attendance_ids' own NOTE: not actually course-filtered)."""
        course = self.env.company.current_course_id
        data = course.get_guard_duty_board_lines(weekday, shift)
        groups = [{'id': group.id, 'name': group.name} for group in data['groups']]
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
                    'teachers': cell['teachers'].mapped('display_name'),
                    'room': first.space_id.display_name if first and first.space_id else False,
                    'color': cell['color'],
                })
            lines.append({
                'time_label': line['time_label'],
                'cells': cells,
                'guards': line['guards'].mapped('employee_id.display_name'),
            })
        return {'groups': groups, 'lines': lines}

    @api.model
    def get_current_course_data(self):
        """Small helper for the guard duty board's client action: the page has no bound record of
        its own to read 'the current course' from (see the class docstring above for why), so it
        asks for it explicitly instead — used both to label the page and to supply the PDF
        button's own 'active_ids'."""
        course = self.env.company.current_course_id
        return {'id': course.id, 'name': course.name}
