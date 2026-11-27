# -*- coding: utf-8 -*-

import base64
import io
from datetime import date
from unittest.mock import patch

import openpyxl

from odoo.tests.common import TransactionCase

from .common import (
    create_absence, create_level_study, create_role_user, make_working_day, mock_outgoing_email, next_student_id,
    shift_ems_clock)


class TestStaffWalkoutControlSheet(TransactionCase):
    """Issue #865: the walkout control sheet, an .xlsx of every teacher of a teaching area once, in
    the first period of their schedule that day, with what they have then, to print and fill in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.day = shift_ems_clock(cls, hour=10.0, weekdays=(0, 1, 2, 3, 4)).date()
        make_working_day(cls, cls.day)
        Department = cls.env['hr.department']
        cls.area = Department.create({'name': 'TWCS / Area', 'is_top_level': True, 'top_level_area': 'academic'})
        cls.department = Department.create({'name': 'TWCS Department', 'parent_id': cls.area.id})
        cls.other_area = Department.create({'name': 'TWCS Other Area', 'is_top_level': True, 'top_level_area': 'academic'})
        cls.contract = cls.env['hr.contract.type'].create({'name': 'TWCS Interim'})
        level, study = create_level_study(cls, 'TWCS')
        cls.group, cls.split = cls.env['ems.group'].create([
            {'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id},
            {'group_type': 'reinforcement', 'name': 'TWCS split'}])
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWCS1', 'acronym': 'TWCS1', 'name': 'TWCS Subject', 'study_ids': [(4, study.id)]})
        students = cls.env['res.partner'].create([
            {'name': f'TWCS Student {index}', 'contact_type': 'student', 'student_id': next_student_id(),
             'main_group_id': cls.group.id} for index in range(3)])
        # Two of the group's three students take the subject: the roll-call list has them.
        cls.env['ems.enrollment'].create([
            {'student_id': student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id} for student in students[:2]])
        cls.space = cls.env['ems.space'].create({'name': 'TWCS Room', 'code': 'TWCS-9.19'})
        cls.guard = cls.env.ref('ems.non_teaching_g')
        cls.member = create_role_user(cls, 'head_of_studies', 'test_twcs_hos')

    @classmethod
    def _teacher(cls, name, slots, department=None, **values):
        """A teacher of `department` (the area's own by default) with `slots` on the sheet's day:
        (hour_from, hour_to, extra values) each."""
        teacher = cls.env['hr.employee'].create({
            'name': name, 'employee_type': 'teacher', 'department_id': (department or cls.department).id, **values})
        teacher.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': name, 'employee_id': teacher.id,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'name': f'{name} {start}', 'dayofweek': str(cls.day.weekday()), 'hour_from': start,
                        'hour_to': stop, **extra}) for start, stop, extra in slots],
        })
        return teacher

    def _class(self, groups, with_list=False):
        values = {'subject_id': self.subject.id, 'group_ids': [(6, 0, groups.ids)], 'space_id': self.space.id}
        if with_list:
            template = self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, self.env['hr.employee'].create({'name': 'TWCS List Teacher'}).ids)],
                'subject_id': self.subject.id, 'group_ids': [(6, 0, groups.ids)],
                'study_ids': [(6, 0, self.group.study_id.ids)],
                'start_date': date(2020, 1, 1), 'end_date': date(2035, 12, 31)})
            schedule = self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template.id, 'weekday': str(self.day.weekday()),
                'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id})
            # What every calendar resync does to its new lines: the list from the enrollments.
            schedule.fill_students()
            values['attendance_schedule_id'] = schedule.id
        return values

    def _report(self, area=None, day=None):
        return self.env['ems.staff_walkout_report'].with_user(self.member).create(
            {'date': day or self.day, 'area_id': (area or self.area).id})

    def _sheet(self, area=None):
        """`{teacher name: entry}` of `area`'s sheet (see _get_control_sheet_teacher)."""
        areas = self._report(area)._get_control_sheet_areas()
        self.assertEqual(len(areas), 1)
        return {entry['name']: entry for entry in areas[0][2]}

    def test_each_teacher_once_in_their_first_period_with_what_they_have_then(self):
        self._teacher('TWCS Early', [(8.0, 9.0, {'non_teaching': self.guard.id}), (9.0, 10.0, self._class(self.group))],
                              contract_type_id=self.contract.id)
        self._teacher('TWCS Late', [(11.0, 12.0, self._class(self.group))])

        sheet = self._sheet()

        self.assertEqual({name: entry['start'] for name, entry in sheet.items()},
                         {'TWCS Early': (8.0, 9.0), 'TWCS Late': (11.0, 12.0)})
        first = sheet['TWCS Early']
        self.assertEqual((first['contract'], first['department']), ('TWCS Interim', 'TWCS Department'))
        self.assertEqual(first['first']['activity'], self.guard.name)
        self.assertFalse(first['first']['teaching'])
        # The grid keeps every period of their day, the class with its group and room.
        lesson = first['grid'][(9.0, 10.0)]
        self.assertEqual((lesson['groups'], lesson['room_code'], lesson['room']), (self.group.name, 'TWCS-9.19', 'TWCS Room'))

    def test_a_period_of_a_teacher_cut_short_folds_into_the_whole_one(self):
        self._teacher('TWCS Short', [(9.0, 9.5, self._class(self.group))])
        self._teacher('TWCS Whole', [(9.0, 10.0, self._class(self.group))])

        sheet = self._sheet()

        self.assertEqual({entry['start'] for entry in sheet.values()}, {(9.0, 10.0)})

    def test_expected_students_come_from_the_class_list_then_the_main_group(self):
        self._teacher('TWCS Listed', [(9.0, 10.0, self._class(self.group, with_list=True))])
        self._teacher('TWCS Group', [(9.0, 10.0, self._class(self.group))])
        self._teacher('TWCS Split', [(9.0, 10.0, self._class(self.split))])

        sheet = self._sheet()

        self.assertEqual({name: entry['first']['students'] for name, entry in sheet.items()},
                         {'TWCS Listed': 2, 'TWCS Group': 3, 'TWCS Split': None})

    def test_an_absence_request_on_the_first_period_marks_the_teacher(self):
        approved = self._teacher('TWCS Approved', [(9.0, 10.0, self._class(self.group))])
        pending = self._teacher('TWCS Pending', [(9.0, 10.0, self._class(self.group))])
        later = self._teacher('TWCS Later', [(9.0, 10.0, self._class(self.group)), (11.0, 12.0, self._class(self.group))])
        create_absence(self.env, approved, self.day)
        create_absence(self.env, pending, self.day, approve=False)
        create_absence(self.env, later, self.day, 11.0, 12.0)

        sheet = self._sheet()

        self.assertEqual({name: entry['absence'] for name, entry in sheet.items()},
                         {'TWCS Approved': 'approved', 'TWCS Pending': 'pending', 'TWCS Later': False})
        self.assertEqual(sheet['TWCS Later']['absent'], {(11.0, 12.0)})

    def test_the_teachers_attendance_so_far(self):
        """10:00 (shift_ems_clock): present once checked in, at whatever time; on walkout when the
        first period has started without it; nothing yet for a later period or a day to come."""
        came = self._teacher('TWCS Came', [(9.0, 10.0, self._class(self.group))])
        self._teacher('TWCS Walker', [(9.0, 10.0, self._class(self.group))])
        self._teacher('TWCS Later', [(11.0, 12.0, self._class(self.group))])
        away = self._teacher('TWCS Away', [(9.0, 10.0, self._class(self.group))])
        create_absence(self.env, away, self.day)
        Pending = self.env['ems.absence_pending']
        self.env['hr.attendance'].create({
            'employee_id': came.id, 'check_in': Pending._utc_bounds(self.day, 0.0, 9.25)[1]})

        sheet = self._sheet()

        self.assertEqual({name: entry['status'] for name, entry in sheet.items()}, {
            'TWCS Came': 'present', 'TWCS Walker': 'walkout', 'TWCS Later': None, 'TWCS Away': 'absence'})
        self.assertAlmostEqual(sheet['TWCS Came']['arrival'], 9.25)
        # A day to come: nothing has started.
        self.assertIsNone(self.env['ems.staff_walkout_report']._get_teacher_status(False, None, (8.0, 9.0), -1.0))

    def test_the_students_present_come_from_the_roll_call_taken(self):
        values = self._class(self.group, with_list=True)
        self._teacher('TWCS Roll Call', [(9.0, 10.0, values)])
        self.assertIsNone(self._sheet()['TWCS Roll Call']['first']['present'])
        schedule = self.env['ems.attendance_schedule'].browse(values['attendance_schedule_id'])
        # Starting the roll call fills it with the list, each student as attended until marked.
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': self.day, 'mode': 'manual',
            'session_teacher_id': schedule.attendance_template_id.teacher_ids[:1].id})
        self.assertEqual(len(session.attendance_session_line_ids), 2)
        session.attendance_session_line_ids[:1].status_id = self.env.ref('ems.attendance_status_miss')

        cell = self._sheet()['TWCS Roll Call']['first']
        self.assertEqual((cell['present'], cell['students']), (1, 2))
        self.assertEqual(self.env['ems.staff_walkout_report']._students_label(cell), '(1/2)')

    def test_only_the_areas_own_teachers_and_never_a_vacancy(self):
        self._teacher('TWCS Mine', [(9.0, 10.0, self._class(self.group))])
        self._teacher('TWCS Vacancy', [(9.0, 10.0, self._class(self.group))], schedule_import_code='TWCS-V1')
        self._teacher('TWCS Other', [(9.0, 10.0, self._class(self.group))],
                      department=self.env['hr.department'].create({'name': 'TWCS Other Department',
                                                                   'parent_id': self.other_area.id}))

        self.assertEqual(set(self._sheet()), {'TWCS Mine'})
        self.assertEqual(set(self._sheet(self.other_area)), {'TWCS Other'})

    def test_the_download_is_an_xlsx_with_two_sheets_per_area(self):
        self._teacher('TWCS Mine', [(9.0, 10.0, self._class(self.group))])
        report = self._report()

        action = report.action_download_control_sheet()

        self.assertEqual((action['type'], action['target']), ('ir.actions.act_url', 'download'))
        self.assertIn(f'id={report.id}&field=control_sheet', action['url'])
        workbook = openpyxl.load_workbook(io.BytesIO(base64.b64decode(report.control_sheet)))
        # '/' is no character for a worksheet's name.
        self.assertEqual(workbook.sheetnames, ['TWCS - Area - By period', 'TWCS - Area - Grid'])
        rows = list(workbook['TWCS - Area - By period'].iter_rows(values_only=True))
        teacher_row = next(row for row in rows if row[0] == 'TWCS Mine')
        # 10:00, their 9:00 class started and no check-in: on walkout; no roll call taken yet.
        self.assertEqual(teacher_row[4:11], (self.group.name, 'TWCS-9.19', 'TWCS Room', 3, None, 'On walkout', None))
        self.assertTrue(report.control_sheet_name.endswith(f'{self.day.isoformat()}.xlsx'))

    def test_each_period_ends_with_the_figures_so_far_per_contract_type(self):
        """Issue #865: beside each block, from column N, on walkout / present / absent per contract type,
        counting every block up to it, as formulas over the Contract and Attendance columns."""
        came = self._teacher('TWCS Early Came', [(8.0, 9.0, self._class(self.group))], contract_type_id=self.contract.id)
        self._teacher('TWCS Late Walker', [(9.0, 10.0, self._class(self.group))], contract_type_id=self.contract.id)
        self._teacher('TWCS Loose', [(9.0, 10.0, self._class(self.group))])
        self.env['hr.attendance'].create({
            'employee_id': came.id, 'check_in': self.env['ems.absence_pending']._utc_bounds(self.day, 0.0, 7.9)[1]})
        report = self._report()
        report.action_download_control_sheet()
        content = io.BytesIO(base64.b64decode(report.control_sheet))
        formulas = openpyxl.load_workbook(content)['TWCS - Area - By period']
        cached = openpyxl.load_workbook(content, data_only=True)['TWCS - Area - By period']
        first = next(row[0].row for row in formulas.iter_rows() if row[0].value == 'TWCS Early Came')
        last = next(row[0].row for row in formulas.iter_rows() if row[0].value == 'TWCS Loose')

        # The 9:00 block's summary ends on its last row, under a heading saying the figures are
        # cumulative: Interim, then the teachers with no contract.
        self.assertEqual(formulas.cell(last - 3, 14).value, 'Cumulative figures')
        self.assertEqual([formulas.cell(last - 2, column).value for column in (14, 17)], ['TWCS Interim', 'No contract'])
        self.assertEqual([formulas.cell(last - 1, column).value for column in range(14, 17)],
                         ['T-Walkout', 'T-Pres.', 'T-Abs.'])
        self.assertEqual(formulas.cell(last, 15).value,
                         f'=COUNTIFS($C${first}:$C${last},"TWCS Interim",$J${first}:$J${last},"Present")')
        self.assertEqual([cached.cell(last, column).value for column in range(14, 20)], [1, 1, 0, 1, 0, 0])
        # The 8:00 block only counts itself.
        self.assertEqual([cached.cell(first, column).value for column in range(14, 17)], [0, 1, 0])
        self.assertEqual(formulas.cell(first, 10).value, 'Present')

    def test_every_area_adds_a_total_sheet_with_the_figures_so_far_of_the_whole_staff(self):
        """Issue #865: with every area, a first "Total" sheet has every period of every area, each with
        the figures of every teacher who starts by then, added up from the areas' own sheets."""
        other_department = self.env['hr.department'].create(
            {'name': 'TWCS Other Department', 'parent_id': self.other_area.id})
        self._teacher('TWCS Early', [(8.0, 9.0, self._class(self.group))], contract_type_id=self.contract.id)
        self._teacher('TWCS Other Late', [(9.5, 10.5, self._class(self.group))], department=other_department,
                      contract_type_id=self.contract.id)
        report = self.env['ems.staff_walkout_report'].with_user(self.member).create({'date': self.day})
        # Only the fixture's areas: the database may have teaching areas of its own.
        areas = [entry for entry in report._get_control_sheet_areas()
                 if entry[0] in self.area | self.other_area]
        with patch.object(type(report), '_get_control_sheet_areas', return_value=areas):
            report.action_download_control_sheet()
        content = io.BytesIO(base64.b64decode(report.control_sheet))
        workbook = openpyxl.load_workbook(content)
        self.assertEqual(workbook.sheetnames[0], 'Total')
        formulas = workbook['Total']
        cached = openpyxl.load_workbook(content, data_only=True)['Total']
        blocks = {formulas.cell(row, 1).value: row for row in range(1, formulas.max_row + 1)
                  if formulas.cell(row, 1).value in ('08:00-09:00', '09:30-10:30')}

        self.assertEqual(set(blocks), {'08:00-09:00', '09:30-10:30'})
        early, late = blocks['08:00-09:00'], blocks['09:30-10:30']
        self.assertEqual(formulas.cell(early + 1, 1).value, 'Cumulative figures')
        self.assertEqual(formulas.cell(early + 2, 1).value, 'TWCS Interim')
        # At 8:00 only this area's teacher counts; at 9:30, both areas' (on walkout, at 10:00).
        self.assertEqual(formulas.cell(early + 4, 1).value,
                         """=COUNTIFS('TWCS - Area - By period'!$C$7,"TWCS Interim","""
                         """'TWCS - Area - By period'!$J$7,"On walkout")""")
        self.assertEqual(cached.cell(early + 4, 1).value, 1)
        self.assertIn("+COUNTIFS('TWCS Other Area - By period'!", formulas.cell(late + 4, 1).value)
        self.assertEqual(cached.cell(late + 4, 1).value, 2)

    def test_nobody_scheduled_in_the_area_says_so(self):
        with self.assertRaisesRegex(Exception, 'has a schedule on this day'):
            self._report(self.other_area)._get_control_sheet_areas()

    def test_the_time_off_officers_reach_the_report_like_the_other_reports(self):
        menus = self.env['ir.ui.menu']
        report = self.env.ref('ems.menu_staff_walkout_report').id
        self.assertIn(report, menus.with_user(self.member)._visible_menu_ids())
        for role in ('teacher', 'secretary'):
            user = create_role_user(self, role, f'test_twcs_{role}')
            self.assertNotIn(report, menus.with_user(user)._visible_menu_ids(), role)
