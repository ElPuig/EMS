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
        employee = create_role_employee(cls, cls.user, department_id=cls.department.id)
        # Only the department's own chiefs start its minutes (ems.minute.type.starter_scope).
        cls.department.manager_id = employee

    def test_write_a_minute_tour(self):
        self.start_tour("/odoo", "ems_minute_write", login="minute.tour@example.com")

    def test_attendee_reads_a_minute_tour(self):
        """A teacher who attended a meeting of another department opens its minute: they may read
        it but not write it, so the form opens read-only, with no action that would change it."""
        reader = create_role_user(self, 'teacher', 'minute.reader@example.com', name='Minute Tour Reader')
        reader_employee = create_role_employee(self, reader)
        writer = self.env['hr.employee.public'].browse(self.user.employee_id.id)
        minute = self.env['ems.minute'].create({
            'type_id': self.env.ref('__import__.minute_type_dep').id,
            'department_id': self.department.id,
            'attendee_ids': [(6, 0, [reader_employee.id])],
            'redactor_employee_id': writer.id,
            'approver_employee_id': writer.id,
        })
        minute.action_start_meeting()
        self.start_tour(f"/odoo/action-ems.action_minute/{minute.id}", "ems_minute_read_only", login="minute.reader@example.com")
