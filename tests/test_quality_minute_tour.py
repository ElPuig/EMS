# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestQualityMinuteTour(HttpCase):
    """Browser coverage for the staff-facing minute screen.

    Logged in as a department head, which is the least-privileged role expected to write a
    department minute - not as an administrator, so a missing access row or an unreadable field
    shows up here rather than in production (the failure class of issue #434)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['hr.department'].create({'name': '0000 Minute Tour Department'})
        cls.user = create_role_user(cls, 'department_chief', 'minute.tour@example.com')
        create_role_employee(cls, cls.user, department_id=cls.department.id)

    def test_write_a_minute_tour(self):
        self.start_tour("/odoo", "ems_minute_write", login="minute.tour@example.com")
