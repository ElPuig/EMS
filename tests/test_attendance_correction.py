# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import fields
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
            'requested_check_in': 8.5,  # 08:30
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

    def test_default_requested_times_match_original(self):
        correction = self.env['ems.attendance_correction'].with_context(
            default_attendance_id=self.attendance.id
        ).with_user(self.teacher_user).new({})
        expected_check_in = correction.time_to_float(correction.utc_datetime_to_local(self.attendance.check_in).time())
        expected_check_out = correction.time_to_float(correction.utc_datetime_to_local(self.attendance.check_out).time())
        self.assertAlmostEqual(correction.requested_check_in, expected_check_in, places=4)
        self.assertAlmostEqual(correction.requested_check_out, expected_check_out, places=4)

    def test_default_requested_check_out_falls_back_to_schedule_when_open(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Schedule (Attendance Correction)',
            'attendance_ids': [(0, 0, {
                'name': 'Monday Morning',
                'dayofweek': '0',
                'hour_from': 8.0,
                'hour_to': 15.0,
            })],
        })
        self.teacher_employee.resource_calendar_id = calendar.id
        open_attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher_employee.id,
            'check_in': datetime(2026, 1, 12, 8, 0),  # also a Monday, no check_out yet
        })
        correction = self.env['ems.attendance_correction'].with_context(
            default_attendance_id=open_attendance.id
        ).with_user(self.teacher_user).new({})
        self.assertEqual(correction.requested_check_out, 15.0)

    def test_accept_applies_correction(self):
        original_check_in = self.attendance.check_in
        original_check_out = self.attendance.check_out
        correction = self._create_correction(
            self.teacher_user,
            requested_check_in=8.5,  # 08:30
            requested_check_out=16.5,  # 16:30
        )
        correction.with_user(self.hos_user).action_accept()
        self.assertEqual(correction.state, 'accepted')

        # The date must stay the same as the original attendance; only the time changes.
        self.assertEqual(
            correction.utc_datetime_to_local(self.attendance.check_in).date(),
            correction.utc_datetime_to_local(original_check_in).date(),
        )
        self.assertEqual(
            correction.time_to_float(correction.utc_datetime_to_local(self.attendance.check_in).time()),
            8.5,
        )
        self.assertEqual(
            correction.utc_datetime_to_local(self.attendance.check_out).date(),
            correction.utc_datetime_to_local(original_check_out).date(),
        )
        self.assertEqual(
            correction.time_to_float(correction.utc_datetime_to_local(self.attendance.check_out).time()),
            16.5,
        )
        self.assertEqual(correction.approver_id, self.hos_user)
        self.assertTrue(correction.decision_date)

    def test_create_via_default_attendance_id_context_snapshots_originals(self):
        # The real "Request Correction" button flow never sends attendance_id explicitly -
        # the field is readonly="1" in the form (views/attendance/attendance_correction/form.xml)
        # and only ever gets populated via the button's default_attendance_id context
        # (views/attendance/attendance_correction/hr_attendance_form.xml). Odoo only merges
        # context defaults into vals inside the base create() (_add_missing_default_values,
        # called from _prepare_create_values) - which runs AFTER this model's own create()
        # override. If the override reads vals.get("attendance_id") assuming it's already
        # there, it browses an empty recordset and silently snapshots original_check_in/out
        # as False - reproduced by simulating exactly what the client sends: no attendance_id
        # key in vals at all, only the context default (confirmed against the real browser
        # flow via test_attendance_correction_request_tour.py).
        correction = self.env['ems.attendance_correction'].with_context(
            default_attendance_id=self.attendance.id
        ).with_user(self.teacher_user).create({
            'reason': 'Forgot to check in on time.',
            'requested_check_in': 8.5,  # 08:30
        })
        self.assertEqual(correction.attendance_id, self.attendance)
        self.assertEqual(correction.original_check_in, self.attendance.check_in)
        self.assertEqual(correction.original_check_out, self.attendance.check_out)

        correction.with_user(self.hos_user).action_accept()
        self.assertEqual(correction.state, 'accepted')
        self.assertEqual(
            correction.time_to_float(correction.utc_datetime_to_local(self.attendance.check_in).time()),
            8.5,
        )

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
        # Deadline must not default to "today" (see attendance_correction.py's
        # APPROVAL_ACTIVITY_DEADLINE_DAYS) or the notification email reads as if
        # the request were already overdue on the day it was submitted.
        self.assertGreater(activities.date_deadline, fields.Date.context_today(correction))

    def test_requester_notified_on_decision(self):
        correction = self._create_correction(self.teacher_user)
        correction.with_user(self.hos_user).action_accept()
        messages = self.env['mail.message'].search([
            ('model', '=', 'ems.attendance_correction'),
            ('res_id', '=', correction.id),
            ('partner_ids', 'in', self.teacher_user.partner_id.ids),
        ])
        self.assertTrue(messages)

    def test_can_revise_decision_after_accept(self):
        correction = self._create_correction(self.teacher_user)
        correction.with_user(self.hos_user).action_accept()
        self.assertEqual(correction.state, 'accepted')
        self.assertNotEqual(self.attendance.check_in, correction.original_check_in)

        # The approver made a mistake and now rejects it instead: the attendance
        # must be restored to its original value.
        correction.with_user(self.hos_user).action_reject()
        self.assertEqual(correction.state, 'rejected')
        self.assertEqual(self.attendance.check_in, correction.original_check_in)

    def test_can_revise_decision_after_reject(self):
        correction = self._create_correction(self.teacher_user)
        correction.with_user(self.hos_user).action_reject()
        self.assertEqual(correction.state, 'rejected')
        self.assertEqual(self.attendance.check_in, correction.original_check_in)

        correction.with_user(self.hos_user).action_accept()
        self.assertEqual(correction.state, 'accepted')
        self.assertNotEqual(self.attendance.check_in, correction.original_check_in)

    def test_hr_attendance_correction_ids_and_count(self):
        correction = self._create_correction(self.teacher_user)
        self.assertIn(correction, self.attendance.correction_ids)
        self.assertEqual(self.attendance.correction_count, 1)

    def test_action_view_corrections_domain(self):
        correction = self._create_correction(self.teacher_user)
        action = self.attendance.action_view_corrections()
        self.assertEqual(action['domain'], [('attendance_id', '=', self.attendance.id)])
        self.assertIn(correction.id, self.env['ems.attendance_correction'].search(action['domain']).ids)
