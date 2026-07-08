# -*- coding: utf-8 -*-

from datetime import datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestAttendanceCorrection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_head_of_studies = cls.env.ref('ems.group_head_of_studies')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Attendance Correction)',
            'login': 'test_admin_attendance_correction',
            'email': 'test_admin_attendance_correction@example.com',
            'groups_id': [(4, cls.group_academic_admin.id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.hos_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HOS (Attendance Correction)',
            'login': 'test_hos_attendance_correction',
            'email': 'test_hos_attendance_correction@example.com',
            'groups_id': [(4, cls.group_head_of_studies.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.hos_employee = cls.env['hr.employee'].create({
            'name': 'Test HOS Employee (Attendance Correction)',
            'employee_type': 'teacher',
            'user_id': cls.hos_user.id,
        })

        cls.manager_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Middle Manager (Attendance Correction)',
            'login': 'test_manager_attendance_correction',
            'email': 'test_manager_attendance_correction@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.manager_employee = cls.env['hr.employee'].create({
            'name': 'Test Middle Manager Employee (Attendance Correction)',
            'employee_type': 'teacher',
            'user_id': cls.manager_user.id,
            'parent_id': cls.hos_employee.id,
        })

        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Attendance Correction)',
            'login': 'test_teacher_attendance_correction',
            'email': 'test_teacher_attendance_correction@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher Employee (Attendance Correction)',
            'employee_type': 'teacher',
            'user_id': cls.teacher_user.id,
            'parent_id': cls.manager_employee.id,
        })

        cls.other_teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Other Teacher (Attendance Correction)',
            'login': 'test_other_teacher_attendance_correction',
            'email': 'test_other_teacher_attendance_correction@example.com',
            'groups_id': [(4, cls.group_teacher.id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.other_teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher Employee (Attendance Correction)',
            'employee_type': 'teacher',
            'user_id': cls.other_teacher_user.id,
        })

        cls.attendance = cls.env['hr.attendance'].create({
            'employee_id': cls.teacher_employee.id,
            'check_in': datetime(2026, 1, 5, 8, 0),
            'check_out': datetime(2026, 1, 5, 16, 0),
        })

    def _create_correction(self, user, **values):
        vals = {
            'attendance_id': self.attendance.id,
            'reason': 'Forgot to check in on time.',
            'requested_check_in': datetime(2026, 1, 5, 8, 30),
        }
        vals.update(values)
        return self.env['ems.attendance_correction'].with_user(user).create(vals)

    def test_create_valid_correction(self):
        correction = self._create_correction(self.teacher_user)
        self.assertEqual(correction.state, 'pending')
        self.assertEqual(correction.employee_id, self.teacher_employee)

    def test_reason_required(self):
        with self.assertRaises(Exception):
            self._create_correction(self.teacher_user, reason=False)

    def test_at_least_one_requested_field_required(self):
        # NOTE: the DB-level check constraint fires before the ORM constrain, so a
        # plain Exception is expected here (see CLAUDE.md testing conventions).
        with self.assertRaises(Exception):
            self._create_correction(self.teacher_user, requested_check_in=False)

    def test_display_name(self):
        correction = self._create_correction(self.teacher_user)
        self.assertTrue(correction.display_name)
        self.assertIn(self.teacher_employee.name, correction.display_name)

    def test_admin_crud(self):
        correction = self._create_correction(self.admin_user)
        correction.with_user(self.admin_user).write({'reason': 'Updated reason.'})
        correction.with_user(self.admin_user).unlink()

    def test_teacher_cannot_read_others_requests(self):
        correction = self._create_correction(self.teacher_user)
        found = self.env['ems.attendance_correction'].with_user(self.other_teacher_user).search(
            [('id', '=', correction.id)]
        )
        self.assertFalse(found)

    def test_teacher_cannot_unlink(self):
        correction = self._create_correction(self.teacher_user)
        with self.assertRaises(AccessError):
            correction.with_user(self.teacher_user).unlink()

    def test_approver_resolution_immediate_manager(self):
        # manager_employee's direct manager (hos_employee) is in group_head_of_studies.
        approver = self.manager_employee.find_head_of_studies()
        self.assertEqual(approver, self.hos_employee)

    def test_approver_resolution_walks_chain(self):
        # teacher_employee -> manager_employee (not HOS) -> hos_employee (HOS).
        approver = self.teacher_employee.find_head_of_studies()
        self.assertEqual(approver, self.hos_employee)

    def test_approver_resolution_self_approval(self):
        approver = self.hos_employee.find_head_of_studies()
        self.assertEqual(approver, self.hos_employee)

    def test_approver_resolution_falls_through_to_admin(self):
        approver = self.other_teacher_employee.find_head_of_studies()
        self.assertFalse(approver)

    def test_accept_applies_correction(self):
        correction = self._create_correction(
            self.teacher_user,
            requested_check_in=datetime(2026, 1, 5, 8, 30),
            requested_check_out=datetime(2026, 1, 5, 16, 30),
        )
        correction.with_user(self.hos_user).action_accept()
        self.assertEqual(correction.state, 'accepted')
        self.assertEqual(self.attendance.check_in, datetime(2026, 1, 5, 8, 30))
        self.assertEqual(self.attendance.check_out, datetime(2026, 1, 5, 16, 30))
        self.assertEqual(correction.approver_id, self.hos_user)
        self.assertTrue(correction.decision_date)

    def test_reject_leaves_attendance_untouched(self):
        original_check_in = self.attendance.check_in
        correction = self._create_correction(self.teacher_user)
        correction.with_user(self.hos_user).action_reject()
        self.assertEqual(correction.state, 'rejected')
        self.assertEqual(self.attendance.check_in, original_check_in)

    def test_only_approver_can_accept_or_reject(self):
        correction = self._create_correction(self.teacher_user)
        with self.assertRaises(UserError):
            correction.with_user(self.other_teacher_user).action_accept()

    def test_notification_activity_scheduled_on_create(self):
        correction = self._create_correction(self.teacher_user)
        activity_type = self.env.ref('ems.mail_activity_attendance_correction')
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'ems.attendance_correction'),
            ('res_id', '=', correction.id),
            ('activity_type_id', '=', activity_type.id),
        ])
        self.assertEqual(activities.user_id, self.hos_user)

    def test_requester_notified_on_decision(self):
        correction = self._create_correction(self.teacher_user)
        correction.with_user(self.hos_user).action_accept()
        messages = self.env['mail.message'].search([
            ('model', '=', 'ems.attendance_correction'),
            ('res_id', '=', correction.id),
            ('partner_ids', 'in', self.teacher_user.partner_id.ids),
        ])
        self.assertTrue(messages)
