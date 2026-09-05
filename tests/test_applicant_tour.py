from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestApplicantTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'PREI',
            level={'name': 'Test Level (Preinscription Tour)'},
            study={'code': 'PREI001', 'name': 'Test Study (Preinscription Tour)', 'date': date.today()},
        )
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Preinscription Tour Template', 'ems_study_id': cls.study.id, 'study_year': 1,
        })
        cls.applicant = cls.env['res.partner'].create({
            'name': 'Preinscription Tour Applicant', 'contact_type': 'applicant',
            'study_id': cls.study.id, 'preinscription_course': '1',
        })

    def test_applicant_form_and_proposal_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_applicant_form_and_proposal", login="admin")

        order = self.env['sale.order'].search([
            ('partner_id', '=', self.applicant.id), ('sale_order_template_id', '=', self.template.id),
        ])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.ems_study_id, self.study)
        self.assertEqual(order.ems_group_id, self.group)
