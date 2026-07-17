# -*- coding: utf-8 -*-

from odoo import fields, models

WEEKDAYS = ('0', '1', '2', '3', '4')
# A group's own shift already tells us the realistic hour window for its schedule, so the report
# doesn't need to show/print a wider range than that. Kept in sync by hand with the JS copy
# (SHIFT_HOURS in static/src/js/backend/group_schedule_grid_field.js).
SHIFT_HOURS = {
    'morning': (8, 15),
    'afternoon': (15, 22),
}


class ems_group_schedule(models.Model):
    # NOTE: an explicit '_name' is required here — a 2-item '_inherit' list without one would make
    # Odoo's metaclass define a brand-new model named after this Python class instead of extending
    # 'ems.group' in place (see MetaModel in odoo/models.py).
    _name = 'ems.group'
    _inherit = ['ems.group', 'ems.schedule_report_mixin']

    # Union of two sources: the group's real teaching slots, aggregated from every teacher's
    # calendar whose 'group_ids' includes this group, and — when derivable — the group's break
    # period, taken from its level's schedule framework (see '_get_break_entries'). Not stored,
    # same pattern already used for 'enrolled_student_ids'.
    schedule_attendance_ids = fields.Many2many(string="Schedule", comodel_name="resource.calendar.attendance",
        compute="_compute_schedule_attendance_ids")

    def _compute_schedule_attendance_ids(self):
        for group in self:
            teaching = self.env['resource.calendar.attendance'].search([('group_ids', '=', group.id)])
            group.schedule_attendance_ids = teaching | group._get_break_entries()

    def _get_break_entries(self):
        """The group's break/patio period, derived from its level's schedule framework (a
        'resource.calendar' with is_framework=True and a matching level_id) — filtering that
        framework's own non-teaching rows for is_break=True and a day_period matching the group's
        own shift. A break row never carries 'group_ids' itself (see 'ems_working_schedule_assignation'),
        so this is the only way to attach one to a group. Returns an empty recordset, without error,
        when the group has no level (e.g. a reinforcement group), no shift, or its level has no
        framework — the break simply doesn't appear on that group's schedule."""
        self.ensure_one()
        if not self.level_id or not self.shift:
            return self.env['resource.calendar.attendance']
        framework = self.env['resource.calendar'].search(
            [('is_framework', '=', True), ('level_id', '=', self.level_id.id)], limit=1)
        return framework.attendance_ids.filtered(
            lambda attendance: attendance.dayofweek in WEEKDAYS
                and attendance.non_teaching.is_break and attendance.day_period == self.shift)

    def get_schedule_report_lines(self):
        """Weekly schedule rows (one per distinct Mon-Fri period, one column per weekday) for the
        group's Schedule tab/PDF. Unlike the teacher-side version this method mirrors
        (resource.calendar.get_schedule_report_lines), a cell can hold more than one entry: several
        teachers co-teaching the same subject at the same time. Those are grouped into a single
        'block' (same subject/non-teaching reason) instead of one block per teacher — co-teaching is
        surfaced in 'get_subject_teachers_summary' instead, not by repeating the block."""
        self.ensure_one()
        weekday_entries = self.schedule_attendance_ids.filtered(lambda attendance: attendance.dayofweek in WEEKDAYS)
        shift_hours = SHIFT_HOURS.get(self.shift)
        if shift_hours:
            shift_start, shift_end = shift_hours
            weekday_entries = weekday_entries.filtered(
                lambda attendance: attendance.hour_from >= shift_start and attendance.hour_to <= shift_end)
        periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in weekday_entries})

        color_by_key = {}
        for attendance in weekday_entries.sorted(key=lambda attendance: (attendance.dayofweek, attendance.hour_from)):
            key = self._report_color_key(attendance)
            color_by_key.setdefault(key, self.REPORT_COLOR_PALETTE[len(color_by_key) % len(self.REPORT_COLOR_PALETTE)])

        lines = []
        for hour_from, hour_to in periods:
            cells = []
            for dayofweek in WEEKDAYS:
                day_entries = weekday_entries.filtered(
                    lambda attendance, dayofweek=dayofweek, hour_from=hour_from, hour_to=hour_to:
                        attendance.dayofweek == dayofweek and attendance.hour_from == hour_from and attendance.hour_to == hour_to
                )
                blocks_by_key = {}
                for attendance in day_entries:
                    key = self._report_color_key(attendance)
                    blocks_by_key[key] = blocks_by_key.get(key, self.env['resource.calendar.attendance']) | attendance
                cells.append({
                    'blocks': [{'entries': entries, 'color': color_by_key.get(key)} for key, entries in blocks_by_key.items()],
                })
            lines.append({
                'time_label': f"{self._format_report_time(hour_from)}-{self._format_report_time(hour_to)}",
                'cells': cells,
            })
        return lines

    def get_subject_teachers_summary(self):
        """One row per distinct subject taught to this group, with the sorted, de-duplicated list of
        teachers teaching it — this is where co-teaching becomes visible (more than one name in the
        row), instead of in the grid (see 'get_schedule_report_lines')."""
        self.ensure_one()
        teaching_entries = self.schedule_attendance_ids.filtered('subject_id')
        rows = []
        for subject in teaching_entries.mapped('subject_id').sorted('name'):
            entries = teaching_entries.filtered(lambda attendance, subject=subject: attendance.subject_id == subject)
            teachers = sorted(set(entries.mapped('employee_id.display_name')))
            rows.append({'subject': subject.display_name, 'teachers': ", ".join(teachers)})
        return rows
