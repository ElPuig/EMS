# -*- coding: utf-8 -*-

from odoo.tests import HttpCase, tagged

from .test_portal_schedule import create_portal_schedule_fixtures


@tagged('post_install', '-at_install')
class TestPortalScheduleTour(HttpCase):
    """Issue #453 - proves the portal schedule page (grid, Subject/Teacher(s) table, PDF button)
    actually renders in a browser for a real portal student. Access scoping and the PDF itself are
    covered by tests/test_portal_schedule.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_portal_schedule_fixtures(cls)

    def test_portal_schedule_render_tour(self):
        self.start_tour("/my/asistencia", "ems_portal_schedule_render", login=self.student_user.login)
