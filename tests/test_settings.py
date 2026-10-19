from unittest.mock import MagicMock, patch

from odoo.addons.ems.models.settings import settings as settings_module
from odoo.modules.module import get_manifest
from odoo.tests.common import TransactionCase
from odoo.tools import config

RELEASE_URL = "https://github.com/ElPuig/EMS/releases/tag/v99.0.0.0.0"


class TestSettings(TransactionCase):
    """res.config.settings (models/settings/settings.py) is a thin related-field proxy over
    res.company (see test_company_settings.py/test_company_director.py/test_course.py for
    the fields it exposes) — the only behaviour unique to this model is set_values()
    activating the EMS auto-checkout cron, and the installed/latest EMS version it shows."""

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

    def test_ems_version_is_the_installed_one(self):
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(settings.ems_version, get_manifest('ems')['version'])

    def _settings_with_latest(self, release):
        """A settings record as the form opens it, with GitHub answering `release`."""
        Settings = type(self.env['res.config.settings'])
        with patch.object(Settings, '_fetch_latest_ems_release', return_value=release):
            return self.env['res.config.settings'].create({})

    def test_version_status_latest(self):
        installed = get_manifest('ems')['version']
        settings = self._settings_with_latest({'version': installed, 'url': RELEASE_URL})
        self.assertEqual(settings.ems_version_status, 'latest')

    def test_version_status_latest_when_installed_is_ahead(self):
        # A development branch already carries the next version in its manifest.
        settings = self._settings_with_latest({'version': '18.0.0.0.1', 'url': RELEASE_URL})
        self.assertEqual(settings.ems_version_status, 'latest')

    def test_version_status_outdated_links_the_release(self):
        settings = self._settings_with_latest({'version': '99.0.0.0.0', 'url': RELEASE_URL})
        self.assertEqual(settings.ems_version_status, 'outdated')
        self.assertIn(f'href="{RELEASE_URL}"', settings.ems_version_message)
        self.assertIn('99.0.0.0.0', settings.ems_version_message)

    def test_version_status_unknown(self):
        settings = self._settings_with_latest(None)
        self.assertEqual(settings.ems_version_status, 'unknown')

    def test_check_again_waits_longer(self):
        Settings = type(self.env['res.config.settings'])
        with patch.object(Settings, '_fetch_latest_ems_release', return_value=None) as fetch:
            self.env['res.config.settings'].create({})
            fetch.assert_called_once_with(settings_module.LATEST_VERSION_TIMEOUT)
            fetch.reset_mock()
            self.env['res.config.settings'].with_context(ems_check_version_again=True).create({})
            fetch.assert_called_once_with(settings_module.LATEST_VERSION_RETRY_TIMEOUT)

    def test_fetch_takes_newest_published_release(self):
        response = MagicMock()
        response.json.return_value = [
            {'tag_name': 'v99.0.0.1.0', 'html_url': 'draft', 'draft': True},
            {'tag_name': 'v99.0.0.0.0', 'html_url': RELEASE_URL, 'draft': False, 'prerelease': True},
        ]
        with patch.dict(config.options, {'test_enable': False}), \
                patch.object(settings_module.requests, 'get', return_value=response) as get:
            release = self.env['res.config.settings']._fetch_latest_ems_release(2)
        self.assertEqual(release, {'version': '99.0.0.0.0', 'url': RELEASE_URL})
        self.assertEqual(get.call_args.kwargs['timeout'], 2)

    def test_fetch_failure_returns_none(self):
        with patch.dict(config.options, {'test_enable': False}), \
                patch.object(settings_module.requests, 'get', side_effect=settings_module.requests.Timeout):
            self.assertIsNone(self.env['res.config.settings']._fetch_latest_ems_release(2))
