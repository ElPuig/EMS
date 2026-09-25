import base64

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


class TestStudentBenefitAccess(TransactionCase):
    """Issue #511 follow-up: a student's bonifications and exemptions (family economic data) are
    read by admin, secretary, Head of Studies, guidance, coexistence and the student's own tutor
    scope - not by any other teacher, who only keeps the benefits badge (benefit_status, stored)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_benefit_access_tutor')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        create_head_of_studies_branch(cls, 'SBA', cls.tutor)
        __, __, group = create_level_study_group(cls, 'SBA', group={'tutor_id': cls.tutor.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'Benefit Access Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        cls.benefit = cls.env['ems.student.benefit'].create({
            'student_id': cls.student.id, 'benefit_type': 'scholarship',
            'document': base64.b64encode(b'%PDF-1.4 test'), 'document_name': 'test.pdf',
        })
        cls.readers = (
            cls.tutor_user, cls.department_chief,
            create_role_user(cls, 'academic_admin', 'test_benefit_access_admin'),
            create_role_user(cls, 'secretary', 'test_benefit_access_secretary'),
            create_role_user(cls, 'head_of_studies', 'test_benefit_access_hos'),
            create_role_user(cls, 'orientation', 'test_benefit_access_orientation'),
            create_role_user(cls, 'coexistence', 'test_benefit_access_coexistence'),
        )
        cls.others = (
            create_role_user(cls, 'teacher', 'test_benefit_access_teacher'),
            create_role_user(cls, 'tac', 'test_benefit_access_tac'),
            cls.other_department_chief,
        )

    def test_readers_read_benefits(self):
        for user in self.readers:
            student = self.student.with_user(user)
            self.assertEqual(student.benefit_ids, self.benefit, user.login)
            self.assertTrue(student.can_see_benefits, user.login)

    def test_other_teachers_do_not(self):
        for user in self.others:
            student = self.student.with_user(user)
            self.assertFalse(student.benefit_ids, user.login)
            self.assertFalse(student.can_see_benefits, user.login)
            with self.assertRaises(AccessError, msg=user.login):
                self.benefit.with_user(user).read(['benefit_type'])

    def test_benefits_badge_stays_for_every_teacher(self):
        for user in self.others:
            self.assertEqual(self.student.with_user(user).benefit_status, 'bonification', user.login)
