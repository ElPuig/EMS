from unittest.mock import patch

from odoo.tests.common import TransactionCase


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
