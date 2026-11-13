from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusMobilityCase, ErasmusStaffMobilityCase
from .test_erasmus_pocket_money import ErasmusPocketMoneyCase


@tagged('post_install', '-at_install')
class TestErasmusMobilityWarnings(ErasmusMobilityCase):
    """Issue #787 - the mobility says which step it is at and who has it, and what is missing."""

    def test_the_step_and_who_has_it(self):
        """5.3, 8.1: the destination choice, then what the record still needs."""
        first, _second = self._accepted()
        mobility = first.with_context(lang='en_US')
        first.call_id.choice_open = False
        self.assertEqual(mobility.step_note, "Waiting for the destination choice to open.")
        first.sudo().turn_deadline = '2030-01-10 17:00:00'
        self.assertIn("Their turn to choose the destination, until 10/01/2030", mobility.step_note)
        first.sudo().write({'turn_deadline': False, 'turn_missed': True})
        self.assertIn("Missed their turn", mobility.step_note)
        first.sudo().write({'state': 'preparing', 'turn_missed': False})
        if first.document_ids.filtered(lambda line: line.todo_state in ('missing', 'needs_change')):
            self.assertIn("Pending:", mobility.step_note)
        first.sudo().state = 'cancelled'
        self.assertFalse(mobility.step_note)

    def test_grant_missing_once_there_is_a_destination(self):
        """5.12: nothing calculates the grant, so its absence is said once there is a destination."""
        first, _second = self._accepted()
        self.assertFalse(first.grant_missing, "No destination yet.")
        first.sudo().write({'country_id': self.env.ref('base.ie').id, 'grant_amount': 0})
        self.assertTrue(first.grant_missing)
        first.sudo().grant_amount = 1200
        self.assertFalse(first.grant_missing)


@tagged('post_install', '-at_install')
class TestErasmusStaffSteps(ErasmusStaffMobilityCase):
    """Issue #787 - 8.8: the teacher sees the steps of their mobility and ticks theirs; P11, P14:
    their mobility says what to do now."""

    def test_the_teacher_ticks_their_steps(self):
        mobility = self._accepted_staff()
        if not mobility.task_ids.filtered(lambda step: step.stage == 'preparation'):
            self.staff_call.task_ids = [(0, 0, {'name': 'Test step'})]
            mobility._ems_sync_requirements()
        own = self.env(user=self.staff_users[0])['ems.erasmus.mobility'].browse(mobility.id)
        task = own.task_ids.filtered(lambda step: step.stage == 'preparation')[:1]
        self.assertTrue(task.staff_can_tick)
        task.action_staff_done()
        self.assertTrue(task.done)
        self.assertEqual(task.sudo().done_user_id, self.staff_users[0])
        self.assertTrue(task.staff_can_untick)
        task.action_staff_undo()
        self.assertFalse(task.done)
        # A step the team ticked stays the team's.
        mobility.task_ids[:1].with_user(self.erasmus_user).done = True
        task.invalidate_recordset()
        self.assertFalse(task.staff_can_untick)
        with self.assertRaises(UserError):
            task.action_staff_undo()
        # Another teacher reads nothing of it.
        other = self.env(user=self.staff_users[1])['ems.erasmus.mobility.task']
        self.assertFalse(other.search([('id', '=', task.id)]))
        # Nor ticks it, by its id or through the mobility.
        foreign = other.browse(task.id)
        with self.assertRaises(AccessError):
            foreign.read(['name', 'done'])
        self.assertFalse(foreign.staff_can_tick)
        with self.assertRaises(UserError):
            foreign.action_staff_done()
        with self.assertRaises(AccessError):
            foreign.write({'done': True})
        with self.assertRaises(AccessError):
            self.env(user=self.staff_users[1])['ems.erasmus.mobility'].browse(mobility.id).write(
                {'task_ids': [(1, task.id, {'done': True})]})
        # The owner can't change it by writing either: only the buttons do.
        with self.assertRaises(AccessError):
            task.write({'done': False})

    def test_return_steps_only_from_the_stay(self):
        """P17: a step on return is ticked by the teacher only once the stay has started (closed too);
        the team, always."""
        mobility = self._accepted_staff()
        self.staff_call.task_ids = [(0, 0, {'name': 'News piece', 'stage': 'return'})]
        mobility.sudo().write({'state': 'preparing'})
        mobility._ems_sync_requirements()
        own = self.env(user=self.staff_users[0])['ems.erasmus.mobility'].browse(mobility.id)
        task = own.task_ids.filtered(lambda step: step.stage == 'return')[:1]
        self.assertTrue(task, "The return step reaches the mobility.")
        today = fields.Date.today()
        mobility.sudo().write({'date_start': today + timedelta(days=10), 'date_end': today + timedelta(days=20)})
        task.invalidate_recordset()
        self.assertEqual(mobility.phase, 'preparing')
        self.assertFalse(task.staff_can_tick)
        with self.assertRaises(UserError):
            task.action_staff_done()
        mobility.sudo().write({'date_start': today - timedelta(days=1)})
        task.invalidate_recordset()
        self.assertEqual(mobility.phase, 'stay')
        self.assertTrue(task.staff_can_tick)
        mobility.sudo().write({'state': 'done'})
        task.invalidate_recordset()
        self.assertTrue(task.staff_can_tick, "A closed mobility still takes the return steps.")
        # The team ticks it whatever the phase.
        mobility.sudo().write({'state': 'preparing', 'date_start': today + timedelta(days=10)})
        mobility.task_ids.filtered(lambda step: step.stage == 'return')[:1].with_user(self.erasmus_user).done = True

    def test_the_teacher_mobility_says_what_to_do(self):
        mobility = self._accepted_staff()
        own = self.env(user=self.staff_users[0])['ems.erasmus.mobility'].browse(mobility.id).with_context(lang='en_US')
        self.assertEqual(own.staff_next_level, 'warning')
        self.assertIn("proposal", own.staff_next_step)
        self.assertIn("propose the activity", mobility.with_context(lang='en_US').step_note)
        self._send_proposal(mobility)
        own.invalidate_recordset()
        self.assertIn("waiting for validation", own.staff_next_step)
        mobility.invalidate_recordset()
        self.assertIn("Direction to validate", mobility.with_context(lang='en_US').step_note)


@tagged('post_install', '-at_install')
class TestErasmusExclusionReason(ErasmusMobilityCase):
    """Issue #787 - 3.3: the exclusion reason in the list and on top of the form."""

    def test_reason_in_list_and_form(self):
        form = etree.fromstring(self.env['ems.erasmus.application'].get_view(
            self.env.ref('ems.view_erasmus_application_form').id)['arch'])
        self.assertTrue(form.xpath("//div[contains(@class, 'alert')]/field[@name='exclusion_reason']"))
        tree = etree.fromstring(self.env['ems.erasmus.application'].get_view(
            self.env.ref('ems.view_erasmus_application_list').id)['arch'])
        self.assertTrue(tree.xpath("//field[@name='exclusion_reason']"))


@tagged('post_install', '-at_install')
class TestErasmusGroupWarnings(ErasmusPocketMoneyCase):
    """Issue #787 - the group mobility warns before starting the stay (9.5) and before paying the
    pocket money (9.16, 9.17)."""

    def test_grant_and_pocket_money_warnings(self):
        participants = self._ready()
        self.assertFalse(self.mobility.grant_missing)
        self.students[:1].grant_amount = 0
        self.assertEqual(self.mobility.grant_missing, self.students[:1].partner_id.name)
        self.students[:1].grant_amount = 1200
        self.assertFalse(self.mobility.pocket_negative)
        self._collective(1300 * len(participants.filtered(lambda participant: participant.state == 'active')))
        self.mobility.invalidate_recordset()
        self.assertIn(self.students[:1].partner_id.name, self.mobility.pocket_negative,
                      "A student's 1,200 € grant minus a 1,300 € share.")

    def test_start_warning(self):
        self._ready()
        today = self.env['ems.datetime_utils'].get_local_today()
        self.mobility.write({'host_partner_id': False, 'date_start': today + timedelta(days=30)})
        warning = self.mobility.with_context(lang='en_US').start_warning
        self.assertIn("no host entity", warning)
        self.assertIn("planned to start", warning)
        self.mobility.date_start = today
        self.assertNotIn("planned to start", self.mobility.with_context(lang='en_US').start_warning)
        self.mobility.action_start_stay()
        self.assertEqual(self.mobility.state, 'stay', "A warning, never a block.")
        self.assertFalse(self.mobility.start_warning)
