# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestQualityTour(HttpCase):
    """Browser coverage for the screens phase 1 delivers.

    Logged in as the quality coordination role rather than admin: that is the least-privileged
    role the screens are meant for, and it is the only way these tours would catch a missing
    access row or a field the role cannot read (the failure class of issue #434)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_role_user(cls, 'quality_admin', 'quality.tour@example.com')
        create_role_employee(cls, cls.user, employee_type='asp')
        # The action tour needs at least one department to pick as the scope, and the registry
        # tour needs at least one procedure; both come from the module's own seeded data, but a
        # fresh test database may be built before that data lands, so make it explicit.
        if not cls.env['hr.department'].search([], limit=1):
            cls.env['hr.department'].create({'name': 'Quality Tour Department'})
        if not cls.env['ems.quality.procedure'].search([], limit=1):
            process = cls.env['ems.quality.process'].create({'code': 'ZT1', 'name': 'Tour process', 'kind': 'support'})
            procedure = cls.env['ems.quality.procedure'].create({'code': 'ZT1.01', 'name': 'Tour procedure', 'process_id': process.id})
            cls.env['ems.quality.document'].create({'code': 'ZT1.01.01', 'name': 'Tour document', 'procedure_id': procedure.id})
        # A fictitious published address: the tour only checks that the screen embeds whatever
        # the setting holds, and a test must never depend on reaching the real document.
        cls.env.company.quality_process_map_url = "https://docs.google.com/document/d/e/2PACX-tour/pub?embedded=true"

    def test_document_registry_tour(self):
        self.start_tour("/odoo", "ems_quality_registry", login="quality.tour@example.com")

    def test_action_followup_tour(self):
        self.start_tour("/odoo", "ems_quality_action_followup", login="quality.tour@example.com")
