from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import (
    CORPORATE_TEST_DOMAIN, create_role_employee, create_role_user, enforce_corporate_email_policy,
    next_student_id,
)


class TestPersonalEmailNotCorporate(TransactionCase):
    """A personal email (res.partner.email on students/families, hr.employee.private_email on
    staff) can never be an address of the centre's own Google Workspace domain (issue #514)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        enforce_corporate_email_policy(cls)
        cls.company = cls.env.company
        cls.corporate = f'laia.puig@{CORPORATE_TEST_DOMAIN}'

    def _student(self, **vals):
        return self.env['res.partner'].create({
            'name': 'PENC Student', 'contact_type': 'student', 'student_id': next_student_id(), **vals})

    def _assert_rejected(self):
        # Matches this check's own message, so an unrelated ValidationError (e.g. a missing
        # IDALU) can't make the test pass by accident.
        return self.assertRaisesRegex(ValidationError, "can't be used as a personal email")

    # --- res.company._ems_is_corporate_email ---------------------------------

    def test_detects_domain_and_subdomains_case_insensitively(self):
        self.assertTrue(self.company._ems_is_corporate_email(self.corporate))
        self.assertTrue(self.company._ems_is_corporate_email(f'Laia.Puig@{CORPORATE_TEST_DOMAIN.upper()}'))
        self.assertTrue(self.company._ems_is_corporate_email(f'laia@alumnes.{CORPORATE_TEST_DOMAIN}'))

    def test_other_domains_are_personal(self):
        self.assertFalse(self.company._ems_is_corporate_email('laia@example.com'))
        # Same suffix but a different domain, not a subdomain.
        self.assertFalse(self.company._ems_is_corporate_email(f'laia@other{CORPORATE_TEST_DOMAIN}'))
        self.assertFalse(self.company._ems_is_corporate_email(False))

    def test_no_check_without_a_configured_domain(self):
        self.company.google_ws_domain = False
        self.assertFalse(self.company._ems_is_corporate_email(self.corporate))

    def test_no_check_on_a_development_database(self):
        self.env['ir.config_parameter'].sudo().set_param('ems.environment_type', 'dev')
        self.assertFalse(self.company._ems_is_corporate_email(self.corporate))
        self._student(email=self.corporate)  # no ValidationError

    def test_checked_when_the_environment_is_undeclared(self):
        # A clean database (e.g. CI) never ran install/devel/deploy.sh: validate there too.
        self.env['ir.config_parameter'].sudo().search([('key', '=', 'ems.environment_type')]).unlink()
        self.assertTrue(self.company._ems_is_corporate_email(self.corporate))

    # --- res.partner ---------------------------------------------------------

    def test_student_create_and_write_reject_corporate_email(self):
        with self._assert_rejected():
            self._student(email=self.corporate)
        student = self._student(email='laia@example.com')
        with self._assert_rejected():
            student.write({'email': self.corporate})

    def test_every_student_lifecycle_type_and_family_is_checked(self):
        for contact_type in ('applicant', 'alumni', 'withdrawal', 'expelled', 'family'):
            with self.subTest(contact_type=contact_type), self._assert_rejected():
                self.env['res.partner'].create({
                    'name': f'PENC {contact_type}', 'contact_type': contact_type,
                    'student_id': next_student_id(), 'email': self.corporate})

    def test_contacts_without_a_personal_email_type_are_not_checked(self):
        # A staff member's work contact (no contact_type) holds the corporate account itself.
        self.env['res.partner'].create({'name': 'PENC Work Contact', 'email': self.corporate})
        self.env['res.partner'].create({
            'name': 'PENC Provider', 'contact_type': 'provider', 'email': self.corporate})

    def test_legacy_corporate_email_does_not_block_a_type_change(self):
        student = self._student(email='laia@example.com')
        # A legacy value stored before the check existed.
        self.env.cr.execute("UPDATE res_partner SET email = %s WHERE id = %s", (self.corporate, student.id))
        student.invalidate_recordset(['email'])
        student.write({'contact_type': 'alumni'})
        self.assertEqual(student.contact_type, 'alumni')

    # --- hr.employee ---------------------------------------------------------

    def test_employee_private_email_rejects_corporate_email(self):
        with self._assert_rejected():
            self.env['hr.employee'].create({'name': 'PENC Teacher', 'private_email': self.corporate})
        employee = self.env['hr.employee'].create({'name': 'PENC Teacher', 'private_email': 'ada@example.com'})
        with self._assert_rejected():
            employee.write({'private_email': self.corporate})
        # The work email is the corporate account and stays allowed.
        employee.write({'work_email': f'ada@{CORPORATE_TEST_DOMAIN}'})

    def test_teacher_cannot_set_corporate_email_from_my_profile(self):
        user = create_role_user(self, 'teacher', 'penc_teacher')
        employee = create_role_employee(self, user, private_email='penc@example.com')
        with self._assert_rejected():
            user.with_user(user).write({'private_email': self.corporate})
        user.with_user(user).write({'private_email': 'penc.new@example.com'})
        self.assertEqual(employee.private_email, 'penc.new@example.com')
