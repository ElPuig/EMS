from odoo.tests import HttpCase, tagged

from .common import create_role_employee, create_role_user, mock_outgoing_email, next_student_id
from .test_convalidation import create_convalidation_fixtures


@tagged('post_install', '-at_install')
class TestConvalidationTutorTour(HttpCase):
    """Issue #864 - what a tutor finds: the convalidations of their tutees (from the student's
    form and from the menu), shown as the student sees them, and the strike deletion. Logic and
    permissions are covered by test_convalidation.py and test_strike.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_convalidation_fixtures(cls)
        cls.tutor = create_role_user(cls, 'tutor', 'test_convalidation_tutor_tour', name='Convalidation Tutor')
        cls.group.tutor_id = create_role_employee(cls, cls.tutor)
        cls.request = cls.env['ems.convalidation'].create({
            'student_id': cls.student.id, 'study_id': cls.study.id, 'course_id': cls.course.id,
            'line_ids': [(0, 0, {'subject_id': cls.subject.id})],
        })
        cls.request.line_ids.write({'state': 'granted'})
        cls.request.sudo().action_propose()
        cls.request.sudo().action_resolve()
        cls.without_requests = cls.student.copy({
            'name': 'Convalidation Student Without Requests', 'student_id': next_student_id(),
            'email': 'convalidation.student.none@example.com', 'main_group_id': cls.group.id})

    def test_student_form_button_and_summary(self):
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_convalidation_tutor_student",
                        login=self.tutor.login)

    def test_student_form_button_counts_zero(self):
        self.start_tour(f"/odoo/res.partner/{self.without_requests.id}", "ems_convalidation_tutor_zero",
                        login=self.tutor.login)

    def test_menu_lists_the_tutees_requests(self):
        self.start_tour("/odoo", "ems_convalidation_tutor_menu", login=self.tutor.login)

    def test_tutor_deletes_a_strike_of_their_tutee(self):
        teacher_employee = self.teacher.employee_ids[:1]
        strike = self.env['ems.strike'].create({
            'student_id': self.student.id, 'teacher_id': teacher_employee.id,
            'reason_id': self.env.ref('ems.strike_reason_other').id})
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_strike_tutor_delete",
                        login=self.tutor.login)
        self.assertFalse(strike.exists())
