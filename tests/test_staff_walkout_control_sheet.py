# -*- coding: utf-8 -*-

import base64
import io
from datetime import date

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
        cls.member = create_role_user(cls, 'management_team', 'test_twcs_member')

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
        self.assertEqual(teacher_row[4:10], (self.group.name, 'TWCS-9.19', 'TWCS Room', 3, None, '☐'))
        self.assertTrue(report.control_sheet_name.endswith(f'{self.day.isoformat()}.xlsx'))

    def test_nobody_scheduled_in_the_area_says_so(self):
        with self.assertRaisesRegex(Exception, 'has a schedule on this day'):
            self._report(self.other_area)._get_control_sheet_areas()

    def test_a_member_of_the_management_team_reaches_the_report_but_not_the_other_reports(self):
        secretary = create_role_user(self, 'secretary', 'test_twcs_secretary')
        secretary.groups_id |= self.env.ref('ems.group_management_team')
        visible = self.env['ir.ui.menu'].with_user(secretary)._visible_menu_ids()
        self.assertIn(self.env.ref('ems.menu_staff_walkout_report').id, visible)
        self.assertIn(self.env.ref('hr_holidays.menu_hr_holidays_report').id, visible)
        for xmlid in ('hr_holidays.menu_hr_available_holidays_report_tree', 'hr_holidays.menu_hr_holidays_summary_all',
                      'ems.menu_absence_monthly_report'):
            self.assertNotIn(self.env.ref(xmlid).id, visible, xmlid)
        # Without the group, the Secretary does not see the report.
        plain = create_role_user(self, 'secretary', 'test_twcs_plain_secretary')
        self.assertNotIn(self.env.ref('ems.menu_staff_walkout_report').id,
                         self.env['ir.ui.menu'].with_user(plain)._visible_menu_ids())

    def test_the_director_belongs_to_the_management_team(self):
        director = create_role_user(self, 'director', 'test_twcs_director')
        self.assertTrue(director.has_group('ems.group_management_team'))
