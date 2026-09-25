# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_role_user


@tagged('post_install', '-at_install')
class TestUserMenuDocumentationTour(HttpCase):
    """Issue #516: the user menu's "Documentation" entry opens EMS's user manuals in the
    user's own language (ca/es/en), falling back to English for any other language."""

    def test_documentation_link_catalan(self):
        create_role_user(self, 'teacher', 'test_516_doc_ca', lang='ca_ES')
        self.start_tour("/odoo", "ems_user_menu_documentation_ca_tour", login="test_516_doc_ca")

    def test_documentation_link_english_fallback(self):
        # fr_FR has no docs tree of its own - must fall back to English, not a broken /fr/ URL.
        self.env['res.lang']._activate_lang('fr_FR')
        create_role_user(self, 'teacher', 'test_516_doc_fr', lang='fr_FR')
        self.start_tour("/odoo", "ems_user_menu_documentation_en_fallback_tour", login="test_516_doc_fr")
