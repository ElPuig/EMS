import re
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import CORPORATE_TEST_DOMAIN, enforce_corporate_email_policy, mock_outgoing_email, next_student_id
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


class PortalContactDataHelpers:
    """Posting the review form as the logged-in portal user, with the family fixtures of
    create_portal_contact_data_fixtures()."""

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

    def _request(self, student=None):
        return self.env['ems.contact.data.request'].search([('student_id', '=', (student or self.minor).id)])


@tagged('post_install', '-at_install')
class TestPortalContactData(PortalContactDataHelpers, HttpCase):
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
        self.assertIn('href="/my/dades-contacte"', response.text)

    def test_home_has_no_contact_data_card(self):
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('/my/dades-contacte', response.text, "The review is reached from the profile")
        self.assertNotIn('Review the contact details of the student and the family', response.text)

    def test_profile_links_to_the_review_and_no_longer_offers_a_mailto(self):
        self.env.company.secretariat_email = 'secretariat.tpcd@example.com'
        response = self.url_open('/my/account')
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/my/dades-contacte"', response.text)
        self.assertNotIn('Request a data change', response.text)
        self.assertNotIn('secretariat.tpcd@example.com', response.text)


@tagged('post_install', '-at_install')
class TestPortalContactDataRules(PortalContactDataHelpers, HttpCase):
    """Who may answer a request, and what may be sent: only a portal account that acts for the
    student (res.partner._ems_portal_contact_data_student) reaches the review - never a minor on
    their own view-only account, nor a family looking at an adult child - and an address of the
    centre's own domain is refused before it is staged (issue #514)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        enforce_corporate_email_policy(cls)
        create_portal_contact_data_fixtures(cls, 'TPCR')
        cls.minor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.minor.name, 'login': 'test_minor_tpcr', 'password': 'test_minor_tpcr',
            'partner_id': cls.minor.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        # An adult child of the same family who authorized sharing with it: the family only consults him.
        cls.grown = cls.env['res.partner'].create({
            'name': 'Grown Child (TPCR)', 'contact_type': 'student', 'student_id': next_student_id(),
            'email': 'grown.tpcr@example.com', 'birth_date': date.today() - relativedelta(years=19),
        })
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_father').id,
            'right_partner_id': cls.grown.id,
        })
        cls.env.flush_all()  # else the ORM would write the computed auth_share over the SQL below
        cls.env.cr.execute("UPDATE res_partner SET auth_share = TRUE WHERE id = %s", (cls.grown.id,))
        cls.grown.invalidate_recordset(['auth_share'])

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _assert_cannot_review_nor_send(self, student):
        """`student`'s review is refused to the logged-in account: the page and the form send it
        home, the home has no banner even with a request waiting, the profile no button."""
        self.env['ems.contact.data.request']._ems_open_for(student, self.course)._ems_mark_sent()
        page = self.url_open('/my/dades-contacte')
        posted = self.url_open('/my/dades-contacte',
                               data=dict(self._complete_form(), csrf_token=Request.csrf_token(self)))
        for response in (page, posted):
            self.assertTrue(response.url.split('?')[0].endswith('/my/home'), response.url)
        self.assertFalse(self._request(student).line_ids, "Nothing is staged")
        self.assertEqual(self._request(student).state, 'pending')
        self.assertNotIn('o_ems_contact_data_banner', self.url_open('/my/home').text)
        self.assertNotIn('/my/dades-contacte', self.url_open('/my/account').text)

    def test_the_family_of_a_minor_answers(self):
        self._login(self.family_user)
        self.assertEqual(self.family._ems_portal_contact_data_student(), self.minor)
        self.env['ems.contact.data.request']._ems_open_for(self.minor, self.course)._ems_mark_sent()
        self.assertIn('o_ems_contact_data_banner', self.url_open('/my/home').text)
        self.assertIn('href="/my/dades-contacte"', self.url_open('/my/account').text)

    def test_a_minor_on_their_own_account_cannot_review_nor_send(self):
        self._login(self.minor_user)
        self.assertFalse(self.minor._ems_portal_contact_data_student())
        self._assert_cannot_review_nor_send(self.minor)

    def test_a_family_looking_at_an_adult_child_cannot_review_nor_send(self):
        self.family.sudo().selected_student_id = self.grown
        self.family.invalidate_recordset(['selected_student_id'])
        self.assertEqual(self.family.get_portal_student(), self.grown)
        self.assertFalse(self.family._ems_portal_contact_data_student())
        self._login(self.family_user)
        self._assert_cannot_review_nor_send(self.grown)

    def test_a_corporate_email_is_refused_before_it_is_staged(self):
        self._login(self.family_user)
        key = f'f{self.family.id}'
        response = self._post(**self._complete_form(**{f'{key}_email': f'mother@{CORPORATE_TEST_DOMAIN}'}))
        self.assertIn('o_ems_contact_data_errors', response.text)
        self.assertRegex(response.text, rf'name="{key}_email"[^>]*is-invalid|is-invalid[^>]*name="{key}_email"')
        self.assertIn('be used as a personal email', response.text)
        self.assertFalse(self._request(), "Nothing is staged")

    def test_a_corporate_email_already_on_file_does_not_block_the_answer(self):
        self.env.flush_all()
        self.env.cr.execute("UPDATE res_partner SET email = %s WHERE id = %s",
                            (f'legacy@{CORPORATE_TEST_DOMAIN}', self.family.id))
        self.family.invalidate_recordset(['email'])
        self._login(self.family_user)
        response = self._post(**self._complete_form())
        self.assertIn('o_ems_contact_data_sent', response.text)
        self.assertEqual(self._request().state, 'submitted')
