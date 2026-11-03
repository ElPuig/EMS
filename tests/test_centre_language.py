# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase

from odoo.addons.ems.models.quality.common import scope_code


class TestCentreLanguage(TransactionCase):
    """The centre language (res.company.ems_lang, issue #746): what EMS writes itself is in it,
    and it is the language new contacts and users get."""

    def test_catalan_is_the_centre_language_and_the_default_of_new_contacts(self):
        self.assertEqual(self.env.company.ems_lang, 'ca_ES')
        self.assertEqual(self.env['ir.default']._get('res.partner', 'lang'), 'ca_ES')

    def test_another_centre_language_is_followed_by_what_ems_writes_and_by_new_users(self):
        if not self.env['res.lang']._lang_get('es_ES'):
            self.skipTest("needs Spanish installed")
        department = self.env['hr.department'].create({'name': 'Physics Test'})
        department.update_field_translations('name', {'ca_ES': 'Física Prova', 'es_ES': 'Física Prueba'})
        self.env.company.ems_lang = 'es_ES'
        self.assertEqual(self.env['ir.default']._get('res.partner', 'lang'), 'es_ES')
        self.assertEqual(self.env['res.partner'].create({'name': 'New Contact Test'}).lang, 'es_ES')
        self.assertEqual(self.env['ems.minute']._ems_centre_lang(), 'es_ES')
        self.assertEqual(scope_code(department), 'FISPRU', "the codes read the department's name in the centre language")

    def test_the_centre_language_cannot_be_empty(self):
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env.company.ems_lang = False
            self.env.company.flush_recordset()

    def test_install_and_upgrade_seed_catalan(self):
        """What post_init_hook and the upgrade run: Catalan, and as the default of new contacts."""
        if not self.env['res.lang']._lang_get('es_ES'):
            self.skipTest("needs Spanish installed")
        self.env.company.ems_lang = 'es_ES'
        self.env['res.company']._ems_seed_centre_lang()
        self.assertEqual(self.env.company.ems_lang, 'ca_ES')
        self.assertEqual(self.env['ir.default']._get('res.partner', 'lang'), 'ca_ES')
