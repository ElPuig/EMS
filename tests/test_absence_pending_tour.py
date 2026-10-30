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
        # Issue #707: only once their Head of Studies asks them to justify it.
        absence.with_user(self.head_of_studies).action_request_justification()
        self.start_tour(f"/odoo/ems.absence_pending/{absence.id}", "ems_absence_pending_teacher",
                        login=self.teacher_user.login)

    def test_head_of_studies_reviews_detected_absences_tour(self):
        """Issue #707: the reviewer, the teacher's Head of Studies (the least-privileged role that
        reviews). Five teachers of their branch, each with a detected absence of yesterday."""
        # Approving the absence it creates posts as them: like any real user, they have an email.
        self.head_of_studies.email = 'review.hos@example.com'
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        for letter in 'ABCDE':
            teacher = self.env['hr.employee'].create({
                'name': f'Review Teacher {letter}', 'employee_type': 'teacher',
                'parent_id': self.teacher.parent_id.id})
            Pending.create({
                'employee_id': teacher.id, 'origin': 'check_in',
                'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 11.0)[1],
            })
        self.start_tour("/odoo", "ems_absence_pending_review", login=self.head_of_studies.login)
