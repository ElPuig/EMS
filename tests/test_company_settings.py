from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools import config


class TestCompanySettings(TransactionCase):
    """Covers the res.company fields/logic not already exercised by
    test_company_director.py (director_id) or test_course.py (current_course_id sync)."""

    def test_limesurvey_pwd_roundtrip(self):
        self.env.company.limesurvey_pwd = 'Test Secret Password 123'

        self.assertTrue(self.env.company.limesurvey_pwd_encrypted)
        self.assertNotEqual(self.env.company.limesurvey_pwd_encrypted, 'Test Secret Password 123')
        self.assertEqual(self.env.company.limesurvey_pwd, 'Test Secret Password 123')

    def test_limesurvey_pwd_cleared(self):
        self.env.company.limesurvey_pwd = 'Something'
        self.env.company.limesurvey_pwd = False
        self.assertFalse(self.env.company.limesurvey_pwd_encrypted)
        self.assertFalse(self.env.company.limesurvey_pwd)

    def test_google_ws_sa_json_roundtrip(self):
        self.env.company.google_ws_sa_json = '{"type": "service_account", "test": true}'

        self.assertTrue(self.env.company.google_ws_sa_json_encrypted)
        self.assertNotEqual(self.env.company.google_ws_sa_json_encrypted, '{"type": "service_account", "test": true}')
        self.assertEqual(self.env.company.google_ws_sa_json, '{"type": "service_account", "test": true}')

    def test_google_ws_sa_json_cleared(self):
        self.env.company.google_ws_sa_json = '{"a": 1}'
        self.env.company.google_ws_sa_json = False
        self.assertFalse(self.env.company.google_ws_sa_json_encrypted)
        self.assertFalse(self.env.company.google_ws_sa_json)

    def test_get_fernet_key_missing_secret_raises(self):
        with patch('odoo.addons.ems.models.settings.company.config.get', return_value=None):
            with self.assertRaises(ValueError):
                self.env.company._get_fernet_key()

    def test_decrypt_with_garbage_encrypted_value_returns_false(self):
        # Simulate corrupted/foreign data in the encrypted column: decrypting must not raise,
        # it should degrade to an empty value.
        self.env.company.limesurvey_pwd_encrypted = 'not-a-valid-fernet-token'
        self.assertFalse(self.env.company.limesurvey_pwd)

    def _clear_environment_type(self):
        self.env['ir.config_parameter'].sudo().search([('key', '=', 'ems.environment_type')]).unlink()

    def test_register_hook_warns_when_environment_type_unset(self):
        self._clear_environment_type()
        # test_enable is always True for any real test run - patched False here to exercise the
        # "not a throwaway test database" branch the hook is actually meant to guard.
        with patch.dict(config.options, {'test_enable': False}):
            with self.assertLogs('odoo.addons.ems.models.settings.company', level='WARNING') as captured:
                self.env.company._register_hook()
        self.assertIn('ems.environment_type', captured.output[0])

    def test_register_hook_silent_when_environment_type_set(self):
        self.env['ir.config_parameter'].sudo().set_param('ems.environment_type', 'dev')
        with patch.dict(config.options, {'test_enable': False}):
            with self.assertRaises(AssertionError):
                # assertLogs itself raises AssertionError when nothing was logged - the most
                # portable way to assert "no warning fired" across Python versions.
                with self.assertLogs('odoo.addons.ems.models.settings.company', level='WARNING'):
                    self.env.company._register_hook()

    def test_register_hook_silent_during_a_real_test_run(self):
        self._clear_environment_type()
        # No patching here: config['test_enable'] is genuinely True for this test run itself,
        # exactly the condition that must always suppress the warning.
        with self.assertRaises(AssertionError):
            with self.assertLogs('odoo.addons.ems.models.settings.company', level='WARNING'):
                self.env.company._register_hook()
