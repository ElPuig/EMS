# -*- coding: utf-8 -*-

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, mock_outgoing_email, next_student_id


def _enrollment_fixture(case, birth_date=False, contact_type='student'):
    """A student (or applicant) and its enrollment, still a quotation, for the enrollment course."""
    course = case.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
        or case.env['ems.course'].create({'start': 2096, 'end': 2097, 'is_enrollment_default': True})
    __, study = create_level_study(case, 'SBD', level={'name': 'Birth Date Level'}, study={
        'code': 'SBD001', 'acronym': 'SBDS', 'name': 'Birth Date Study'})
    subject = case.env['ems.subject'].create({
        'code': 'SBDSUB', 'acronym': 'SBD1', 'name': 'Birth Date Subject', 'study_ids': [(6, 0, [study.id])]})
    student = case.env['res.partner'].create({
        'name': 'Birth Date Student', 'contact_type': contact_type, 'student_id': next_student_id(),
        'study_id': study.id, 'birth_date': birth_date})
    order = case.env['sale.order'].create({
        'partner_id': student.id, 'ems_course_id': course.id, 'ems_study_id': study.id,
        'order_line': [(0, 0, {'product_id': subject.product_id.id})]})
    return student, order


class TestStudentBirthDate(TransactionCase):
    """Nobody becomes, or stays, a student without a birth date (issue #640): without it EMS takes
    them for a minor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)

    def test_an_enrollment_is_not_confirmed_without_the_birth_date(self):
        student, order = _enrollment_fixture(self)
        with self.assertRaisesRegex(ValidationError, 'Birth Date Student'):
            order.action_confirm()
        student.birth_date = '2010-05-04'
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_an_applicant_without_birth_date_does_not_become_a_student(self):
        applicant, order = _enrollment_fixture(self, contact_type='applicant')
        with self.assertRaises(ValidationError):
            order.action_confirm()
        self.assertEqual(applicant.contact_type, 'applicant')

    def test_the_portal_birth_date_must_be_plausible(self):
        partner = self.env['res.partner']
        today = self.env['ems.datetime_utils'].get_local_today()
        self.assertEqual(partner._ems_portal_birth_date('2010-05-04'), date(2010, 5, 4))
        for value in ('', None, 'not a date', '2010-13-40', str(today), str(today + relativedelta(days=1)),
                      str(today - relativedelta(years=101))):
            self.assertFalse(partner._ems_portal_birth_date(value), value)
