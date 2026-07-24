# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import TransactionCase


class TestAttendanceReportWizards(TransactionCase):
    """Covers the 3 attendance report wizards after their raw SQL (cr.execute) was replaced
    by ORM calls: the teacher-scoping filters (allowed_group_ids/allowed_student_ids/
    allowed_subject_ids) and the print() methods that fetch ems.attendance_session_line ids.
    Also covers two pre-existing bugs fixed in the same change: allowed_group_ids ignoring
    study_id, and allowed_subject_ids not actually scoping to the current teacher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.level = cls.env['ems.level'].create({'acronym': 'TARW', 'name': 'Test Level (Attendance Reports)'})
        cls.study1 = cls.env['ems.study'].create({
            'code': 'TARW001', 'acronym': 'TARW1', 'name': 'Test Study 1 (Attendance Reports)',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.study2 = cls.env['ems.study'].create({
            'code': 'TARW002', 'acronym': 'TARW2', 'name': 'Test Study 2 (Attendance Reports)',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.subject_a = cls.env['ems.subject'].create({
            'code': 'TARWA', 'acronym': 'TARWA', 'name': 'Test Subject A (Attendance Reports)',
            'study_ids': [(6, 0, [cls.study1.id, cls.study2.id])],
        })
        cls.subject_b = cls.env['ems.subject'].create({
            'code': 'TARWB', 'acronym': 'TARWB', 'name': 'Test Subject B (Attendance Reports)',
            'study_ids': [(6, 0, [cls.study1.id, cls.study2.id])],
        })
        cls.group1 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TARW1', 'level_id': cls.level.id, 'study_id': cls.study1.id,
            'name': 'Test Group 1 (Attendance Reports)',
        })
        cls.group2 = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TARW2', 'level_id': cls.level.id, 'study_id': cls.study2.id,
            'name': 'Test Group 2 (Attendance Reports)',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TARW-A', 'name': 'Test Space (Attendance Reports)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })

        cls.owner_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Owner Teacher (Attendance Reports)', 'login': 'test_owner_teacher_arw',
            'email': 'test_owner_teacher_arw@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.owner_employee = cls.env['hr.employee'].create({
            'name': 'Test Owner Teacher Employee (Attendance Reports)', 'employee_type': 'teacher',
            'user_id': cls.owner_user.id,
        })
        cls.other_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher (Attendance Reports)', 'login': 'test_other_teacher_arw',
            'email': 'test_other_teacher_arw@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.other_employee = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher Employee (Attendance Reports)', 'employee_type': 'teacher',
            'user_id': cls.other_user.id,
        })
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Attendance Reports)', 'login': 'test_admin_arw',
            'email': 'test_admin_arw@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })

        # owner teaches group1/subject_a and group2/subject_a; other teaches group1/subject_b.
        cls.env['ems.teaching'].create({
            'teacher_id': cls.owner_employee.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_a.id,
        })
        cls.env['ems.teaching'].create({
            'teacher_id': cls.owner_employee.id, 'group_id': cls.group2.id, 'subject_id': cls.subject_a.id,
        })
        cls.env['ems.teaching'].create({
            'teacher_id': cls.other_employee.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_b.id,
        })

        cls.student1 = cls.env['res.partner'].create({
            'name': 'Test Student 1 (Attendance Reports)', 'contact_type': 'student',
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Test Student 2 (Attendance Reports)', 'contact_type': 'student',
        })
        # student1 is enrolled in both subjects of group1; student2 only in subject_a.
        cls.env['ems.enrollment'].create({
            'student_id': cls.student1.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_a.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student1.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_b.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student2.id, 'group_id': cls.group1.id, 'subject_id': cls.subject_a.id,
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.owner_employee.id])], 'level_id': cls.level.id, 'study_id': cls.study1.id,
            'subject_id': cls.subject_a.id, 'group_ids': [(6, 0, [cls.group1.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        cls.status_attended = cls.env.ref('ems.attendance_status_attended')

        cls.today = date.today()
        cls.old_date = cls.today - timedelta(days=10)
        cls.session_recent = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': cls.today,
            'mode': 'manual', 'session_teacher_id': cls.owner_employee.id,
        })
        cls.session_old = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': cls.old_date,
            'mode': 'manual', 'session_teacher_id': cls.owner_employee.id,
        })
        cls.line_recent = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student1.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': cls.session_recent.id,
        })
        cls.line_old = cls.env['ems.attendance_session_line'].create({
            'student_id': cls.student1.id, 'status_id': cls.status_attended.id,
            'attendance_session_id': cls.session_old.id,
        })

    # --- allowed_group_ids: study_id filter (bug fix) -----------------

    def test_allowed_group_ids_filters_by_study(self):
        wizard = self.env['ems.attendance_report_group_wizard'].with_user(self.owner_user).create({
            'study_id': self.study1.id,
        })
        wizard._compute_allowed_group_ids()
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

        wizard.study_id = self.study2.id
        wizard._compute_allowed_group_ids()
        self.assertIn(self.group2, wizard.allowed_group_ids)
        self.assertNotIn(self.group1, wizard.allowed_group_ids)

    def test_allowed_group_ids_scoped_to_teacher(self):
        wizard = self.env['ems.attendance_report_group_wizard'].with_user(self.other_user).create({
            'study_id': self.study1.id,
        })
        wizard._compute_allowed_group_ids()
        # 'other' teaches group1/subject_b, not group2, and never teaches in study2 at all.
        self.assertIn(self.group1, wizard.allowed_group_ids)

        wizard.study_id = self.study2.id
        wizard._compute_allowed_group_ids()
        self.assertFalse(wizard.allowed_group_ids)

    def test_allowed_group_ids_admin_still_study_filtered(self):
        wizard = self.env['ems.attendance_report_group_wizard'].with_user(self.admin_user).create({
            'study_id': self.study1.id,
        })
        wizard._compute_allowed_group_ids()
        self.assertIn(self.group1, wizard.allowed_group_ids)
        self.assertNotIn(self.group2, wizard.allowed_group_ids)

    # --- allowed_subject_ids: teacher scoping (bug fix) ----------------

    def test_allowed_subject_ids_scoped_to_owner(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.owner_user).create({
            'group_id': self.group1.id, 'subject_id': self.subject_a.id,
        })
        wizard._compute_allowed_subject_ids()
        self.assertIn(self.subject_a, wizard.allowed_subject_ids)
        self.assertNotIn(self.subject_b, wizard.allowed_subject_ids)

    def test_allowed_subject_ids_scoped_to_other(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.other_user).create({
            'group_id': self.group1.id, 'subject_id': self.subject_b.id,
        })
        wizard._compute_allowed_subject_ids()
        self.assertIn(self.subject_b, wizard.allowed_subject_ids)
        self.assertNotIn(self.subject_a, wizard.allowed_subject_ids)

    def test_allowed_subject_ids_admin_sees_both(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].with_user(self.admin_user).create({
            'group_id': self.group1.id, 'subject_id': self.subject_a.id,
        })
        wizard._compute_allowed_subject_ids()
        self.assertIn(self.subject_a, wizard.allowed_subject_ids)
        self.assertIn(self.subject_b, wizard.allowed_subject_ids)

    # --- allowed_student_ids (already-correct logic, now via ORM) ------

    def test_allowed_student_ids_scoped_to_owner(self):
        wizard = self.env['ems.attendance_report_student_wizard'].with_user(self.owner_user).create({
            'group_id': self.group1.id, 'student_id': self.student1.id,
        })
        wizard._compute_allowed_student_ids()
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertIn(self.student2, wizard.allowed_student_ids)

    def test_allowed_student_ids_scoped_to_other(self):
        wizard = self.env['ems.attendance_report_student_wizard'].with_user(self.other_user).create({
            'group_id': self.group1.id, 'student_id': self.student1.id,
        })
        wizard._compute_allowed_student_ids()
        # 'other' only teaches subject_b in group1: student1 is enrolled there, student2 is not.
        self.assertIn(self.student1, wizard.allowed_student_ids)
        self.assertNotIn(self.student2, wizard.allowed_student_ids)

    # --- print(): ORM-fetched status_ids --------------------------------

    def test_print_group_wizard_returns_all_lines_in_range(self):
        wizard = self.env['ems.attendance_report_group_wizard'].create({
            'group_id': self.group1.id, 'from_date': self.old_date, 'to_date': self.today,
        })
        result = wizard.print()
        self.assertEqual(result['type'], 'ir.actions.report')
        self.assertEqual(sorted(result['data']['status_ids']), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_subject_wizard_returns_lines_for_subject(self):
        wizard = self.env['ems.attendance_report_subject_wizard'].create({
            'group_id': self.group1.id, 'subject_id': self.subject_a.id,
            'from_date': self.old_date, 'to_date': self.today,
        })
        result = wizard.print()
        self.assertEqual(sorted(result['data']['status_ids']), sorted([self.line_recent.id, self.line_old.id]))

    def test_print_student_wizard_filters_by_date_range(self):
        wizard = self.env['ems.attendance_report_student_wizard'].create({
            'group_id': self.group1.id, 'student_id': self.student1.id,
            'from_date': self.today - timedelta(days=2), 'to_date': self.today,
        })
        result = wizard.print()
        self.assertEqual(result['data']['status_ids'], [self.line_recent.id])
        self.assertNotIn(self.line_old.id, result['data']['status_ids'])

    # --- stored related fields (used by the 'Attendance reports' pivot/graph) ---

    def test_session_line_analysis_fields_follow_the_session(self):
        self.assertEqual(self.line_recent.date, self.today)
        self.assertEqual(self.line_recent.level_id, self.level)
        self.assertEqual(self.line_recent.study_id, self.study1)
        self.assertEqual(self.line_recent.subject_id, self.subject_a)

    def test_absence_rate_follows_status_category(self):
        self.assertEqual(self.line_recent.status_id.category, 'assistance')
        self.assertEqual(self.line_recent.absence_rate, 0.0)

        miss_status = self.env.ref('ems.attendance_status_miss')
        absent_line = self.env['ems.attendance_session_line'].create({
            'student_id': self.student1.id, 'status_id': miss_status.id,
            'attendance_session_id': self.session_recent.id,
        })
        self.assertEqual(absent_line.status_id.category, 'absence')
        self.assertEqual(absent_line.absence_rate, 100.0)

    # --- _get_report_values: docids is always None on the real report_action() call path ---

    def test_get_report_values_handles_none_docids(self):
        wizard = self.env['ems.attendance_report_group_wizard'].create({
            'group_id': self.group1.id, 'from_date': self.old_date, 'to_date': self.today,
        })
        data = {'doc_ids': [wizard.id], 'status_ids': [self.line_recent.id, self.line_old.id]}
        # report_action(None, data=data) never sets active_ids, so the controller always calls
        # _get_report_values with docids=None, not []: len(None) used to raise TypeError here.
        values = self.env['report.ems.attendance_report_group']._get_report_values(None, data=data)
        self.assertEqual(values['doc_ids'], [wizard.id])
        self.assertEqual(len(values['main'].overall), 2)
        self.assertIn(self.group1, self.line_recent.group_ids)
