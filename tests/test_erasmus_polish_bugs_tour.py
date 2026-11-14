from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestErasmusPolishBugsTour(HttpCase):
    """Issue #777 - bugs found in the review of 46.0, each screen driven by the least privileged
    role that uses it: the Mobility technician for the host entities and the rates, the Secretary
    for the economic panel and the project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.technician_user = create_role_user(cls, 'erasmus', 'test_polish_technician', lang='en_US')
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_polish_secretary', lang='en_US')
        cls.project = cls.env['ems.erasmus.project'].create({'name': '2099-1-ES01-KA121-VET-000777777',
                                                             'kind': 'ka121_vet'})
        cls.env['ems.erasmus.support.rate'].create({'call_year': 2099, 'kind': 'ka121_vet', 'amount': 350})

    def test_host_entity_details_tour(self):
        host = self.env['res.partner'].create({'name': 'Test Polish Host GmbH', 'is_company': True,
                                               'is_erasmus_host': True, 'contact_type': 'provider'})
        # The team's members are teachers too: the contact form reads student data (enrolments,
        # authorisations, documents...) that the Erasmus role alone cannot.
        self.technician_user.groups_id = [(4, self.env.ref('ems.group_teacher').id)]
        self.start_tour('/odoo/action-ems.action_erasmus_host_entity', 'ems_erasmus_host_entity_details',
                        login=self.technician_user.login)
        self.assertEqual((host.street, host.city, host.website, host.erasmus_oid),
                         ('Hauptstrasse 1', 'Reutlingen', 'https://host.example.com', 'E10150031'))

    def test_project_year_tour(self):
        self.assertEqual(self.project.call_year, 2099)
        self.start_tour('/odoo/action-ems.action_erasmus_project', 'ems_erasmus_project_year',
                        login=self.secretary_user.login)

    def test_support_rate_year_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_support_rate', 'ems_erasmus_support_rate_year',
                        login=self.technician_user.login)
