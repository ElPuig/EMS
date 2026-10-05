from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_enrollment_subject_group import create_subject_group_fixture


@tagged('post_install', '-at_install')
class TestEnrollmentSubjectGroupTour(HttpCase):
    """The Studies tab only offers the student's own study subjects, and a subject sold by
    another course's enrollment template lands in that course's group. See
    docs/en/developers/contacts/enrollment.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_subject_group_fixture(cls, 'TESGT')
        # Secretary: the least-privileged role allowed to add enrollment lines by hand
        # (ems.enrollment.default_get). create_role_user() sets 'lang': 'en_US', needed since
        # the tour asserts on the "Studies" tab label.
        create_role_user(cls, 'secretary', 'test_secretary_enrollment_subject_group_tour')

    def test_studies_tab_subject_domain_and_default_group_tour(self):
        self.start_tour("/odoo", "ems_enrollment_subject_group", login="test_secretary_enrollment_subject_group_tour")

        enrollment = self.env['ems.enrollment'].search([('student_id', '=', self.student.id)])
        self.assertEqual(enrollment.subject_id, self.subject_year1)
        self.assertEqual(enrollment.group_id, self.group_1a)
