import re

from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_contact_data_request import create_contact_data_fixtures, valid_dni


def create_portal_contact_data_fixtures(cls, prefix):
    create_contact_data_fixtures(cls, prefix)
    cls.family_user = cls.env['res.users'].with_context(no_reset_password=True).create({
        'name': cls.family.name, 'login': f'test_family_{prefix.lower()}', 'password': f'test_family_{prefix.lower()}',
        'partner_id': cls.family.id, 'lang': 'en_US',
        'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
    })
    # Creating the user rewrites the partner's name, which partner_firstname re-splits into the
    # last name: put the fixture's first name back.
    cls.family.write({'firstname': 'Contact', 'lastname': False})


@tagged('post_install', '-at_install')
class TestPortalContactData(HttpCase):
    """/my/dades-contacte (issue #507): the family reviews the selected child's contact data and
    sends it for review - validated, staged, never written straight to the contacts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_contact_data_fixtures(cls, 'TPCD')

    def setUp(self):
        super().setUp()
        self.authenticate(self.family_user.login, self.family_user.login)

    def _post(self, **values):
        page = self.url_open('/my/dades-contacte')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        return self.url_open('/my/dades-contacte', data=dict(values, csrf_token=token))

    def _complete_form(self, **overrides):
        key = f'f{self.family.id}'
        values = {
            's_street': 'Portal Street 3', 's_zip': '08923', 's_city': 'Portal City',
            's_document_id': valid_dni(10000005),
            f'{key}_firstname': 'Contact', f'{key}_lastname': 'Portal', f'{key}_mobile': '711200001',
            f'{key}_email': self.family.email, f'{key}_same_address': '1',
        }
        values.update(overrides)
        return values

    def _request(self):
        return self.env['ems.contact.data.request'].search([('student_id', '=', self.minor.id)])

    def test_page_shows_the_student_and_the_family(self):
        response = self.url_open('/my/dades-contacte')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.minor.name, response.text)
        self.assertIn(f'name="f{self.family.id}_mobile"', response.text)

    def test_missing_fields_are_marked_and_nothing_is_staged(self):
        response = self._post(**self._complete_form(s_street=''))
        self.assertIn('o_ems_contact_data_errors', response.text)
        self.assertRegex(response.text, r'name="s_street"[^>]*is-invalid|is-invalid[^>]*name="s_street"')
        self.assertFalse(self._request())

    def test_valid_answer_is_staged_for_review(self):
        response = self._post(**self._complete_form(n0_relation_type_id=str(self.env.ref('ems.relation_type_father').id),
                                                    n0_firstname='Portal', n0_lastname='Father',
                                                    n0_mobile='711200006', n0_same_address='1'))
        self.assertIn('o_ems_contact_data_sent', response.text)
        request = self._request()
        self.assertEqual(request.state, 'submitted')
        self.assertEqual(request.submitted_uid, self.family_user)
        self.assertIn('Father', request.line_ids.mapped('new_value'))
        self.assertFalse(self.minor.street, "Nothing is written before the review")
        again = self.url_open('/my/dades-contacte')
        self.assertIn('o_ems_contact_data_pending_review', again.text)
        self.assertIn('Portal Street 3', again.text)

    def test_another_students_family_cannot_be_touched(self):
        stranger = self.env['res.partner'].create({
            'firstname': 'Stranger', 'lastname': 'Family', 'contact_type': 'family', 'mobile': '711200007'})
        self._post(**self._complete_form(**{f'f{stranger.id}_lastname': 'Hacked', f'f{stranger.id}_remove': '1'}))
        self.assertFalse(self._request().line_ids.filtered(lambda line: line.partner_id == stranger))
        self.assertEqual(stranger.lastname, 'Family')

    def test_home_shows_the_pending_request(self):
        self.env['ems.contact.data.request']._ems_open_for(self.minor, self.course)._ems_mark_sent()
        response = self.url_open('/my/home')
        self.assertIn('o_ems_contact_data_banner', response.text)
