from odoo.tests import HttpCase, tagged

from .test_enrollment_head_of_studies import create_enrollment_outside_any_chain
from .common import create_role_user


@tagged('post_install', '-at_install')
class TestEnrollmentHeadOfStudiesTour(HttpCase):
    """Issue #654: the Head of Studies reads every screen of Academic management > Enrollment
    and its Configuration section."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_enrollment_outside_any_chain(cls, 'HSET')
        cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_hos_enrollment_tour')

    def test_enrollments_tour(self):
        self.start_tour("/odoo/action-ems.action_ems_enrollments", "ems_enrollment_head_of_studies",
                        login=self.head_of_studies.login)

    def test_other_lists_tour(self):
        for action in ('ems.action_ems_applicants', 'ems.action_students_no_destination',
                       'ems.action_ems_enrollment_items', 'ems.action_ems_enrollment_template',
                       'ems.action_task_assignment'):
            with self.subTest(action=action):
                self.start_tour(f"/odoo/action-{action}", "ems_enrollment_head_of_studies_list",
                                login=self.head_of_studies.login)
