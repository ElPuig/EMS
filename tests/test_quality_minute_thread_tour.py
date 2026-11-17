# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_role_employee, create_role_user, ensure_catchall_address, mock_outgoing_email
from .test_quality_minute_thread import REPLY


@tagged('post_install', '-at_install')
class TestQualityMinuteThreadTour(HttpCase):
    """Browser coverage of a meeting held by email (issue #822), as a teacher: any teacher can
    open one, so it is the least-privileged role that uses the screen."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        cls.mail_transport.side_effect = lambda message, *args, **kwargs: message['Message-Id']
        cls.env.company.alias_domain_id.write({'bounce_alias': 'bounce.tmtt', 'catchall_alias': 'answers.tmtt'})
        cls.user = create_role_user(cls, 'teacher', 'thread.tour@example.com', name='TMTT Writer',
                                    email='thread.tour@example.com')
        writer = create_role_employee(cls, cls.user)
        writer.work_email = 'thread.tour@example.com'
        other = create_role_employee(cls, create_role_user(cls, 'teacher', 'thread.other@example.com', name='TMTT Other',
                                                           email='thread.other@example.com'))
        other.work_email = 'thread.other@example.com'
        public = cls.env['hr.employee.public']
        cls.minute = cls.env['ems.minute'].with_user(cls.user).create({
            'type_id': cls.env.ref('__import__.minute_type_email_thread').id,
            'scope_choice': 'none',
            'redactor_employee_id': writer.id,
            'attendee_ids': [(6, 0, (public.browse(writer.id) | public.browse(other.id)).ids)],
            'reply_deadline': fields.Date.today() + timedelta(days=7),
        })

    def test_open_a_thread_tour(self):
        self.start_tour(f"/odoo/action-ems.action_minute/{self.minute.id}", "ems_minute_thread_open", login="thread.tour@example.com")
        self.assertEqual(self.minute.state, 'meeting')

    def test_interventions_tour(self):
        self.minute.with_user(self.user).action_start_meeting()
        opening = self.minute.message_ids.filtered(lambda message: message.message_type == 'comment'
                                                   and message.subtype_id == self.env.ref('mail.mt_comment'))[:1]
        self.env['mail.thread'].message_process(False, REPLY.format(
            sender='TMTT Other <thread.other@example.com>', to=ensure_catchall_address(self),
            parent=opening.message_id, number=901, text='TMTT I agree with the item'))
        self.start_tour(f"/odoo/action-ems.action_minute/{self.minute.id}", "ems_minute_thread_interventions",
                        login="thread.tour@example.com")
