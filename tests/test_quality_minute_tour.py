# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_role_employee, create_role_user, mock_outgoing_email


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
        # The draft is emailed to whoever attended (issue #755): nothing leaves this box from a test.
        employee.work_email = 'minute.tour@example.com'
        cls.mail_transport = mock_outgoing_email(cls)
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

    def test_attendance_lists_exclude_each_other_tour(self):
        alpha, beta = (
            create_role_employee(self, create_role_user(self, 'teacher', f'minute.drag.{key}@example.com', name=f'Drag Tour {key.title()}'))
            for key in ('alpha', 'beta'))
        writer = self.env['hr.employee.public'].browse(self.user.employee_id.id)
        minute = self.env['ems.minute'].create({
            'type_id': self.env.ref('__import__.minute_type_dep').id,
            'department_id': self.department.id,
            'attendance_mode': 'manual',
            'attendee_ids': [(6, 0, [writer.id, alpha.id, beta.id])],
            'redactor_employee_id': writer.id,
            'approver_employee_id': writer.id,
        })
        minute.action_start_meeting()
        self.start_tour(f"/odoo/action-ems.action_minute/{minute.id}", "ems_minute_attendance_lists", login="minute.tour@example.com")
        self.assertEqual(set(minute.absentee_ids.ids), {alpha.id, beta.id})
        self.assertEqual(minute.attendee_ids.ids, [writer.id])

    def test_autosave_keeps_the_focus_tour(self):
        """Issue #755: the save the minute does by itself while it is being written must not take
        the cursor out of the text box, for an item already saved and for one just added."""
        writer = self.env['hr.employee.public'].browse(self.user.employee_id.id)
        minute = self.env['ems.minute'].create({
            'type_id': self.env.ref('__import__.minute_type_dep').id,
            'department_id': self.department.id,
            'attendance_mode': 'manual',
            'redactor_employee_id': writer.id,
            'approver_employee_id': writer.id,
            'agenda_ids': [(0, 0, {'name': 'First item'})],
        })
        minute.action_start_meeting()
        Minute = type(self.env['ems.minute'])
        saves = []
        web_save = Minute.web_save

        def counted_web_save(records, *args, **kwargs):
            saves.append(records.id)
            return web_save(records, *args, **kwargs)

        with patch.object(Minute, 'web_save', counted_web_save):
            self.start_tour(f"/odoo/action-ems.action_minute/{minute.id}", "ems_minute_autosave_keeps_focus", login="minute.tour@example.com")
        self.assertGreaterEqual(len(saves), 3, "the form saved by itself twice (an existing item, a new one), then by hand")
        self.assertEqual(minute.agenda_ids.mapped('name'), ['First item', 'Second item'])
        self.assertIn('First words and more', minute.agenda_ids[0].notes)
        self.assertIn('New words and more', minute.agenda_ids[1].notes)

    def test_send_for_approval_with_the_draft_tour(self):
        """Issue #755: sending a minute for approval offers to send its draft to everybody convened;
        afterwards it can be sent again from the Actions."""
        writer = self.env['hr.employee.public'].browse(self.user.employee_id.id)
        minute = self.env['ems.minute'].create({
            'type_id': self.env.ref('__import__.minute_type_dep').id,
            'department_id': self.department.id,
            'attendance_mode': 'manual',
            'attendee_ids': [(6, 0, writer.ids)],
            'redactor_employee_id': writer.id,
            'approver_employee_id': writer.id,
        })
        minute.section_value_ids.filtered('required').content = "<p>Discussed.</p>"
        minute.action_start_meeting()
        self.start_tour(f"/odoo/action-ems.action_minute/{minute.id}", "ems_minute_submit_with_draft", login="minute.tour@example.com")
        self.assertEqual(minute.state, 'to_approve')
        # Written in the centre's language: found by the minute, the only mail it sends here.
        drafts = self.env['mail.mail'].sudo().search([('model', '=', 'ems.minute'), ('res_id', '=', minute.id)])
        self.assertEqual(len(drafts), 2, "with the approval, and again from the Actions")
        self.assertIn('minute.tour@example.com', drafts[0].email_to)

