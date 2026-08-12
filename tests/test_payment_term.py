from odoo.tests.common import TransactionCase


class TestPaymentTerm(TransactionCase):
    """models/enrollment/payment_term.py — AccountPaymentTerm (account.payment.term
    extension). Two independent Boolean flags, no compute/constrains/override logic
    of its own; the actual portal-visibility filtering
    (ems_portal_visible AND (not ems_requires_fees OR enrollment has fees)) lives in
    controllers/portal_enrollment.py, out of this pass's scope — see
    docs/en/developers/enrollment/payment_term.md."""

    def test_defaults_are_false(self):
        term = self.env['account.payment.term'].create({'name': 'Test Term Defaults'})
        self.assertFalse(term.ems_portal_visible)
        self.assertFalse(term.ems_requires_fees)

    def test_flags_are_independently_settable(self):
        term = self.env['account.payment.term'].create({
            'name': 'Test Term Portal Only', 'ems_portal_visible': True, 'ems_requires_fees': False,
        })
        self.assertTrue(term.ems_portal_visible)
        self.assertFalse(term.ems_requires_fees)

        term2 = self.env['account.payment.term'].create({
            'name': 'Test Term Fees Only', 'ems_portal_visible': False, 'ems_requires_fees': True,
        })
        self.assertFalse(term2.ems_portal_visible)
        self.assertTrue(term2.ems_requires_fees)

    def test_flags_persist_after_write(self):
        term = self.env['account.payment.term'].create({'name': 'Test Term Write'})
        term.write({'ems_portal_visible': True, 'ems_requires_fees': True})
        term.invalidate_recordset()
        self.assertTrue(term.ems_portal_visible)
        self.assertTrue(term.ems_requires_fees)
