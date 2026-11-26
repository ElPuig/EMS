# -*- coding: utf-8 -*-

import base64
import io
import re
from collections import defaultdict

import xlsxwriter
from xlsxwriter.utility import xl_range_abs

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..attendance.absence_coverage import overlaps
from ..attendance.guard_duty_board import _merge_absorbed_periods

AREA_DOMAIN = [('is_top_level', '=', True), ('top_level_area', '=', 'academic')]
# The "By period" sheet's columns the summary counts on, and where the summary starts (column N).
CONTRACT_COLUMN, ATTENDANCE_COLUMN, SUMMARY_COLUMN = 2, 9, 13
SUMMARY_STATUSES = ('walkout', 'present', 'absence')


def _sheet_name(*parts):
    """A worksheet name from `parts`: Excel refuses []:*?/\\ in one, and more than 31 characters."""
    return re.sub(r'[\[\]:*?/\\]', '-', ' - '.join(parts))[:31]


class EmsStaffWalkoutReport(models.TransientModel):
    """Issue #865: the walkout control sheet, an .xlsx to print before a walkout day starts and
    note down by hand who comes. One pair of sheets per teaching area (a top-level academic
    department): every teacher once, in the first period of their schedule that day, with what
    they have then (activity, group, room, expected students) and blank columns to fill in; and a
    grid of every teacher by period, like the guard duty board.

    The file is built when asked for and kept in the transient record itself (attachment=False),
    downloaded through Odoo's own /web/content: no controller of its own, and the data (staff and
    their absences) leaves the database with the record when Odoo vacuums it."""
    _inherit = 'ems.staff_walkout_report'

    area_id = fields.Many2one(string="Area", comodel_name='hr.department', domain=AREA_DOMAIN,
                              help="Leave it empty for every teaching area, each on sheets of its own.")
    control_sheet = fields.Binary(string="Control sheet", attachment=False, readonly=True)
    control_sheet_name = fields.Char(string="Control sheet file name", readonly=True)

    def action_download_control_sheet(self):
        self.ensure_one()
        self.write({
            'control_sheet': base64.b64encode(self._get_control_sheet_xlsx()),
            'control_sheet_name': f"{_('Walkout control sheet')} {self.date.isoformat()}.xlsx",
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=control_sheet'
                   f'&filename_field=control_sheet_name&download=true',
            'target': 'download',
        }

    # --- Data ------------------------------------------------------------------------------------

    def _get_control_sheet_areas(self):
        """`[(area, periods, teachers)]`, one per teaching area with somebody scheduled that day:
        `periods` the area's own periods in order, `teachers` one dict per teacher (see
        _get_control_sheet_teacher). sudo: the sheet is for whoever sees the walkout report, who
        sees the whole staff's day (the same reach as the report itself)."""
        self.ensure_one()
        self._check_not_public_holiday()
        areas = self.area_id or self.env['hr.department'].search(AREA_DOMAIN, order='name')
        teachers = self.env['hr.employee'].sudo().search([
            ('employee_type', '=', 'teacher'), ('schedule_import_code', '=', False),
            ('department_id', 'child_of', areas.ids)])
        slots = self.env['ems.absence_pending']._ems_scheduled_slots(self.date, teachers)
        day = self._get_control_sheet_day(teachers, slots)
        area_of = self._get_department_areas(teachers)
        slots_by_area = defaultdict(lambda: defaultdict(lambda: slots.browse()))
        for slot in slots:
            teacher = slot.calendar_id.employee_id
            slots_by_area[area_of[teacher.department_id.id]][teacher] |= slot
        result = []
        for area in areas:
            teacher_slots = slots_by_area.get(area.id)
            if not teacher_slots:
                continue
            members = _merge_absorbed_periods(sorted({(slot.hour_from, slot.hour_to)
                                                      for area_slots in teacher_slots.values() for slot in area_slots}))
            period_of = {member: period for period, period_members in members.items() for member in period_members}
            result.append((area, sorted(members), sorted(
                (self._get_control_sheet_teacher(teacher, area_slots, period_of, day)
                 for teacher, area_slots in teacher_slots.items()),
                key=lambda entry: (entry['start'], entry['name']))))
        if not result:
            raise UserError(_("Nobody in %s has a schedule on this day.",
                              self.area_id.name or _("the teaching areas")))
        return result

    def _get_control_sheet_day(self, teachers, slots):
        """What is known of the day so far, read once for every teacher and class: 'absences' (the
        absence requests, as the walkout report takes them), 'arrivals' (each teacher's first
        check-in), 'expected' and 'present' (students per slot, see _get_expected_students and
        _get_present_students) and 'now', the hour up to which the day has gone by (24 for a day
        over, -1 for one to come)."""
        utils = self.env['ems.datetime_utils']
        local_now = utils.get_local_datetime()
        if self.date < local_now.date():
            now = 24.0
        elif self.date == local_now.date():
            now = utils.time_to_float(local_now)
        else:
            now = -1.0
        return {
            'absences': self.env['ems.course']._get_guard_duty_leave_intervals(self.date, teachers),
            'arrivals': self.env['hr.attendance']._ems_first_check_in_hours(self.date, teachers),
            'expected': self._get_expected_students(slots),
            'present': self._get_present_students(slots),
            'now': now,
        }

    def _get_control_sheet_teacher(self, teacher, slots, period_of, day):
        """What the sheet shows of `teacher`: their name, department and contract, the period they
        start in ('start') with what they do then ('first', see _get_control_sheet_cell), and every
        period of their day ('grid'). 'absence' tells whether an absence request (approved or
        awaiting approval) covers their first period; 'absent' lists the grid's periods one covers.
        'status' and 'arrival' are the teacher's attendance so far (see _get_teacher_status)."""
        by_period = defaultdict(lambda: slots.browse())
        for slot in slots.sorted(lambda slot: (slot.hour_from, slot.id)):
            by_period[period_of[(slot.hour_from, slot.hour_to)]] |= slot
        start = min(by_period)
        absences = day['absences'].get(teacher.id, ())

        def covering(period):
            return [state for hour_from, hour_to, state in absences if overlaps(*period, hour_from, hour_to)]

        first_absences = covering(start)
        absence = ('pending' if 'pending' in first_absences else 'approved') if first_absences else False
        return {
            'name': teacher.name,
            'department': teacher.department_id.name or '',
            'contract': teacher.contract_type_id.name or '',
            'start': start,
            'first': self._get_control_sheet_cell(by_period[start], day),
            'absence': absence,
            'status': self._get_teacher_status(absence, day['arrivals'].get(teacher.id), start, day['now']),
            'arrival': day['arrivals'].get(teacher.id),
            'grid': {period: self._get_control_sheet_cell(period_slots, day)
                     for period, period_slots in by_period.items()},
            'absent': {period for period in by_period if covering(period)},
        }

    @staticmethod
    def _get_teacher_status(absence, arrival, start, now):
        """'absence' when an absence request covers their first period, 'present' once they have
        checked in (at any time: a late arrival may be the walkout's own doing, as the walkout report
        counts it), 'walkout' when their first period has started with neither, None until then."""
        if absence:
            return 'absence'
        if arrival is not None:
            return 'present'
        return 'walkout' if start[0] <= now else None

    def _get_control_sheet_cell(self, slots, day):
        """What `slots` (a teacher's slots in one period, usually one) are about: activity, groups,
        room code and name, expected and present students (None when unknown) and whether it is a
        class."""
        def total(counts):
            known = [counts[slot.id] for slot in slots if counts.get(slot.id) is not None]
            return sum(known) if known else None

        return {
            'activity': ' / '.join(
                slot.subject_id._label_with_topic(slot.topic) if slot.subject_id else (slot.non_teaching.name or slot.name)
                for slot in slots),
            'groups': ', '.join(slots.group_ids.mapped('name')),
            'room_code': ', '.join(code for code in slots.space_id.mapped('code') if code),
            'room': ', '.join(slots.space_id.mapped('name')),
            'students': total(day['expected']),
            'present': total(day['present']),
            'teaching': bool(slots.subject_id),
        }

    def _get_present_students(self, slots):
        """`{slot.id: count}` for the classes among `slots` whose roll call has been taken that day:
        the students marked with an attendance status (attended, minor delay), as the attendance
        reports count them. A class with no roll call yet is left out. Two queries for every class."""
        schedules = slots.attendance_schedule_id
        sessions = self.env['ems.attendance_session_header'].sudo().search(
            [('attendance_schedule_id', 'in', schedules.ids), ('date', '=', self.date)])
        if not sessions:
            return {}
        present = dict(self.env['ems.attendance_session_line'].sudo()._read_group(
            [('attendance_session_id', 'in', sessions.ids), ('status_id.category', '=', 'assistance'),
             ('not_expected_reason', '=', False)],
            ['attendance_session_id'], ['__count']))
        by_schedule = {session.attendance_schedule_id.id: present.get(session, 0) for session in sessions}
        return {slot.id: by_schedule[slot.attendance_schedule_id.id]
                for slot in slots if slot.attendance_schedule_id.id in by_schedule}

    def _get_expected_students(self, slots):
        """`{slot.id: count}` for the classes among `slots`: the roll-call list of the class (its
        ems.attendance_schedule line, built from the enrollments) or, when the class has none (no
        enrollment per subject, as in ESO and Batxillerat), the students of its groups when they are
        all main groups. A class of a split, optional or reinforcement group with no list is left
        out: there is no knowing who goes to it."""
        classes = slots.filtered(lambda slot: slot.subject_id and slot.group_ids)
        counts = {slot.id: len(slot.attendance_schedule_id.student_ids) for slot in classes}
        without_list = classes.filtered(
            lambda slot: not counts[slot.id] and set(slot.group_ids.mapped('group_type')) == {'main'})
        per_group = dict(self.env['res.partner'].sudo()._read_group(
            [('contact_type', '=', 'student'), ('main_group_id', 'in', without_list.group_ids.ids)],
            ['main_group_id'], ['__count'])) if without_list else {}
        for slot in without_list:
            counts[slot.id] = sum(per_group.get(group, 0) for group in slot.group_ids)
        known = set(without_list.ids)
        return {slot_id: count for slot_id, count in counts.items() if count or slot_id in known}

    # --- Spreadsheet -----------------------------------------------------------------------------

    def _get_control_sheet_xlsx(self):
        areas = self._get_control_sheet_areas()
        format_time = self.env['ems.schedule_report_mixin']._format_report_time

        def label(period):
            return f"{format_time(period[0])}-{format_time(period[1])}"

        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {'in_memory': True})
        base = {'border': 1, 'border_color': '#999999', 'valign': 'vcenter', 'text_wrap': True}
        formats = {
            'title': workbook.add_format({'bold': True, 'font_size': 14}),
            'note': workbook.add_format({'italic': True, 'font_size': 9}),
            'block': workbook.add_format({'bold': True, 'font_size': 12, 'font_color': '#FFFFFF', 'bg_color': '#970A2C'}),
            'header': workbook.add_format({**base, 'bold': True, 'bg_color': '#F1EDEE'}),
            'header_centre': workbook.add_format({**base, 'bold': True, 'bg_color': '#F1EDEE', 'align': 'center'}),
            'grid_header': workbook.add_format({**base, 'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#970A2C',
                                                'align': 'center'}),
        }
        for name, colour in (('cell', None), ('duty', '#FDEEDC'), ('absent', '#D9D9D9')):
            extra = {'bg_color': colour} if colour else {}
            formats[name] = workbook.add_format({**base, **extra})
            formats[f'{name}_centre'] = workbook.add_format({**base, **extra, 'align': 'center'})
        day = self.date.strftime('%d/%m/%Y')
        absence_notes = {'approved': _("Approved absence"), 'pending': _("Absence awaiting approval")}
        statuses = {'present': _("Present"), 'walkout': _("On walkout"), 'absence': _("Absence"), None: '☐'}
        headers = [_("Teacher"), _("Department"), _("Contract"), _("Activity"), _("Group"), _("Classroom code"),
                   _("Classroom"), _("Expected students"), _("Students present"), _("Attendance"), _("Arrival time"),
                   _("Remarks")]
        centred = {5, 7, 8, 9, 10}
        for area, periods, teachers in areas:
            sheet = workbook.add_worksheet(_sheet_name(area.name, _('By period')))
            sheet.set_landscape()
            sheet.fit_to_pages(1, 0)
            sheet.set_paper(9)
            for column, width in enumerate((30, 22, 14, 44, 12, 9, 14, 10, 10, 9, 13, 30)):
                sheet.set_column(column, column, width)
            last = len(headers) - 1
            sheet.merge_range(0, 0, 0, last, _("Walkout %(day)s - %(area)s: each teacher once, in their first period",
                                               day=day, area=area.name), formats['title'])
            sheet.merge_range(1, 0, 1, last, _(
                "From the schedules in EMS, as on the guard duty board. Grey: an absence request covers it. "
                "Expected students: the class's roll-call list, or its group's students; empty when unknown."),
                formats['note'])
            sheet.merge_range(2, 0, 2, last, _(
                "Attendance as at %(time)s: present once checked in, on walkout when their first period has "
                "started without it; students present as the roll call was taken, empty if not taken yet.",
                time=self.env['ems.datetime_utils'].get_local_datetime().strftime('%d/%m/%Y %H:%M')),
                formats['note'])
            contracts = sorted({teacher['contract'] for teacher in teachers}, key=lambda contract: (not contract, contract))
            row = 4
            first_row = row + 2
            counted = []
            for period in periods:
                starting = [teacher for teacher in teachers if teacher['start'] == period]
                if not starting:
                    continue
                sheet.merge_range(row, 0, row, last, _("%(period)s - %(count)s teacher(s) start",
                                                       period=label(period), count=len(starting)), formats['block'])
                sheet.write_row(row + 1, 0, headers, formats['header'])
                row += 2
                sheet.data_validation(row, ATTENDANCE_COLUMN, row + len(starting) - 1, ATTENDANCE_COLUMN, {
                    'validate': 'list', 'source': [statuses[status] for status in SUMMARY_STATUSES] + ['☐']})
                counted += starting
                self._write_control_sheet_summary(
                    sheet, formats, contracts, statuses, counted, first_row, row + len(starting) - 1)
                for teacher in starting:
                    cell = teacher['first']
                    kind = 'absent' if teacher['absence'] else ('cell' if cell['teaching'] else 'duty')
                    arrival = teacher['arrival']
                    values = [teacher['name'], teacher['department'], teacher['contract'], cell['activity'],
                              cell['groups'], cell['room_code'], cell['room'], cell['students'], cell['present'],
                              statuses[teacher['status']], format_time(arrival) if arrival is not None else '',
                              absence_notes.get(teacher['absence'], '')]
                    for column, value in enumerate(values):
                        style = formats[f'{kind}_centre' if column in centred else kind]
                        sheet.write(row, column, '' if value is None else value, style)
                    row += 1
                row += 1
            self._write_control_sheet_grid(workbook, formats, area, periods, teachers, label)
        workbook.close()
        return stream.getvalue()

    @staticmethod
    def _write_control_sheet_summary(sheet, formats, contracts, statuses, counted, first_row, last_row):
        """Beside a period's block, from column N and ending on its last row: for each contract type,
        how many teachers are on walkout, present or absent so far (every block up to this one).
        Formulas over the Contract and Attendance columns, so the figures follow what is filled in by
        hand; their cached values are the ones known now, for whatever opens the file without
        recalculating."""
        short = {'walkout': _("Walkout"), 'present': _("Pres."), 'absence': _("Abs.")}
        for index, contract in enumerate(contracts):
            column = SUMMARY_COLUMN + index * len(SUMMARY_STATUSES)
            title = contract or _("No contract")
            sheet.merge_range(last_row - 2, column, last_row - 2, column + len(SUMMARY_STATUSES) - 1, title,
                              formats['header_centre'])
            for offset, status in enumerate(SUMMARY_STATUSES):
                sheet.write(last_row - 1, column + offset, f"{title[:1]}-{short[status]}", formats['header_centre'])
                criteria = (contract or '').replace('"', '""')
                label = statuses[status].replace('"', '""')
                contract_range = xl_range_abs(first_row, CONTRACT_COLUMN, last_row, CONTRACT_COLUMN)
                attendance_range = xl_range_abs(first_row, ATTENDANCE_COLUMN, last_row, ATTENDANCE_COLUMN)
                value = sum(1 for teacher in counted
                            if teacher['contract'] == contract and teacher['status'] == status)
                sheet.write_formula(
                    last_row, column + offset,
                    f'=COUNTIFS({contract_range},"{criteria}",{attendance_range},"{label}")',
                    formats['cell_centre'], value)
            sheet.set_column(column, column + len(SUMMARY_STATUSES) - 1, 9)

    @staticmethod
    def _students_label(cell):
        """'(present/expected)' once the roll call is taken, '(expected)' before, '' when unknown."""
        expected = '?' if cell['students'] is None else cell['students']
        if cell['present'] is not None:
            return f"({cell['present']}/{expected})"
        return f"({expected})" if cell['students'] is not None else ''

    def _write_control_sheet_grid(self, workbook, formats, area, periods, teachers, label):
        """Every teacher of `area` by period, like the guard duty board: the group (with its
        students, see _students_label, and room code) or the duty, and a box to tick."""
        sheet = workbook.add_worksheet(_sheet_name(area.name, _('Grid')))
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_paper(9)
        sheet.repeat_rows(0)
        sheet.freeze_panes(1, 4)
        sheet.write_row(0, 0, [_("Teacher"), _("Department"), _("Contract"), _("Expected arrival")]
                        + [label(period) for period in periods], formats['grid_header'])
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 3, 12)
        sheet.set_column(4, 3 + len(periods), 12)
        for row, teacher in enumerate(sorted(teachers, key=lambda entry: entry['name']), start=1):
            sheet.set_row(row, 30)
            style = 'absent' if teacher['absence'] else 'cell'
            for column, value in enumerate((teacher['name'], teacher['department'], teacher['contract'],
                                            label(teacher['start'])[:5])):
                sheet.write(row, column, value, formats[style])
            for column, period in enumerate(periods, start=4):
                cell = teacher['grid'].get(period)
                kind = 'cell'
                text = ''
                if cell:
                    kind = 'absent' if period in teacher['absent'] else ('cell' if cell['teaching'] else 'duty')
                    text = cell['activity'] if not cell['groups'] else ' '.join(filter(None, (
                        cell['groups'], self._students_label(cell), cell['room_code'])))
                    if kind != 'absent':
                        text += '\n☐'
                sheet.write(row, column, text, formats[f'{kind}_centre'])
