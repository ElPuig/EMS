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

    def test_profile_notice_is_translated(self):
        # The sentence must stay a term of its own: next to the lock icon in a plain <span> Odoo
        # merges both into one term, which no .po entry matches, and the notice stays in English.
        arch = self.env.ref('ems.portal_my_details_readonly').with_context(lang='ca_ES').arch_db
        self.assertIn('Les teves dades personals són de només lectura', arch)

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


@tagged('post_install', '-at_install')
class TestPortalContactDataSiblings(PortalContactDataHelpers, HttpCase):
    """A family with two children (issue #507): a family contact it adds can also be linked to the
    other child, and one that repeats a contact of that other child - same document or same
    phone - is pointed out and asked about, so the person is not entered twice. Nothing is said
    about contacts of other families."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_contact_data_fixtures(cls, 'TPCB')
        Partner = cls.env['res.partner']
        cls.father = cls.env.ref('ems.relation_type_father')

        def student(name):
            return Partner.create({
                'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
                'birth_date': date.today() - relativedelta(years=13), 'main_group_id': cls.group.id})

        def contact(firstname, mobile, document, *children):
            partner = Partner.create({'firstname': firstname, 'lastname': 'TPCB', 'contact_type': 'family',
                                      'mobile': mobile, 'document_id': document})
            cls.env['res.partner.relation'].create([{
                'left_partner_id': partner.id, 'type_id': cls.father.id, 'right_partner_id': child.id,
            } for child in children])
            return partner

        # The account's other child, whose father is not a contact of the first child yet.
        cls.sibling = student('Sibling Student (TPCB)')
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_mother').id,
            'right_partner_id': cls.sibling.id})
        cls.sibling_father = contact('Sibfather', '+34 711 300 001', valid_dni(10000201), cls.sibling)
        # Somebody else's family.
        cls.foreign_student = student('Foreign Student (TPCB)')
        cls.stranger = contact('Stranger', '+34 711 300 002', valid_dni(10000202), cls.foreign_student)
        cls.env.flush_all()

    def setUp(self):
        super().setUp()
        self.authenticate(self.family_user.login, self.family_user.login)

    def _new_contact(self, key='n0', **overrides):
        values = {
            f'{key}_relation_type_id': str(self.father.id), f'{key}_firstname': 'Newfather',
            f'{key}_lastname': 'TPCB', f'{key}_mobile': '711300099', f'{key}_same_address': '1',
        }
        values.update({f'{key}_{name}': value for name, value in overrides.items()})
        return values

    def _relation(self, contact, student):
        return self.env['res.partner.relation.all'].search_count([
            ('this_partner_id', '=', contact.id), ('other_partner_id', '=', student.id)])

    def _lines(self, key='n0'):
        return self._request().line_ids.filtered(lambda line: line.person_key == key)

    def _answer(self, **contact):
        return self._post(**self._complete_form(**self._new_contact(**contact)))

    def test_the_form_offers_the_other_child(self):
        page = self.url_open('/my/dades-contacte').text
        self.assertIn(f'n__INDEX___also_{self.sibling.id}', page)
        self.assertIn(self.sibling.name, page)

    def test_a_phone_of_a_siblings_contact_is_pointed_out_before_anything_is_staged(self):
        response = self._answer(mobile=self.sibling_father.mobile, firstname='Someoneelse')
        self.assertIn('o_ems_contact_match', response.text)
        self.assertIn('has the same mobile number', response.text)
        self.assertIn(self.sibling_father.name, response.text)
        self.assertIn(self.sibling.name, response.text)
        self.assertFalse(self._request(), "Nothing is staged until the family answers")

    def test_yes_links_the_existing_contact_instead_of_creating_another(self):
        response = self._answer(mobile=self.sibling_father.mobile, confirm='yes', match=str(self.sibling_father.id))
        self.assertIn('o_ems_contact_data_sent', response.text)
        line = self._lines()[0]
        self.assertEqual(line.matched_partner_id, self.sibling_father)
        self.assertFalse(line.possible_duplicate_id)
        families = self.env['res.partner'].search_count([('contact_type', '=', 'family'), ('mobile', '=', self.sibling_father.mobile)])
        self._request().action_approve()
        self.assertEqual(self._relation(self.sibling_father, self.minor), 1)
        self.assertEqual(self._relation(self.sibling_father, self.sibling), 1, "Still a contact of the sibling")
        self.assertEqual(self.env['res.partner'].search_count([
            ('contact_type', '=', 'family'), ('mobile', '=', self.sibling_father.mobile)]), families)

    def test_no_creates_a_new_contact_and_flags_the_shared_phone(self):
        self._answer(mobile=self.sibling_father.mobile, firstname='Someoneelse', confirm='no',
                     match=str(self.sibling_father.id))
        line = self._lines()[0]
        self.assertFalse(line.matched_partner_id)
        self.assertEqual(line.possible_duplicate_id, self.sibling_father)
        self._request().action_approve()
        self.assertEqual(self.env['res.partner'].search_count([
            ('contact_type', '=', 'family'), ('mobile', '=', self.sibling_father.mobile)]), 2)

    def test_the_same_document_is_asked_too_and_cannot_be_another_person(self):
        document = dict(document_id=self.sibling_father.document_id, mobile='711300098')
        first = self._answer(**document)
        self.assertIn('has the same identity document', first.text)
        self.assertFalse(self._request())
        refused = self._answer(confirm='no', match=str(self.sibling_father.id), **document)
        self.assertIn('correct the document number', refused.text)
        self.assertFalse(self._request())
        accepted = self._answer(confirm='yes', match=str(self.sibling_father.id), **document)
        self.assertIn('o_ems_contact_data_sent', accepted.text)
        self.assertEqual(self._lines()[0].matched_partner_id, self.sibling_father)

    def test_an_answer_about_another_contact_than_the_one_shown_is_not_taken(self):
        response = self._answer(mobile=self.sibling_father.mobile, confirm='yes', match=str(self.stranger.id))
        self.assertIn('o_ems_contact_match', response.text)
        self.assertFalse(self._request())

    def test_a_contact_of_another_family_is_never_pointed_out(self):
        for values in (dict(mobile=self.stranger.mobile), dict(document_id=self.stranger.document_id)):
            response = self._answer(**values)
            self.assertNotIn('o_ems_contact_match', response.text)
            self.assertNotIn(self.stranger.name, response.text)
            self.assertEqual(self._request().state, 'submitted')
            self._request().unlink()

    def test_a_new_contact_can_also_be_linked_to_the_other_child(self):
        self._answer(**{f'also_{self.sibling.id}': '1'})
        self.assertEqual(self._lines()[0].also_student_ids, self.sibling)
        self._request().action_approve()
        contact = self.env['res.partner'].search([('contact_type', '=', 'family'), ('mobile', 'like', '711300099')])
        self.assertEqual(len(contact), 1)
        self.assertEqual(self._relation(contact, self.minor), 1)
        self.assertEqual(self._relation(contact, self.sibling), 1)

    def test_not_ticking_the_other_child_links_only_the_one_reviewed(self):
        self._answer()
        self.assertFalse(self._lines()[0].also_student_ids)
        self._request().action_approve()
        contact = self.env['res.partner'].search([('contact_type', '=', 'family'), ('mobile', 'like', '711300099')])
        self.assertEqual(self._relation(contact, self.minor), 1)
        self.assertEqual(self._relation(contact, self.sibling), 0)

    def test_only_the_accounts_own_children_can_be_chosen(self):
        self._answer(**{f'also_{self.foreign_student.id}': '1', f'also_{self.sibling.id}': '1'})
        self.assertEqual(self._lines()[0].also_student_ids, self.sibling)

    def test_reopening_a_sent_answer_shows_the_choices_again(self):
        self._answer(mobile=self.sibling_father.mobile, confirm='yes', match=str(self.sibling_father.id))
        page = self.url_open('/my/dades-contacte').text
        self.assertIn('o_ems_contact_data_pending_review', page)
        self.assertRegex(page, r'value="yes"[^>]*checked')

