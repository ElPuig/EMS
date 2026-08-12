from odoo.tests.common import TransactionCase

from .common import mock_outgoing_email


class TestStrikeReason(TransactionCase):
    """models/coexistence/strike_reason.py — EmsStrikeReason. A small lookup
    model (name/sequence/active, no compute or business logic); embedded in
    the strike-issuance OWL component, already exercised by
    static/tests/tours/strike_tour.js (the reason-select step) — not
    duplicated here. See docs/en/developers/coexistence/strike.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ems.strike sends real emails synchronously on create() (see CLAUDE.md).
        mock_outgoing_email(cls)

    def test_create_requires_name(self):
        with self.assertRaises(Exception):
            self.env['ems.strike.reason'].create({})

    def test_default_active(self):
        reason = self.env['ems.strike.reason'].create({'name': 'Test Reason'})
        self.assertTrue(reason.active)

    def test_ordered_by_sequence_then_name(self):
        self.env['ems.strike.reason'].create({'name': 'Z Reason', 'sequence': 5})
        self.env['ems.strike.reason'].create({'name': 'A Reason', 'sequence': 5})
        self.env['ems.strike.reason'].create({'name': 'B Reason', 'sequence': 1})
        reasons = self.env['ems.strike.reason'].search([
            ('name', 'in', ['Z Reason', 'A Reason', 'B Reason']),
        ])
        self.assertEqual(reasons.mapped('name'), ['B Reason', 'A Reason', 'Z Reason'])

    def test_archiving_does_not_affect_strikes_already_using_it(self):
        reason = self.env['ems.strike.reason'].create({'name': 'Archivable Reason'})
        teacher = self.env['hr.employee'].create({
            'name': 'Test Teacher (Strike Reason)', 'employee_type': 'teacher'})
        student = self.env['res.partner'].create({
            'name': 'Test Student (Strike Reason)', 'contact_type': 'student'})
        strike = self.env['ems.strike'].create({
            'student_id': student.id, 'teacher_id': teacher.id, 'reason_id': reason.id,
        })
        reason.active = False
        self.assertEqual(strike.reason_id, reason)
        self.assertFalse(reason.active)

    def test_seed_default_reason_exists(self):
        self.assertTrue(self.env.ref('ems.strike_reason_other').active)
