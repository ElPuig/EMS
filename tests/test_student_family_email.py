from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import enforce_corporate_email_policy, next_student_id


class TestStudentFamilyEmail(TransactionCase):
    """A student's personal email can never be a family contact's, and neither can be corporate
    (issue #842)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.father = cls.env.ref('ems.relation_type_father')
        enforce_corporate_email_policy(cls)

    def _student(self, email, age=15):
        return self.env['res.partner'].create({
            'name': f'Family Email Student {email}', 'firstname': 'Family', 'lastname': 'Student',
            'contact_type': 'student', 'student_id': next_student_id(), 'email': email,
            'birth_date': date.today() - relativedelta(years=age),
        })

    def _family(self, email):
        return self.env['res.partner'].create({
            'name': f'Family Email Contact {email}', 'contact_type': 'family', 'email': email})

    def _link(self, family, student):
        return self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.father.id,
            'right_partner_id': student.id})

    def test_linking_a_family_with_the_students_email_is_refused(self):
        student, family = self._student('same.link@example.com'), self._family('Same.Link@example.com')
        with self.assertRaises(ValidationError):
            self._link(family, student)

    def test_changing_the_family_email_to_the_students_is_refused(self):
        student, family = self._student('student.own@example.com'), self._family('family.own@example.com')
        self._link(family, student)
        with self.assertRaises(ValidationError):
            family.email = 'student.own@example.com'

    def test_changing_the_student_email_to_the_familys_is_refused(self):
        student, family = self._student('student.two@example.com'), self._family('family.two@example.com')
        self._link(family, student)
        with self.assertRaises(ValidationError):
            student.email = 'family.two@example.com'

    def test_different_emails_and_unrelated_contacts_are_fine(self):
        student, family = self._student('student.ok@example.com'), self._family('family.ok@example.com')
        self._link(family, student)
        self._family('student.ok@example.com')  # not related to this student: no clash

    def test_a_family_contact_cannot_have_a_corporate_email(self):
        domain = self.env.company.google_ws_domain
        with self.assertRaises(ValidationError):
            self._family(f'someone@{domain}')
