from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_contact_data_request import valid_dni
from .test_portal_contact_data import PortalContactDataHelpers, create_portal_contact_data_fixtures


@tagged('post_install', '-at_install')
class TestPortalProfile(PortalContactDataHelpers, HttpCase):
    """/my/account for portal users (issue #736): the student's school data, read only; the
    account's own contact details, the same ones /my/dades-contacte sends; the review's status and
    button for whoever may send it; and the family contacts on the student's own account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_contact_data_fixtures(cls, 'TPPR')
        cls.minor.write({
            'student_email': 'minor.tppr@corporate.example.com', 'street': 'Profile Street 9',
            'zip': '08924', 'city': 'Profile City', 'medical_id': 'TPPR0000001', 'nuss': '081234567840',
            'vat': f'ES{valid_dni(10000003)}',
        })
        cls.family.document_id = valid_dni(10000009)
        cls.minor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.minor.name, 'login': 'test_minor_tppr', 'password': 'test_minor_tppr',
            'partner_id': cls.minor.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.adult_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.adult.name, 'login': 'test_adult_tppr', 'password': 'test_adult_tppr',
            'partner_id': cls.adult.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def _profile(self, user):
        self.authenticate(user.login, user.login)
        response = self.url_open('/my/account')
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_student_sees_school_data_contact_data_and_family(self):
        page = self._profile(self.minor_user)
        for value in (self.minor.student_id, self.group.name, self.study.name, self.tutor.name,
                      'minor.tppr@corporate.example.com', 'Profile Street 9, 08924 Profile City',
                      'TPPR0000001', '081234567840', self.family.name, self.family.email):
            self.assertIn(value, page)
        self.assertIn('o_ems_profile_family', page)
        self.assertNotIn(self.minor.vat, page, "The VAT number is not part of the reviewable data")

    def test_minor_is_told_the_family_updates_the_details(self):
        page = self._profile(self.minor_user)
        self.assertIn('o_ems_profile_family_updates', page)
        self.assertNotIn('/my/dades-contacte', page)

    def test_family_sees_its_own_details_and_the_childs_school_data(self):
        page = self._profile(self.family_user)
        self.assertIn(self.minor.student_id, page)
        self.assertIn(self.family.document_id, page)
        self.assertNotIn('TPPR0000001', page, "The child's health card is on the review page, not here")
        self.assertNotIn('o_ems_profile_family"', page)
        self.assertIn('href="/my/dades-contacte"', page)

    def test_review_status(self):
        Request = self.env['ems.contact.data.request']
        self.assertNotIn('o_ems_profile_requested', self._profile(self.family_user))
        data_request = Request._ems_open_for(self.minor, self.course)
        data_request._ems_mark_sent()
        self.assertIn('o_ems_profile_requested', self._profile(self.family_user))
        self._post(**self._complete_form())
        self.assertIn('o_ems_profile_pending_review', self._profile(self.family_user))
        data_request._ems_reject('Wrong TPPR street')
        page = self._profile(self.family_user)
        self.assertIn('o_ems_profile_returned', page)
        self.assertIn('Wrong TPPR street', page)

    def test_adult_student_reviews_their_own_details(self):
        page = self._profile(self.adult_user)
        self.assertIn('href="/my/dades-contacte"', page)
        self.assertIn(self.adult.document_id, page)
