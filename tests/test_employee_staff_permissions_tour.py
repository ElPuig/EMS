# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email


@tagged('post_install', '-at_install')
class TestEmployeeStaffPermissionsTour(HttpCase):
    """Issue #391, browser side: a real Head of Studies session must be able to open the
    Teachers screen, edit a teacher, create a new one and see the Google Workspace buttons."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Saving a teacher with no corporate email posts a chatter note
        # (_gw_notify_missing_fields) - see CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)
        # Logged in as a real Head of Studies, not admin: the whole point of this tour is
        # what THIS group can do, and admin would pass every step regardless.
        login = 'test_391_hos_tour'
        cls.hos_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Staff Perms Tour HoS',
            'login': login,
            'password': login,
            # Pinned so the tour's ":contains('Private Information')" tab selector does not
            # depend on whatever language this database happens to default to.
            'lang': 'en_US',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('ems.group_head_of_studies').id),
            ],
        })
        # "0000 " prefix: hr.employee's default _order is "name", so these sort first on the
        # list's very first page among the pre-existing teachers in this DB (same trick as
        # test_employee_google_workspace_tour.py).
        cls.teacher = cls.env['hr.employee'].create({
            'name': '0000 Staff Perms Teacher',
            'employee_type': 'teacher',
            'private_email': 'staff.perms.teacher@example.com',
        })

    def test_employee_staff_permissions_tour(self):
        # To watch this tour in a real browser during development, add watch=True below.
        self.start_tour("/odoo", "ems_employee_staff_permissions", login='test_391_hos_tour')
