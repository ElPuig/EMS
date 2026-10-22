# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import mock_outgoing_email
from .test_quality_minute_rules import MinuteRulesFixtures


class TestQualityMinuteGuest(MinuteRulesFixtures, TransactionCase):
    """People from outside EMS at a meeting (a student's family, a teacher from another school):
    the minute records them by name, surname and email, with no account of their own."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The call is an email: no real one may leave a test.
        mock_outgoing_email(cls)

    def _minute_with_guests(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        minute = self._minute(self.dep_a, redactor_employee_id=public_a.id, attendee_ids=[(6, 0, public_a.ids)])
        minute.with_user(self.user_a).write({'guest_ids': [
            (0, 0, {'name': 'Marta', 'surname': 'Guest Puig', 'email': 'marta.guest@example.com',
                    'organisation': "Mother of a student"}),
            (0, 0, {'name': 'Pere', 'surname': 'Absent Soler', 'attended': False}),
        ]})
        return minute

    def test_whoever_writes_the_minute_adds_people_from_outside(self):
        minute = self._minute_with_guests()
        guest = minute.guest_ids.filtered(lambda item: item.name == 'Marta')
        self.assertEqual(guest.display_name, "Marta Guest Puig (Mother of a student)")
        self.assertEqual(minute.attendee_count, 2, "the teacher and the guest who attended")

    def test_a_wrong_email_is_refused(self):
        minute = self._minute(self.dep_a)
        with self.assertRaises(ValidationError):
            minute.write({'guest_ids': [(0, 0, {'name': 'Anna', 'surname': 'Typo', 'email': 'anna.example.com'})]})

    def test_the_pdf_names_them_but_never_prints_their_email(self):
        minute = self._minute_with_guests()
        html = self.env['ir.actions.report']._render_qweb_html('ems.report_minute', minute.ids)[0].decode()
        self.assertIn('Marta Guest Puig', html)
        self.assertIn('Pere Absent Soler', html)
        self.assertNotIn('marta.guest@example.com', html)

    def test_the_call_is_not_sent_to_them(self):
        """The call goes out as one message with every recipient in view: a family must not get
        the staff's addresses, nor the staff a family's."""
        self.employee_a.work_email = 'rules.a.work@example.com'
        minute = self._minute_with_guests()
        minute.start_datetime = fields.Datetime.now()
        minute.with_user(self.user_a).action_send_call()
        sent = self.env['mail.mail'].search([('email_to', 'ilike', 'rules.a.work@example.com')], order='id desc', limit=1)
        self.assertTrue(sent)
        self.assertNotIn('marta.guest@example.com', sent.email_to)
        self.assertEqual(minute.call_recipient_count, 1)

    def test_the_guests_table_shows_only_when_used(self):
        minute = self._minute(self.dep_a)
        self.assertFalse(minute.show_guests, "a minute with nobody from outside keeps the block short")
        self.assertTrue(self._minute_with_guests().show_guests)

    def test_a_guest_can_get_the_call_in_a_message_of_their_own(self):
        self.employee_a.work_email = 'rules.a.work@example.com'
        minute = self._minute_with_guests()
        minute.start_datetime = fields.Datetime.now()
        minute.guest_ids.filtered(lambda item: item.name == 'Marta').send_call = True
        minute.with_user(self.user_a).action_send_call()
        mails = self.env['mail.mail'].search([('model', '=', 'ems.minute'), ('res_id', '=', minute.id)])
        staff = mails.filtered(lambda mail: 'rules.a.work@example.com' in mail.email_to)
        guest = mails.filtered(lambda mail: 'marta.guest@example.com' in mail.email_to)
        self.assertEqual(len(staff), 1)
        self.assertNotIn('marta.guest@example.com', staff.email_to)
        self.assertEqual(len(guest), 1)
        self.assertNotIn('rules.a.work@example.com', guest.email_to)
        self.assertNotIn('/odoo/action-ems.action_minute', guest.body_html, "no link they cannot open")
        self.assertEqual(minute.call_recipient_count, 2)

    def test_the_call_needs_an_email_to_be_sent(self):
        minute = self._minute(self.dep_a)
        with self.assertRaises(ValidationError):
            minute.write({'guest_ids': [(0, 0, {'name': 'Jordi', 'surname': 'No Mail', 'send_call': True})]})
