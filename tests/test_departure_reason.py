from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDepartureReason(TransactionCase):
    """hr.departure.reason's EMS-added 'color' field (models/employees/departure_reason.py) -
    feeds the shared 'ems_archived_reason_ribbon' field widget on hr.employee's form/kanban."""

    def test_color_optional(self):
        reason = self.env['hr.departure.reason'].create({'name': 'Test Reason (No Color)'})
        self.assertFalse(reason.color)

    def test_color_accepts_hex(self):
        reason = self.env['hr.departure.reason'].create({
            'name': 'Test Reason (Color)', 'color': '#2E6C8E'})
        self.assertEqual(reason.color, '#2E6C8E')

    def test_color_must_be_hex(self):
        with self.assertRaises(ValidationError):
            self.env['hr.departure.reason'].create({
                'name': 'Test Reason (Bad Color)', 'color': 'not-a-hex-color'})

    def test_native_reasons_have_expected_colors(self):
        # data/main/hr.departure.reason.csv - Fired deliberately left uncolored (falls back to
        # the widget's own default red), Retired/Resigned/Transfer each get their own.
        self.assertFalse(self.env.ref('hr.departure_fired').color)
        self.assertEqual(self.env.ref('hr.departure_retired').color, '#2E6C8E')
        self.assertEqual(self.env.ref('hr.departure_resigned').color, '#C97B3D')
        self.assertEqual(self.env.ref('ems.departure_reason_transfer').color, '#B8A1D9')
