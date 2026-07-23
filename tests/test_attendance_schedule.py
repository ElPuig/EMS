# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestAttendanceScheduleAccess(TransactionCase):
    """Focused regression coverage for the ir.rule fix in security/rules/attendance.xml:
    a teacher who is session_teacher_id/template_teacher_ids on a session built from a
    schedule (e.g. covering a guard-duty/substitution session) must be able to read that
    schedule even when they are not one of the schedule's own template.teacher_ids —
    otherwise the session's own form (which shows attendance_schedule_id) raises an
    AccessError, even though the session itself is readable. This is not a full DTON pass
    on ems.attendance_schedule (no dedicated test file existed before); it covers only the
    access-rule behaviour touched by this fix."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.level = cls.env['ems.level'].create({'acronym': 'TASC', 'name': 'Test Level (Attendance Schedule)'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TASC001', 'acronym': 'TASC', 'name': 'Test Study (Attendance Schedule)',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TASC001', 'acronym': 'TASC', 'name': 'Test Subject (Attendance Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group_record = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASC', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Test Group (Attendance Schedule)',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TASC-A', 'name': 'Test Space (Attendance Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })

        cls.owner_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Owner Teacher (Attendance Schedule)', 'login': 'test_owner_teacher_asc',
            'email': 'test_owner_teacher_asc@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.owner_employee = cls.env['hr.employee'].create({
            'name': 'Test Owner Teacher Employee (Attendance Schedule)', 'employee_type': 'teacher',
            'user_id': cls.owner_user.id,
        })

        cls.substitute_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Substitute Teacher (Attendance Schedule)', 'login': 'test_substitute_teacher_asc',
            'email': 'test_substitute_teacher_asc@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.substitute_employee = cls.env['hr.employee'].create({
            'name': 'Test Substitute Teacher Employee (Attendance Schedule)', 'employee_type': 'teacher',
            'user_id': cls.substitute_user.id,
        })

        cls.unrelated_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Unrelated Teacher (Attendance Schedule)', 'login': 'test_unrelated_teacher_asc',
            'email': 'test_unrelated_teacher_asc@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Attendance Schedule)', 'login': 'test_admin_asc',
            'email': 'test_admin_asc@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.owner_employee.id])], 'level_id': cls.level.id, 'study_id': cls.study.id,
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group_record.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': '1',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        # A session covered by the substitute, not the template's own teacher — the scenario
        # that used to raise an AccessError when opening the session's own form.
        cls.substitute_session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'guard', 'session_teacher_id': cls.substitute_employee.id,
        })

    def test_template_teacher_can_read_schedule(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.owner_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertIn(self.schedule, schedule)

    def test_unrelated_teacher_cannot_read_schedule(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.unrelated_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertNotIn(self.schedule, schedule)

    def test_substitute_teacher_can_read_schedule_via_own_session(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.substitute_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertIn(self.schedule, schedule)

    def test_substitute_teacher_can_read_the_field_on_the_session_form(self):
        session = self.env['ems.attendance_session_header'].with_user(self.substitute_user).browse(
            self.substitute_session.id
        )
        # Reading attendance_schedule_id used to raise AccessError on ems.attendance_schedule.
        self.assertEqual(session.attendance_schedule_id, self.schedule)

    def test_substitute_teacher_cannot_write_schedule(self):
        schedule = self.schedule.with_user(self.substitute_user)
        with self.assertRaises(AccessError):
            schedule.write({'notes': 'Attempted edit.'})

    def test_admin_reads_all_schedules(self):
        schedule = self.env['ems.attendance_schedule'].with_user(self.admin_user).search(
            [('id', '=', self.schedule.id)]
        )
        self.assertIn(self.schedule, schedule)
