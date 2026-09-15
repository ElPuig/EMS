# -*- coding: utf-8 -*-

from odoo import models

# Two hour_from/hour_to values meant to represent the exact same moment can differ by a tiny
# float remainder depending on how each was computed/entered (e.g. a framework's break stored as
# the literal '11.416667' vs a real period's own hour_from computed as '11 + 25/60' ==
# 11.416666666666666) — a strict '<'/'==' comparison would misread that hair's-width gap as a
# real difference. 1/120 hour (30s) safely absorbs that noise without being large enough to treat
# two genuinely distinct, minutes-apart periods as touching. Shared here (not private to one
# model) because both 'hr.employee._get_derived_break_entries' (employees/employee.py) and
# 'ems.course._merge_absorbed_periods' (attendance/guard_duty_board.py) need the exact same
# tolerance for the same kind of comparison.
HOUR_EPSILON = 1 / 120

# Issue #453 - base path of the public, no-login schedule PDFs: one per group (models/contacts/
# group_schedule.py) and one per study (models/curriculum/study_schedule.py). Shared here, not in
# either of those files: 'shared' is imported first, so importing it from another area never
# changes the order Odoo registers that area's models in.
PUBLIC_SCHEDULE_ROUTE = '/ems/schedule'


class EmsScheduleReportMixin(models.AbstractModel):
    _name = 'ems.schedule_report_mixin'
    _description = "Shared weekly-schedule aggregation/coloring/time-formatting helpers, for any " \
                    "model exposing its own read-only 'schedule_attendance_ids' (ems.group, res.partner)."

    WEEKDAYS = ('0', '1', '2', '3', '4')
    # The realistic hour window for a weekly schedule report/grid, so it doesn't need to show/print
    # a wider range than that. Kept in sync by hand with the JS copy (SHIFT_HOURS in
    # static/src/js/backend/schedule_grid_readonly_field.js).
    SHIFT_HOURS = {
        'morning': (8, 15),
        'afternoon': (15, 22),
    }

    # NOTE: assigned in first-seen order to the distinct items on a schedule, so two unrelated
    # items only ever share a color once the palette itself runs out.
    REPORT_COLOR_PALETTE = [
        '#5b8def', '#f4a261', '#2a9d8f', '#e76f51', '#8ecae6', '#ffb703',
        '#c77dff', '#06d6a0', '#ef476f', '#118ab2', '#bc6c25', '#9d4edd',
    ]

    def _report_color_key(self, attendance):
        # 'topic' (issue #428) is part of the key too: two teachers can genuinely share the exact
        # same subject/group/slot while teaching different topics (e.g. FP Basica's MP 3161, split
        # by language) - without topic in the key, this method doubles as get_schedule_report_lines()'s
        # own block-grouping key (see 'blocks_by_key' below), so the two would silently merge into
        # one block showing only one of the two teachers/topics, chosen arbitrarily by entry order.
        if attendance.non_teaching:
            return ('non_teaching', attendance.non_teaching.id)
        return ('subject', attendance.subject_id.id, attendance.topic or False)

    def _format_report_time(self, value):
        hour, minutes = divmod(round(value * 60), 60)
        return f"{hour:02d}:{minutes:02d}"

    def _get_level_break_entries(self, level, shift):
        """The break/patio period derived from `level`'s schedule framework (a 'resource.calendar'
        with is_framework=True and a matching level_id), filtering that framework's own
        non-teaching rows for is_break=True and a day_period matching `shift`. Shared by
        ems.group._get_break_entries() (level/shift = the group's own) and res.partner (student)
        _get_break_entries() (level/shift = the student's main_group_id's) — a break row never
        carries 'group_ids' itself (see 'ems_working_schedule_assignation'), so this is the only
        way to attach one to a group or, transitively, to a student. Returns an empty recordset,
        without error, when `level` or `shift` is falsy, or `level` has no framework."""
        if not level or not shift:
            return self.env['resource.calendar.attendance']
        # 'active_test=True' forced explicitly (not just relied on as the ORM's own default):
        # this method can run under a caller context that already set active_test=False for an
        # unrelated reason (e.g. opened from ems.action_student_kanban, whose own context turns
        # it off so archived/withdrawn students still show up in that list) - without forcing it
        # back on here, an archived framework calendar could resurface a stale break block. See
        # the identical, confirmed-real fix on '_compute_schedule_attendance_ids' in both
        # ems.group and res.partner (student) for the actual incident this was found from.
        framework = self.env['resource.calendar'].with_context(active_test=True).search(
            [('is_framework', '=', True), ('level_id', '=', level.id)], limit=1)
        return framework.attendance_ids.filtered(
            lambda attendance: attendance.dayofweek in self.WEEKDAYS
                and attendance.non_teaching.is_break and attendance.day_period == shift)

    def _schedule_report_shift(self):
        """The shift used to pick 'get_schedule_report_lines()'s hour window (SHIFT_HOURS) and to
        filter 'schedule_attendance_ids' down to a realistic slice of the day. Defaults to a plain
        'shift' field (ems.group's own); res.partner (student) overrides this to read its
        main_group_id.shift instead, since a student has no shift field of its own."""
        self.ensure_one()
        return self.shift

    def get_schedule_report_lines(self):
        """Weekly schedule rows (one per distinct Mon-Fri period, one column per weekday) for a
        Schedule tab/PDF built on top of 'schedule_attendance_ids' — shared by ems.group and
        res.partner (student), the only difference between the two being which shift
        '_schedule_report_shift()' resolves to. A cell can hold more than one entry (several
        teachers co-teaching the same subject at the same time, for a group; a student's own
        overlapping enrollments, for a student): those are grouped into a single 'block' per
        distinct subject/non-teaching reason instead of one block per entry — co-teaching is
        surfaced in 'get_subject_teachers_summary' instead, not by repeating the block."""
        self.ensure_one()
        weekday_entries = self.schedule_attendance_ids.filtered(lambda attendance: attendance.dayofweek in self.WEEKDAYS)
        shift_hours = self.SHIFT_HOURS.get(self._schedule_report_shift())
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
            for dayofweek in self.WEEKDAYS:
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
        """One row per distinct (subject, topic) pair in this schedule, with the sorted,
        de-duplicated list of teachers teaching it — this is where co-teaching (a group) or
        several teachers across different groups (a student's own subjects) becomes visible (more
        than one name in the row), instead of in the grid (see 'get_schedule_report_lines').
        Grouping by topic too (issue #428), not just subject, is what actually separates a subject
        split into several distinct topics (e.g. FP Basica's MP 3161: Castella/Catala/Angles, each
        taught by a different teacher) into their own rows instead of merging every teacher under
        one single 'subject' row."""
        self.ensure_one()
        teaching_entries = self.schedule_attendance_ids.filtered('subject_id')
        rows = []
        for subject in teaching_entries.mapped('subject_id').sorted('name'):
            subject_entries = teaching_entries.filtered(lambda attendance, subject=subject: attendance.subject_id == subject)
            for topic in sorted(set(subject_entries.mapped(lambda attendance: attendance.topic or False)), key=lambda topic: topic or ""):
                entries = subject_entries.filtered(lambda attendance, topic=topic: (attendance.topic or False) == topic)
                teachers = sorted(set(entries.mapped('employee_id.display_name')))
                rows.append({'subject': entries[:1].get_subject_display_label(), 'teachers': ", ".join(teachers)})
        return rows
