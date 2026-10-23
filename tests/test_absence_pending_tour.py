# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestAbsencePendingTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = create_role_user(cls, 'teacher', 'absence_pending_tour_teacher')
        cls.teacher = teacher = create_role_employee(cls, cls.teacher_user, name='Tour Pending Teacher')
        # The least-privileged role with access: the teacher's own Department Chief (issue #604),
        # logging in as themselves (see rule_absence_pending_hierarchy).
        create_head_of_studies_branch(cls, 'APT', teacher)

    def test_absence_pending_tour(self):
        self.start_tour("/odoo", "ems_absence_pending", login=self.department_chief.login)

    def test_teacher_requests_their_detected_absence_tour(self):
        """Issue #696: the least-privileged reader, the teacher themselves, from the reminder's
        link (the record's own URL)."""
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        absence = Pending.create({
            'employee_id': self.teacher.id, 'origin': 'check_in', 'note': 'Not for the teacher',
            'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 11.0)[1],
        })
        self.start_tour(f"/odoo/ems.absence_pending/{absence.id}", "ems_absence_pending_teacher",
                        login=self.teacher_user.login)
