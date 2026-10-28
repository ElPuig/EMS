from unittest.mock import patch

from odoo.addons.ems.models.settings.settings import LATEST_VERSION_RETRY_TIMEOUT
from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestSettingsTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The tour toggles this checkbox once and checks it ends up checked - start from a
        # known, deterministic state rather than assuming this dev DB's current value.
        cls.env.company.google_ws_enabled = False
        # Issue #718: the levels that may come in later only show once that change is on.
        cls.env.company.write({'ems_absence_change_late_entry': False, 'ems_absence_change_early_leave': False})
        create_level_study(cls, 'TSTR')
        # GitHub "doesn't answer" in time when the page opens and does on "Check again", which
        # waits longer: the tour sees both states without any real network call.
        release = {'version': '99.0.0.0.0', 'url': 'https://github.com/ElPuig/EMS/releases/tag/v99.0.0.0.0'}
        patcher = patch.object(
            type(cls.env['res.config.settings']), '_fetch_latest_ems_release',
            side_effect=lambda timeout: release if timeout == LATEST_VERSION_RETRY_TIMEOUT else None,
        )
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def test_settings_edit_tour(self):
        # The tour picks a month by its English label.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_settings_edit", login="admin")
