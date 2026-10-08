# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestAbsencePendingTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        teacher = create_role_employee(
            cls, create_role_user(cls, 'teacher', 'absence_pending_tour_teacher'), name='Tour Pending Teacher')
        # The least-privileged role with access: the teacher's own Department Chief (issue #604),
        # logging in as themselves (see rule_absence_pending_hierarchy).
        create_head_of_studies_branch(cls, 'APT', teacher)

    def test_absence_pending_tour(self):
        self.start_tour("/odoo", "ems_absence_pending", login=self.department_chief.login)
