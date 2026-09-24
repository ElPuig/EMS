from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_contact_data_request import valid_dni
from .test_portal_contact_data import create_portal_contact_data_fixtures


@tagged('post_install', '-at_install')
class TestContactDataRequestTour(HttpCase):
    """Issue #507 in a browser: the family answers from the portal, and the group's tutor - the
    least privileged role that sends and reviews requests - sends one and approves the answer,
    through both view modes of the follow-up action."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_contact_data_fixtures(cls, 'TCDT')

    def test_family_answers_from_the_portal_tour(self):
        self.start_tour("/my/dades-contacte", "ems_contact_data_portal", login=self.family_user.login)
        request = self.env['ems.contact.data.request'].search([('student_id', '=', self.minor.id)])
        self.assertEqual(request.state, 'submitted')
        self.assertIn('Tour Father', ' '.join(request.line_ids.mapped('person_name')))

    def test_tutor_sends_and_approves_tour(self):
        request = self.env['ems.contact.data.request']._ems_open_for(self.minor, self.course)
        data = self.minor._ems_contact_data()
        data['student'].update(street='Tour Street 1', zip='08924', city='Tour City', document_id=valid_dni(10000006))
        data['family'][0]['lastname'] = 'Tour'
        request._ems_submit(data)
        self.start_tour("/odoo", "ems_contact_data_tutor", login=self.tutor.login)
        self.assertEqual(request.state, 'done')
        self.assertEqual(self.minor.street, 'Tour Street 1')
        self.assertTrue(self.env['ems.contact.data.request'].search([('student_id', '=', self.adult.id)]))
