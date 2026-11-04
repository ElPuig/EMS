from odoo.tests import HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestStudentCardTour(HttpCase):
    """Issue #524: a tutor (the least-privileged role that prints cards) finds "Print student card"
    on the students list, on their student's form and on their group's form, and not on another
    tutor's group."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_card_tour_tutor', name='TSCT Tutor')
        tutor = create_role_employee(cls, cls.tutor_user)
        other_tutor = create_role_employee(cls, create_role_user(
            cls, 'tutor', 'test_card_tour_other_tutor', name='TSCT Other Tutor'))
        __, __, cls.group = create_level_study_group(cls, 'TSCT', group={'tutor_id': tutor.id})
        __, __, cls.other_group = create_level_study_group(cls, 'TSCTO', group={'tutor_id': other_tutor.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'TSCT Own Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })

    def test_student_card_tours(self):
        login = self.tutor_user.login
        self.start_tour("/odoo", "ems_student_card_list", login=login)
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_student_card_student_form", login=login)
        self.start_tour(f"/odoo/ems.group/{self.group.id}", "ems_student_card_group_form", login=login)
        self.start_tour(f"/odoo/ems.group/{self.other_group.id}", "ems_student_card_foreign_group_form", login=login)
