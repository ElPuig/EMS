# -*- coding: utf-8 -*-

from datetime import date

from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_student_birth_date import _enrollment_fixture


@tagged('post_install', '-at_install')
class TestStudentBirthDatePortal(HttpCase):
    """The family gives the birth date when confirming the enrollment from the portal (issue
    #640). Without one the student counts as a minor, so it is the family who manages it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.student, cls.order = _enrollment_fixture(cls)
        cls.order.state = 'sent'
        cls.family = cls.env['res.partner'].create({
            'name': 'Birth Date Family', 'contact_type': 'family', 'email': 'birth.date.family@example.com'})
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.family.id, 'type_id': cls.env.ref('ems.relation_type_mother').id,
            'right_partner_id': cls.student.id})
        cls.family_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Birth Date Family', 'login': 'test_birth_date_family', 'password': 'test_birth_date_family',
            'lang': 'en_US',
            'partner_id': cls.family.id, 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.term = cls.env['account.payment.term'].create({
            'name': 'Birth date single payment', 'ems_portal_visible': True,
            'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100.0, 'nb_days': 0})]})
        cls.env['ems.student.document'].create({
            'partner_id': cls.student.id, 'doc_type': 'iban', 'doc_value': 'ES9121000418450200051332',
            'status': 'approved'})

    def _confirm(self, **extra):
        self.authenticate(self.family_user.login, self.family_user.login)
        return self.url_open('/my/gestion-matriculas/confirm', data={
            'csrf_token': Request.csrf_token(self), 'action': 'confirm',
            'payment_term_id': self.term.id, 'payment_method': 'direct_debit', **extra})

    def test_the_page_asks_for_the_missing_birth_date(self):
        self.authenticate(self.family_user.login, self.family_user.login)
        page = self.url_open('/my/gestion-matriculas')
        self.assertIn('name="birth_date"', page.text)

    def test_no_enrollment_without_the_birth_date(self):
        response = self._confirm()
        self.assertIn('error=missing_birth_date', response.url)
        self.assertEqual(self.order.state, 'sent')
        self.assertIn('Enter a valid birth date', self.url_open(response.url).text)

    def test_the_birth_date_given_is_saved_and_the_enrollment_confirmed(self):
        self._confirm(birth_date='2011-02-03')
        self.assertEqual(self.student.birth_date, date(2011, 2, 3))
        self.assertEqual(self.order.state, 'sale')

    def test_portal_birth_date_tour(self):
        self.start_tour("/my/gestion-matriculas", "ems_portal_birth_date", login=self.family_user.login)
        self.assertEqual(self.student.birth_date, date(2011, 2, 3))
        self.assertEqual(self.order.state, 'sale')
