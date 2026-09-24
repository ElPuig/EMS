from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestSettingsTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The tour toggles this checkbox once and checks it ends up checked - start from a
        # known, deterministic state rather than assuming this dev DB's current value.
        cls.env.company.google_ws_enabled = False

    def test_settings_edit_tour(self):
        # The tour picks a month by its English label.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_settings_edit", login="admin")
