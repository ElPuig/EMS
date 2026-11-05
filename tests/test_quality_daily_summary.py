# -*- coding: utf-8 -*-

from datetime import timedelta
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user, mock_outgoing_email


class TestQualityDailySummary(TransactionCase):
    """Issue #753: Quality reaches the staff through their daily summary, never an email of its
    own. The responsible people of an agreement get a task while it is open and a notice for each
    follow-up entry; the people involved get nothing (the minute tells them). Whoever is to approve
    a minute gets a task. What a minute decides is told once it is approved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        # Notices and the follow-up's note are written in the source language in these tests.
        centre_lang = patch.object(type(cls.env['ems.minute']), '_ems_centre_lang', lambda self: 'en_US')
        centre_lang.start()
        cls.addClassCleanup(centre_lang.stop)
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.department = cls.env['hr.department'].create({'name': 'Summary Quality Department'})
        cls.type = cls.env.ref('__import__.minute_type_dep')
        cls.today = cls.env['ems.datetime_utils'].get_local_today()

        def person(login, name, role='teacher'):
            user = create_role_user(cls, role, f'{login}@example.com', name=name, lang='en_US')
            employee = create_role_employee(cls, user, department_id=cls.department.id)
            return user, cls.env['hr.employee.public'].browse(employee.id)

        cls.writer, cls.writer_employee = person('qsum.writer', 'QSum Writer')
        cls.responsible, cls.responsible_employee = person('qsum.responsible', 'QSum Responsible')
        cls.other_responsible, cls.other_responsible_employee = person('qsum.responsible2', 'QSum Second Responsible')
        cls.involved, cls.involved_employee = person('qsum.involved', 'QSum Involved')
        cls.approver, cls.approver_employee = person('qsum.approver', 'QSum Approver', role='department_chief')
        cls.task_type = cls.env.ref('ems.mail_activity_quality_agreement')
        cls.approval_type = cls.env.ref('ems.mail_activity_minute_approval')

    def _action(self, **overrides):
        vals = {
            'name': 'Update the practical syllabus', 'course_id': self.course.id, 'department_id': self.department.id,
            'responsible_employee_ids': [(6, 0, self.responsible_employee.ids)],
            'involved_employee_ids': [(6, 0, self.involved_employee.ids)],
        }
        vals.update(overrides)
        return self.env['ems.quality.action'].create(vals)

    def _minute(self):
        minute = self.env['ems.minute'].create({
            'type_id': self.type.id, 'date': self.today, 'department_id': self.department.id, 'course_id': self.course.id,
            'redactor_employee_id': self.writer_employee.id, 'approver_employee_id': self.approver_employee.id,
        })
        minute.section_value_ids.filtered('required').content = "<p>Discussed.</p>"
        return minute

    def _tasks(self, record, activity_type):
        return record.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)

    def _notices(self, user, action=None):
        domain = [('user_id', '=', user.id), ('res_model', '=', 'ems.quality.action')]
        if action:
            domain.append(('res_id', '=', action.id))
        return self.env['ems.info_notice'].sudo().search(domain)

    def _follow_up(self, action, user, **vals):
        return self.env['ems.quality.followup'].with_user(user).create({
            'action_id': action.id, 'description': 'Syllabus drafted, pending the department.', **vals})

    # --- Agreements -----------------------------------------------------------------------------

    def test_only_the_responsible_people_follow_it(self):
        action = self._action()
        self.assertIn(self.responsible.partner_id, action.message_partner_ids)
        self.assertNotIn(self.involved.partner_id, action.message_partner_ids,
                         "the people involved are told by the minute, not by following the agreement")

    def test_a_follow_up_is_a_notice_for_the_responsible_people_not_an_email(self):
        action = self._action(responsible_employee_ids=[(6, 0, (self.responsible_employee | self.other_responsible_employee).ids)])
        self.mail_transport.reset_mock()
        followup = self._follow_up(action, self.responsible, state='in_progress')

        self.assertFalse(self._notices(self.responsible, action).filtered(lambda notice: 'follow-up' in notice.body),
                         "whoever writes the entry is not told of it")
        notice = self._notices(self.other_responsible, action).filtered(lambda notice: 'follow-up' in notice.body)
        self.assertEqual(len(notice), 1)
        self.assertIn('QSum Responsible', notice.body, "who wrote it")
        self.assertIn('Syllabus drafted', notice.body, "what happened")
        self.assertIn('In progress', notice.body, "the state it leaves the agreement in")
        self.assertIn('Summary Quality Department', notice.body, "and enough about the agreement to understand it")
        self.assertFalse(self._notices(self.involved), "the people involved get nothing")

        note = action.message_ids.filtered(lambda message: 'Syllabus drafted' in (message.body or ''))
        self.assertTrue(note, "the entry stays in the agreement's history")
        self.assertTrue(note.subtype_id.internal, "as an internal note")
        self.assertFalse(note.notified_partner_ids, "which notifies nobody")
        self.mail_transport.assert_not_called()
        self.assertTrue(followup)

    def test_a_responsible_person_gets_a_task_due_on_the_deadline_and_a_notice_now(self):
        deadline = self.today + timedelta(days=30)
        action = self._action(deadline_date=deadline)
        task = self._tasks(action, self.task_type)
        self.assertEqual(task.user_id, self.responsible)
        self.assertEqual(task.date_deadline, deadline)
        notice = self._notices(self.responsible, action)
        self.assertEqual(len(notice), 1, "the task only shows once due: they are told of the agreement now")
        self.assertIn('You are responsible', notice.body)
        self.assertFalse(self._tasks(action, self.task_type).filtered(lambda task: task.user_id == self.involved))

    def test_without_a_deadline_the_task_is_due_today_and_no_notice_is_needed(self):
        action = self._action()
        self.assertEqual(self._tasks(action, self.task_type).date_deadline, self.today)
        self.assertFalse(self._notices(self.responsible, action))

    def test_the_holders_of_the_responsible_post_get_the_task(self):
        role = self.env['ems.role'].create({'name': 'QSum Post', 'employee_type': 'teacher',
                                            'employee_ids': [(6, 0, self.other_responsible_employee.ids)]})
        action = self._action(responsible_role_id=role.id)
        self.assertEqual(self._tasks(action, self.task_type).user_id, self.responsible | self.other_responsible)

    def test_tasks_follow_the_responsible_people_and_the_deadline(self):
        action = self._action()
        action.responsible_employee_ids = self.other_responsible_employee
        self.assertEqual(self._tasks(action, self.task_type).user_id, self.other_responsible,
                         "whoever stops answering for it loses the task")
        later = self.today + timedelta(days=10)
        action.deadline_date = later
        self.assertEqual(self._tasks(action, self.task_type).date_deadline, later)

    def test_closing_the_agreement_marks_the_task_done(self):
        action = self._action()
        self._follow_up(action, self.responsible, state='closed')
        self.assertFalse(self._tasks(action, self.task_type), "done: off the list")
        done = self.env['mail.message'].search([('model', '=', action._name), ('res_id', '=', action.id),
                                                ('mail_activity_type_id', '=', self.task_type.id)])
        self.assertTrue(done, "and recorded as done in its history")

    # --- Minutes --------------------------------------------------------------------------------

    def test_the_approver_gets_a_task_while_the_minute_waits(self):
        minute = self._minute()
        minute.action_start_meeting()
        self.assertFalse(self._tasks(minute, self.approval_type))
        minute.action_submit()
        task = self._tasks(minute, self.approval_type)
        self.assertEqual(task.user_id, self.approver)
        self.assertEqual(task.date_deadline, self.today)
        minute.action_back_to_meeting()
        self.assertFalse(self._tasks(minute, self.approval_type), "no longer waiting for approval")
        minute.action_submit()
        minute.action_approve()
        self.assertFalse(self._tasks(minute, self.approval_type), "approved: done")

    def test_the_holders_of_the_approving_post_get_the_task_when_nobody_is_named(self):
        role = self.env['ems.role'].create({'name': 'QSum Approving Post', 'employee_type': 'teacher',
                                            'employee_ids': [(6, 0, self.other_responsible_employee.ids)]})
        minute = self._minute()
        minute.write({'approver_employee_id': False, 'approver_role_id': role.id})
        minute.action_submit()
        self.assertEqual(self._tasks(minute, self.approval_type).user_id, self.other_responsible)

    def test_what_a_minute_agrees_is_told_once_it_is_approved(self):
        minute = self._minute()
        deadline = self.today + timedelta(days=20)
        minute.write({'agreement_ids': [
            (0, 0, {'name': 'Open agreement', 'deadline_date': deadline,
                    'responsible_employee_ids': [(6, 0, self.responsible_employee.ids)],
                    'involved_employee_ids': [(6, 0, self.involved_employee.ids)]}),
            (0, 0, {'name': 'Decided and done', 'is_closed_in_minute': True,
                    'responsible_employee_ids': [(6, 0, self.other_responsible_employee.ids)]}),
        ]})
        open_one, done = minute.agreement_ids.sorted('id')
        self.assertFalse(self._tasks(open_one, self.task_type), "nothing while the minute may still change")
        self.assertFalse(self._notices(self.responsible) | self._notices(self.other_responsible))

        minute.action_submit()
        minute.action_approve()
        self.assertEqual(self._tasks(open_one, self.task_type).user_id, self.responsible)
        self.assertIn('You are responsible', self._notices(self.responsible, open_one).body)
        self.assertIn(minute.code, self._notices(self.responsible, open_one).body, "names the meeting it comes from")
        self.assertFalse(self._tasks(done, self.task_type), "nothing to carry out")
        notice = self._notices(self.other_responsible, done)
        self.assertEqual(len(notice), 1)
        self.assertIn('Agreed and done in the meeting', notice.body)
        self.assertFalse(self._notices(self.involved))

    def test_a_review_in_a_later_minute_is_told_once_that_minute_is_approved(self):
        action = self._action()
        self.env['ems.info_notice'].sudo().search([('user_id', '=', self.responsible.id)]).unlink()
        minute = self._minute()
        minute.agreement_review_ids = [(0, 0, {'action_id': action.id, 'note': 'Half the units are done.'})]
        minute.agreement_review_ids.note = 'Two thirds of the units are done.'
        self.assertFalse(self._notices(self.responsible, action), "the minute may still change what it says")
        minute.action_submit()
        minute.action_approve()
        notice = self._notices(self.responsible, action)
        self.assertEqual(len(notice), 1)
        self.assertIn('Two thirds of the units', notice.body, "its final wording")

    def test_approving_again_after_undoing_it_tells_only_what_changed(self):
        """Undoing the approval to correct the minute and approving it again (issue #756) does not
        repeat what its people were already told; a reworded review is told again, and a person
        no longer responsible loses the task."""
        minute = self._minute()
        minute.write({'agreement_ids': [
            (0, 0, {'name': 'Open agreement', 'deadline_date': self.today + timedelta(days=20),
                    'responsible_employee_ids': [(6, 0, (self.responsible_employee | self.other_responsible_employee).ids)]}),
            (0, 0, {'name': 'Decided and done', 'is_closed_in_minute': True,
                    'responsible_employee_ids': [(6, 0, self.other_responsible_employee.ids)]}),
        ]})
        open_one, done = minute.agreement_ids.sorted('id')
        action = self._action()
        minute.agreement_review_ids = [(0, 0, {'action_id': action.id, 'note': 'Half the units are done.'})]
        minute.action_submit()
        minute.action_approve()
        before = {user: len(self._notices(user)) for user in (self.responsible, self.other_responsible)}

        minute.action_reopen()
        self.assertEqual(self._tasks(minute, self.approval_type).user_id, self.approver_employee.user_id,
                         "waiting for approval again")
        open_one.responsible_employee_ids = self.responsible_employee
        minute.agreement_review_ids.note = 'Two thirds of the units are done.'
        minute.action_approve()

        self.assertEqual(len(self._notices(self.other_responsible)), before[self.other_responsible],
                         "the agreement done in the meeting is not told twice")
        self.assertFalse(self._tasks(open_one, self.task_type).filtered(lambda task: task.user_id == self.other_responsible))
        self.assertEqual(len(self._notices(self.responsible, open_one)), 1, "nor the open one")
        reviews = self._notices(self.responsible, action).filtered(lambda notice: 'units are done' in notice.body)
        self.assertEqual(len(reviews), 2, "the reworded review is told again")
        self.assertIn('Two thirds', reviews[-1].body)
        self.assertEqual(len(self._notices(self.responsible)), before[self.responsible] + 1)

    def test_the_notice_reaches_the_daily_summary(self):
        action = self._action(deadline_date=self.today + timedelta(days=5))
        content = self.responsible._ems_daily_summary_content()
        self.assertIn(action.code, content['body'])
        self.assertIn('You are responsible', content['body'])

    # --- Edge cases and the recipients' own rights ----------------------------------------------

    def test_a_follow_up_on_an_agreement_of_a_minute_not_approved_is_not_told_yet(self):
        minute = self._minute()
        minute.agreement_ids = [(0, 0, {'name': 'Still being written',
                                        'responsible_employee_ids': [(6, 0, (self.responsible_employee | self.other_responsible_employee).ids)]})]
        self._follow_up(minute.agreement_ids, self.responsible)
        self.assertFalse(self._notices(self.other_responsible), "what the minute agrees may still change")

    def test_naming_another_approver_moves_the_task(self):
        minute = self._minute()
        minute.action_submit()
        minute.approver_employee_id = self.other_responsible_employee
        self.assertEqual(self._tasks(minute, self.approval_type).user_id, self.other_responsible)

    def test_the_responsible_person_opens_postpones_and_closes_their_task(self):
        """A task they could not open or act on would only be noise: the agreement is theirs to
        read (record rules) and the task theirs to postpone or mark done."""
        action = self._action()
        task = self._tasks(action, self.task_type).with_user(self.responsible)
        self.assertTrue(action.with_user(self.responsible).search([('id', '=', action.id)]))
        task.action_ems_snooze(3)
        self.assertEqual(task.date_deadline, self.today + timedelta(days=3))
        task.action_feedback()
        self.assertFalse(self._tasks(action, self.task_type))

    def test_the_approver_can_open_the_minute_of_their_task(self):
        minute = self._minute()
        minute.action_submit()
        self.assertEqual(self._tasks(minute, self.approval_type).user_id, self.approver)
        self.assertTrue(self.env['ems.minute'].with_user(self.approver).search([('id', '=', minute.id)]))
        self.assertTrue(minute.with_user(self.approver).can_approve)
