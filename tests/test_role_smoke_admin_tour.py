# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import ROLE_GROUP_XMLIDS, create_role_employee, create_role_user, mock_outgoing_email

# Every EMS administration role, plus Director and Head of Studies, so the crawler reaches
# every EMS menu.
ADMIN_ROLES = [role for role in ROLE_GROUP_XMLIDS if role.endswith('_admin')] + [
    'director', 'head_of_studies',
]


@tagged('post_install', '-at_install')
class TestRoleSmokeAdminTour(HttpCase):
    """Generic crawler covering every EMS screen an administrator reaches - see CLAUDE.md's
    "Per-role smoke tours". Not a feature test: asserts nothing about the data shown, only
    that no reachable EMS action/view_mode crashes. Replaces the catalog tours that only
    created and saved a record (issue #566)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Saving an employee with no corporate email posts a chatter note - see CLAUDE.md's
        # "Email safety in tests".
        mock_outgoing_email(cls)
        cls.admin_user = create_role_user(cls, ADMIN_ROLES[0], 'test_role_smoke_admin', name='Role Smoke Admin')
        cls.admin_user.groups_id = [(4, cls.env.ref(ROLE_GROUP_XMLIDS[role]).id) for role in ADMIN_ROLES[1:]]
        create_role_employee(cls, cls.admin_user, name='Role Smoke Admin')

    def test_role_smoke_admin_tour(self):
        # Crawls every EMS action an administrator reaches - can take longer than the default 60s.
        self.start_tour("/odoo", "ems_role_smoke_admin", login='test_role_smoke_admin', timeout=300)
