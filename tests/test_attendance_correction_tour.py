from datetime import datetime

from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestAttendanceCorrectionTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Attendance Correction Tour Teacher',
            'login': 'test_teacher_attendance_correction_tour',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Attendance Correction Tour Teacher',
            'employee_type': 'teacher', 'user_id': cls.teacher_user.id,
        })
        cls.attendance = cls.env['hr.attendance'].create({
            'employee_id': cls.teacher_employee.id,
            'check_in': datetime(2026, 1, 5, 8, 0),
            'check_out': datetime(2026, 1, 5, 16, 0),
        })
        cls.correction = cls.env['ems.attendance_correction'].create({
            'attendance_id': cls.attendance.id,
            'requested_check_in': 8.5,
            'reason': 'Tour: forgot to check in on time',
        })

    def test_attendance_correction_accept_tour(self):
        self.assertEqual(self.correction.state, 'pending')

        self.start_tour("/odoo", "ems_attendance_correction_accept", login="admin")

        self.assertEqual(self.correction.state, 'accepted')
        # requested_check_in=8.5 (08:30) is a local time - compare via the same
        # utc<->local conversion the model itself uses, not a hardcoded UTC value which
        # would only be correct for a company in the UTC timezone (see
        # test_attendance_correction.py's own assertions for the same pattern).
        self.assertEqual(
            self.correction.time_to_float(self.correction.utc_datetime_to_local(self.attendance.check_in).time()),
            8.5,
        )

    def test_attendance_correction_pending_filter_tour(self):
        # The tour asserts on literal English filter labels (Pending/Accepted/Rejected).
        force_user_language_to_english(self, self.env.ref('base.user_admin'))

        # Self-contained fixtures (not the class-level ones above, which the accept tour
        # mutates) - one request per state, distinguished by employee name so the tour
        # can assert on row presence/absence per state.
        for state, label in (('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')):
            employee = self.env['hr.employee'].create({
                'name': f'Filter Tour Teacher {label}', 'employee_type': 'teacher',
            })
            attendance = self.env['hr.attendance'].create({
                'employee_id': employee.id,
                'check_in': datetime(2026, 1, 6, 8, 0),
                'check_out': datetime(2026, 1, 6, 16, 0),
            })
            self.env['ems.attendance_correction'].create({
                'attendance_id': attendance.id,
                'requested_check_in': 8.5,
                'reason': f'Tour: {label} filter fixture',
                'state': state,
            })

        self.start_tour("/odoo", "ems_attendance_correction_pending_filter", login="admin", step_delay=300)
