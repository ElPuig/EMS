from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email


@tagged('post_install', '-at_install')
class TestPortalEnrollmentRenewIban(HttpCase):
    """controllers/portal_enrollment.py::portal_documentation_renew_iban -
    see plans/student_document_iban_renewal_allow_out_payment.md (now closed): an IBAN
    document created/renewed via the portal must always leave the underlying
    res.partner.bank trusted (allow_out_payment=True), matching what
    action_approve()/_apply_bank_account() already does for the review-queue path -
    otherwise a direct-debit invoice generated later silently loses its bank reference
    (confirmed in production: 332 already-posted invoices affected before this fix).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.student = cls.env['res.partner'].create({
            'name': 'Portal Renew Student', 'contact_type': 'student',
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Renew Student', 'login': 'test_portal_renew_iban',
            'partner_id': cls.student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def _renew(self):
        self.authenticate(self.portal_user.login, self.portal_user.login)
        return self.url_open(
            url='/my/documentacion/renew-iban',
            data={'csrf_token': Request.csrf_token(self)},
        )

    def test_renew_without_existing_document_trusts_bank(self):
        # Student already has an active bank account (e.g. CSV-imported) but no IBAN
        # document yet - the "create a pre-approved document" branch.
        bank = self.env['res.partner.bank'].create({
            'acc_number': 'ES9121000418450200051332',
            'partner_id': self.student.id,
        })
        self.assertFalse(bank.allow_out_payment)

        response = self._renew()

        self.assertEqual(response.status_code, 200)
        document = self.env['ems.student.document'].search([
            ('partner_id', '=', self.student.id), ('doc_type', '=', 'iban'),
        ])
        self.assertEqual(document.status, 'approved')
        self.assertTrue(bank.allow_out_payment)

    def test_renew_with_existing_approved_document_trusts_bank(self):
        # An IBAN document is already approved (e.g. from before this fix, or from a
        # prior renewal) but its bank was never actually trusted - the "bump expiry
        # on an existing document" branch must also (re-)grant trust.
        bank = self.env['res.partner.bank'].create({
            'acc_number': 'ES9121000418450200051332',
            'partner_id': self.student.id,
            'allow_out_payment': False,
        })
        self.env['ems.student.document'].create({
            'partner_id': self.student.id, 'doc_type': 'iban',
            'doc_value': bank.acc_number, 'doc_value2': 'Existing Holder',
            'status': 'approved',
        })

        response = self._renew()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(bank.allow_out_payment)

    def test_renew_without_any_bank_account_is_a_noop(self):
        # No document, no bank account at all - nothing to renew, must not error.
        response = self._renew()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.env['ems.student.document'].search([
            ('partner_id', '=', self.student.id), ('doc_type', '=', 'iban'),
        ]))
