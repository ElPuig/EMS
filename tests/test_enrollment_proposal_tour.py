from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestEnrollmentProposalTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'EPRO',
            level={'name': 'Test Level (Enrollment Proposal Tour)'},
            study={'code': 'EPRO001', 'name': 'Test Study (Enrollment Proposal Tour)', 'date': date.today()},
        )
        # study_year matches the seeded group's own course (1): a plain renewal in the same
        # group, so _ems_suggested_group's domain (study/course/acronym) resolves back to this
        # exact group without needing a second, higher-course one.
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Enrollment Proposal Tour Template', 'ems_study_id': cls.study.id, 'study_year': 1,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Enrollment Proposal Tour Student', 'contact_type': 'student',
            'study_id': cls.study.id, 'main_group_id': cls.group.id,
        })
        cls.graduate_student = cls.env['res.partner'].create({
            'name': 'Enrollment Proposal Tour Graduate', 'contact_type': 'student',
            'study_id': cls.study.id, 'main_group_id': cls.group.id,
        })

    def test_enrollment_proposal_create_tour(self):
        self.start_tour("/odoo", "ems_enrollment_proposal_create", login="admin")

        order = self.env['sale.order'].search([
            ('partner_id', '=', self.student.id), ('sale_order_template_id', '=', self.template.id),
        ])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.ems_study_id, self.study)
        self.assertEqual(order.ems_group_id, self.group)

    def test_enrollment_proposal_graduation_tour(self):
        self.assertFalse(self.graduate_student.has_graduated)

        self.start_tour("/odoo", "ems_enrollment_proposal_graduation", login="admin")

        self.assertTrue(self.graduate_student.has_graduated)
