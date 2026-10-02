from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_enrollment_slot import create_enrollment_slot_fixture


@tagged('post_install', '-at_install')
class TestEnrollmentSlotTour(HttpCase):
    """Issue #534: splitting a subject between two groups from the student's form. See
    docs/en/developers/contacts/enrollment_slot.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_enrollment_slot_fixture(cls)
        # Secretary: the least-privileged role that edits any student's enrollment.
        # create_role_user() sets 'lang': 'en_US' - the tour matches "Studies" and weekday names.
        create_role_user(cls, 'secretary', 'test_secretary_enrollment_slot_tour')

    def test_split_a_subject_between_two_groups_tour(self):
        self.start_tour("/odoo", "ems_enrollment_slot", login="test_secretary_enrollment_slot_tour")

        self.assertTrue(self.student.custom_schedule)
        lines = self.env['ems.attendance_schedule'].search([('student_ids', 'in', self.student.id)])
        self.assertEqual(lines, self.line_c_mon | self.line_d_wed)
