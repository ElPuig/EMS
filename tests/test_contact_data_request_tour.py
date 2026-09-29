import time
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged

from ..models.contacts.contact_data_request_send_wizard import EmsContactDataRequestSendWizard
from .common import mock_outgoing_email, next_student_id
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
        self.start_tour("/my/account", "ems_contact_data_portal", login=self.family_user.login)
        request = self.env['ems.contact.data.request'].search([('student_id', '=', self.minor.id)])
        self.assertEqual(request.state, 'submitted')
        self.assertIn('Tour Father', ' '.join(request.line_ids.mapped('person_name')))

    def test_tutor_sends_and_approves_tour(self):
        request = self.env['ems.contact.data.request']._ems_open_for(self.minor, self.course)
        data = self.minor._ems_contact_data()
        data['student'].update(street='Tour Street 1', zip='08924', city='Tour City', document_id=valid_dni(10000006))
        data['family'][0]['lastname'] = 'Tour'
        request._ems_submit(data)
        original_apply = EmsContactDataRequestSendWizard.action_apply

        def slow_apply(wizard):
            time.sleep(1.5)  # long enough for the tour to see the "processing" overlay
            return original_apply(wizard)

        with patch.object(EmsContactDataRequestSendWizard, 'action_apply', slow_apply):
            self.start_tour("/odoo", "ems_contact_data_tutor", login=self.tutor.login)
        self.assertEqual(request.state, 'done')
        self.assertEqual(self.minor.street, 'Tour Street 1')
        self.assertTrue(self.env['ems.contact.data.request'].search([('student_id', '=', self.adult.id)]))

    def test_tutor_reaches_student_data_from_the_students_section_tour(self):
        self.start_tour("/odoo", "ems_contact_data_menu", login=self.tutor.login)

    def test_family_with_two_children_is_pointed_to_a_repeated_contact_tour(self):
        Partner = self.env['res.partner']
        sibling = Partner.create({
            'name': 'Tour Sibling Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group.id})
        sibling_father = Partner.create({
            'firstname': 'Sibfather', 'lastname': 'Tour', 'contact_type': 'family', 'mobile': '+34 711 300 001'})
        self.env['res.partner.relation'].create([
            {'left_partner_id': self.family.id, 'type_id': self.env.ref('ems.relation_type_mother').id,
             'right_partner_id': sibling.id},
            {'left_partner_id': sibling_father.id, 'type_id': self.env.ref('ems.relation_type_father').id,
             'right_partner_id': sibling.id},
        ])
        self.env.flush_all()
        self.start_tour("/my/dades-contacte", "ems_contact_data_portal_siblings", login=self.family_user.login)
        request = self.env['ems.contact.data.request'].search([('student_id', '=', self.minor.id)])
        self.assertEqual(request.state, 'submitted')
        new_contact = request.line_ids.filtered(lambda line: line.person_key == 'n0')
        self.assertEqual(new_contact.matched_partner_id, sibling_father)

