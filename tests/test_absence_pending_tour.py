# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestAbsencePendingTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'absence_pending_tour_teacher')
        cls.teacher = teacher = create_role_employee(cls, cls.teacher_user, name='Tour Pending Teacher')
        # The least-privileged role with access: the teacher's own Department Chief (issue #604),
        # logging in as themselves (see rule_absence_pending_hierarchy).
        create_head_of_studies_branch(cls, 'APT', teacher)

    def test_absence_pending_tour(self):
        self.start_tour("/odoo", "ems_absence_pending", login=self.department_chief.login)

    def _absence(self, employee, note=False):
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        return Pending.create({
            'employee_id': employee.id, 'origin': 'check_in', 'note': note,
            'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 11.0)[1],
        })

    def test_head_of_studies_reviews_detected_absences_tour(self):
        """Issue #707: the reviewer, the teachers' Head of Studies, in both view modes."""
        teachers = [self.env['hr.employee'].create({
            'name': name, 'employee_type': 'teacher', 'parent_id': self.teacher.parent_id.id,
        }) for name in ('Tour Review Teacher', 'Tour Review Second Teacher', 'Tour Review Third Teacher')]
        for teacher in teachers:
            self._absence(teacher)
        self.start_tour("/odoo", "ems_absence_pending_review", login=self.head_of_studies.login)

    def test_teacher_requests_their_detected_absence_tour(self):
        """Issue #696: the least-privileged reader, the teacher themselves, from the reminder's
        link (the record's own URL), once the Head of Studies has asked them (issue #707)."""
        absence = self._absence(self.teacher, note='Not for the teacher')
        absence.with_user(self.head_of_studies).action_request_justification()
        self.start_tour(f"/odoo/ems.absence_pending/{absence.id}", "ems_absence_pending_teacher",
                        login=self.teacher_user.login)
