from odoo.tests.common import TransactionCase


class TestSettings(TransactionCase):
    """res.config.settings (models/settings/settings.py) is a thin related-field proxy over
    res.company (see test_company_settings.py/test_company_director.py/test_course.py for
    the fields it exposes) — the only behaviour unique to this model is set_values()
    activating the EMS auto-checkout cron."""

    def _get_cron(self):
        return self.env.ref('hr_attendance.hr_attendance_check_out_cron', raise_if_not_found=False)

    def test_set_values_activates_cron_when_mode_is_ems(self):
        cron = self._get_cron()
        if not cron:
            self.skipTest("hr_attendance_check_out_cron not present in this database")
        cron.sudo().write({'active': False})

        settings = self.env['res.config.settings'].create({
            'auto_checkout_mode': 'ems',
            'auto_checkout_time': 18.5,
        })
        settings.set_values()

        self.assertTrue(cron.active)
        self.assertEqual(cron.interval_number, 1)
        self.assertEqual(cron.interval_type, 'hours')

    def test_set_values_leaves_cron_untouched_when_mode_is_native(self):
        cron = self._get_cron()
        if not cron:
            self.skipTest("hr_attendance_check_out_cron not present in this database")
        cron.sudo().write({'active': False})

        settings = self.env['res.config.settings'].create({'auto_checkout_mode': 'native'})
        settings.set_values()

        self.assertFalse(cron.active)
