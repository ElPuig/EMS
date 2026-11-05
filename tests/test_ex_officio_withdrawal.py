# -*- coding: utf-8 -*-

from contextlib import ExitStack
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import format_date

from .common import (create_head_of_studies_branch, create_level_study_group, create_role_employee,
                     create_role_user, mock_outgoing_email, next_student_id)

POST_COMPULSORY_CODES = ['tutor_contact', 'secretariat_warning', 'direction_approval', 'withdrawal']
COMPULSORY_CODES = ['tutor_contact', 'coexistence_contact', 'secretariat_notice', 'social_services',
                    'secretariat_warning', 'direction_approval', 'withdrawal']


@tagged('post_install', '-at_install')
class TestExOfficioWithdrawal(TransactionCase):
    """Issue #726: the case file opened by hand, its steps and deadlines, who sees and decides it
    (phase 1), the steps done one after another, each its responsible's task (phase 2), and the
    emails to the family, the texts to copy and the case file PDF (phase 3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        cls.Withdrawal = cls.env['ems.ex_officio_withdrawal']
        cls.post_level, cls.post_study, cls.post_group = create_level_study_group(
            cls, 'TEOWP', level={'education_stage': 'post_compulsory'})
        cls.comp_level, cls.comp_study, cls.comp_group = create_level_study_group(
            cls, 'TEOWC', level={'education_stage': 'compulsory'})
        cls.none_level, cls.none_study, cls.none_group = create_level_study_group(cls, 'TEOWN')

        cls.tutor_user = create_role_user(cls, 'tutor', 'test_eow_tutor', name='EOW Tutor')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        create_head_of_studies_branch(cls, 'EOW', cls.tutor)
        cls.other_tutor_user = create_role_user(cls, 'tutor', 'test_eow_other_tutor', name='EOW Other Tutor')
        create_role_employee(cls, cls.other_tutor_user)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_eow_teacher', name='EOW Teacher')
        cls.coexistence_user = create_role_user(cls, 'coexistence', 'test_eow_coexistence', name='EOW Coexistence')
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_eow_secretary', name='EOW Secretary')
        (cls.post_group | cls.comp_group | cls.none_group).tutor_id = cls.tutor
        cls.director_user = create_role_user(cls, 'director', 'test_eow_director', name='EOW Director')
        cls.admin_user = create_role_user(cls, 'academic_admin', 'test_eow_admin', name='EOW Admin')
        cls.settings_admin_user = create_role_user(cls, 'settings_admin', 'test_eow_settings_admin',
                                                   name='EOW Settings Admin')
        # A Coexistence coordinator under the tutor's own Head of Studies, and one under another.
        role_coexistence = cls.env.ref('ems.role_coexistence')
        create_role_employee(cls, cls.coexistence_user, parent_id=cls.head_of_studies.employee_id.id,
                             role_ids=[(4, role_coexistence.id)])
        cls.other_coexistence_user = create_role_user(cls, 'coexistence', 'test_eow_other_coexistence',
                                                      name='EOW Other Coexistence')
        create_role_employee(cls, cls.other_coexistence_user, parent_id=cls.other_head_of_studies.employee_id.id,
                             role_ids=[(4, role_coexistence.id)])

        cls.post_student = cls._student('EOW Post Student', cls.post_group)
        cls.comp_student = cls._student('EOW Comp Student', cls.comp_group)
        cls.none_student = cls._student('EOW None Student', cls.none_group)

        # A Christmas break of the centre in a year nobody configures, so the dev database's own
        # calendar never interferes: 23 December 2041 to 7 January 2042, both included.
        utils = cls.env['ems.datetime_utils']
        cls.env['resource.calendar.leaves'].create({
            'name': 'EOW Christmas break',
            'date_from': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(date(2041, 12, 23), 0.0)),
            'date_to': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(date(2042, 1, 8), 0.0)),
        })

    @classmethod
    def _student(cls, name, group):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id, 'email': f"{name.lower().replace(' ', '.')}@example.com",
        })

    def _on(self, day):
        """Run as if today were `day` in the company's calendar."""
        return patch.object(type(self.env['ems.datetime_utils']), 'get_local_today', return_value=day)

    def _tasks(self, case_file, xmlid):
        return case_file.activity_ids.filtered(lambda activity: activity.activity_type_id == self.env.ref(xmlid))

    def _accept(self, case_file, user, day, tick=True):
        """`user` ticks every action the current step asks for (done on `day`), sends its email to
        the family when it has one (the only way that one gets ticked) and accepts it on `day`, the
        hourly job having run first."""
        with self._on(day):
            self.Withdrawal._cron_ems_due_step_tasks()
            if tick:
                checks = case_file.current_check_ids
                checks.filtered(lambda check: not check.by_button).with_user(user).write({'done': True, 'date': day})
                if checks.filtered(lambda check: check.by_button and not check.done):
                    self._contact(case_file, user, day, outcome='reached'
                                  if case_file.call_step else None).action_confirm()
            case_file.with_user(user).action_accept_step()

    def _open(self, student, first_absence, user=None):
        model = self.Withdrawal.with_user(user) if user else self.Withdrawal
        return model.create({'student_id': student.id, 'first_absence_date': first_absence})

    # --- deadlines ---------------------------------------------------------------------------

    def test_post_compulsory_deadlines_are_school_days_skipping_the_break(self):
        """D0 (a Tuesday) counts as the first day of absence; weekends and the break don't."""
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self.assertEqual(case_file.step_ids.mapped('code'), POST_COMPULSORY_CODES)
        self.assertEqual(case_file.step_ids.mapped('due_date'), [
            date(2042, 1, 8), date(2042, 1, 15), date(2042, 1, 22), date(2042, 1, 22)])
        self.assertEqual(case_file.step_ids.mapped('responsible'),
                         ['tutor', 'secretariat', 'direction', 'secretariat'])
        self.assertEqual(case_file.current_step_id.display_name, 'Contact with the family',
                         "The list's Current step column names it")

    def test_compulsory_deadlines_are_calendar_days_and_months(self):
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        self.assertEqual(case_file.step_ids.mapped('code'), COMPULSORY_CODES)
        self.assertEqual(case_file.step_ids.mapped('due_date'), [
            date(2041, 3, 11), date(2041, 3, 19), date(2041, 4, 4), date(2041, 4, 4),
            date(2041, 4, 19), date(2041, 5, 4), date(2041, 5, 4)])

    def test_steps_ask_only_for_their_own_checks(self):
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        checks = {step.code: step.check_ids.mapped('code') for step in case_file.step_ids}
        self.assertEqual(checks, {
            'tutor_contact': ['phone'], 'coexistence_contact': ['phone'], 'secretariat_notice': ['family_email'],
            'social_services': ['social_services_email'], 'secretariat_warning': ['family_email', 'enotum'],
            'direction_approval': ['approval', 'inspection_email'], 'withdrawal': ['esfera']})
        self.assertEqual(case_file.current_check_ids.mapped('code'), ['phone'],
                         "The case file only offers the current step's checks")

    # --- the case file -----------------------------------------------------------------------

    def test_manual_case_file_takes_the_students_group_and_circuit(self):
        case_file = self._open(self.post_student, date(2041, 12, 17), user=self.tutor_user)
        self.assertRegex(case_file.name, r'^BO-\d{4}-\d{2}-\d{4}$')
        self.assertEqual(case_file.group_id, self.post_group)
        self.assertEqual(case_file.level_id, self.post_level)
        self.assertEqual(case_file.circuit, 'post_compulsory')
        self.assertEqual(case_file.tutor_id, self.tutor)
        self.assertEqual(case_file.origin, 'manual')
        self.assertEqual(case_file.state, 'proposal')
        self.assertFalse(case_file.step_ids)

    def test_level_without_educational_stage_is_refused(self):
        with self.assertRaises(UserError):
            self._open(self.none_student, date(2041, 3, 4))

    def test_one_open_case_file_per_student(self):
        first = self._open(self.post_student, date(2041, 12, 17))
        with self.assertRaises(ValidationError):
            self._open(self.post_student, date(2041, 12, 18))
        first.action_dismiss('A test reason')
        self._open(self.post_student, date(2041, 12, 18))

    def test_dismiss_wizard_cancels_with_the_reason(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        wizard = self.env['ems.ex_officio_withdrawal.dismiss_wizard'].with_user(self.tutor_user).create({
            'withdrawal_id': case_file.id, 'note': 'Hospital stay, family called',
        })
        wizard.action_confirm()
        self.assertEqual(case_file.state, 'cancelled')
        self.assertEqual(case_file.cancel_reason, 'dismissed')
        self.assertEqual(case_file.cancel_note, 'Hospital stay, family called')

    def test_state_and_student_only_change_through_the_buttons(self):
        case_file = self._open(self.post_student, date(2041, 12, 17), user=self.tutor_user)
        with self.assertRaises(UserError):
            case_file.with_user(self.tutor_user).write({'state': 'done'})
        with self.assertRaises(UserError):
            case_file.with_user(self.tutor_user).write({'student_id': self.comp_student.id})

    # --- who sees and decides ----------------------------------------------------------------

    def test_visibility_per_role(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        for user in (self.tutor_user, self.department_chief, self.head_of_studies,
                     self.coexistence_user, self.secretary_user):
            self.assertEqual(self.Withdrawal.with_user(user).search([('id', '=', case_file.id)]), case_file,
                             user.login)
        self.assertFalse(self.Withdrawal.with_user(self.other_tutor_user).search([('id', '=', case_file.id)]))
        self.assertFalse(self.Withdrawal.with_user(self.other_department_chief).search(
            [('id', '=', case_file.id)]))
        with self.assertRaises(AccessError):
            self.Withdrawal.with_user(self.teacher_user).search([])

    def test_only_the_tutor_scope_opens_one_for_a_student(self):
        with self.assertRaises(AccessError):
            self._open(self.post_student, date(2041, 12, 17), user=self.other_tutor_user)
        with self.assertRaises(AccessError):
            self._open(self.post_student, date(2041, 12, 17), user=self.secretary_user)
        with self.assertRaises(AccessError):
            self._open(self.post_student, date(2041, 12, 17), user=self.other_head_of_studies)
        self._open(self.post_student, date(2041, 12, 17), user=self.department_chief)
        self._open(self.comp_student, date(2041, 12, 17), user=self.settings_admin_user)

    def test_who_decides_the_proposal(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        for user in (self.tutor_user, self.department_chief, self.head_of_studies, self.admin_user,
                     self.settings_admin_user):
            self.assertTrue(case_file.with_user(user).can_decide_proposal, user.login)
        for user in (self.coexistence_user, self.secretary_user):
            self.assertFalse(case_file.with_user(user).can_decide_proposal, user.login)
            with self.assertRaises(UserError):
                case_file.with_user(user).action_start()
        case_file.with_user(self.tutor_user).action_start()
        self.assertEqual((case_file.state, case_file.current_step_id.code), ('in_progress', 'tutor_contact'))
        with self.assertRaises(UserError):
            case_file.action_start()

    def test_student_smart_button_count(self):
        self._open(self.post_student, date(2041, 12, 17))
        self.assertEqual(self.post_student.with_user(self.tutor_user).ex_officio_withdrawal_count, 1)

    # --- phase 2: steps and tasks ------------------------------------------------------------

    def test_the_proposal_is_the_tutors_task_until_decided(self):
        case_file = self._open(self.post_student, date(2041, 12, 17), user=self.tutor_user)
        tasks = self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_proposal')
        self.assertEqual(tasks.user_id, self.tutor_user)
        self.assertIn('EOW Post Student', tasks.summary)
        with self._on(date(2041, 12, 17)):
            case_file.with_user(self.tutor_user).action_start()
        self.assertFalse(case_file.activity_ids, "Started, and no step is due yet")

    def test_post_compulsory_runs_from_the_tutor_to_the_secretariat(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        step_task = 'ems.mail_activity_ex_officio_withdrawal_step'

        with self._on(date(2042, 1, 8)):
            self.Withdrawal._cron_ems_due_step_tasks()
        task = self._tasks(case_file, step_task)
        self.assertEqual(task.user_id, self.tutor_user)
        self.assertEqual(task.date_deadline, date(2042, 1, 8))
        with self._on(date(2042, 1, 8)), self.assertRaises(UserError, msg="The phone call is not ticked"):
            case_file.with_user(self.tutor_user).action_accept_step()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        tutor_step = case_file.step_ids[0]
        self.assertEqual(tutor_step.done_by_id, self.tutor_user)
        self.assertTrue(tutor_step.done_date)
        self.assertEqual(case_file.current_step_id.code, 'secretariat_warning')
        self.assertFalse(self._tasks(case_file, step_task), "The Secretariat's step is due on the 15th")

        self._accept(case_file, self.secretary_user, date(2042, 1, 15))
        self.assertEqual(case_file.state, 'direction')
        self._accept(case_file, self.director_user, date(2042, 1, 22))
        self.assertEqual(case_file.state, 'secretariat')
        self.assertEqual(case_file.current_step_id.code, 'withdrawal')
        task = self._tasks(case_file, step_task)
        self.assertIn(self.secretary_user, task.user_id)
        self.assertTrue(self.post_student.withdrawal_expected, "The green light marks an expected withdrawal")

    def test_compulsory_coexistence_step_goes_to_the_tutors_branch_coordinator(self):
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2041, 3, 11))
        with self._on(date(2041, 3, 19)):
            self.Withdrawal._cron_ems_due_step_tasks()
        task = self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_step')
        self.assertEqual(task.user_id, self.coexistence_user)
        self.assertFalse(case_file.with_user(self.other_coexistence_user).can_accept_step)
        self._accept(case_file, self.coexistence_user, date(2041, 3, 19))
        self.assertEqual(case_file.current_step_id.code, 'secretariat_notice')

    def test_who_does_each_step(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        for user in (self.tutor_user, self.department_chief, self.head_of_studies, self.director_user,
                     self.admin_user):
            self.assertTrue(case_file.with_user(user).can_accept_step, user.login)
        for user in (self.other_tutor_user, self.secretary_user, self.coexistence_user):
            self.assertFalse(case_file.with_user(user).can_accept_step, user.login)
        with self.assertRaises(UserError):
            case_file.current_check_ids.with_user(self.secretary_user).write({'done': True})
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        self.assertFalse(case_file.with_user(self.tutor_user).can_accept_step)
        self.assertTrue(case_file.with_user(self.secretary_user).can_accept_step)

    def test_a_step_changes_only_its_checks_and_notes(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        step = case_file.current_step_id.with_user(self.tutor_user)
        with self._on(date(2042, 1, 8)):
            step.write({'notes': 'Mother answered'})
            with self.assertRaises(UserError):
                step.write({'due_date': date(2041, 12, 18)})
            with self.assertRaises(UserError):
                case_file.current_check_ids.with_user(self.tutor_user).write({'code': 'enotum'})
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        self.assertIn('Mother answered', case_file.message_ids[0].body)
        with self.assertRaises(UserError, msg="A step already done is closed"):
            case_file.step_ids[0].with_user(self.tutor_user).write({'notes': 'Changed afterwards'})

    # --- the responsible's block and the history ---------------------------------------------

    def test_a_step_is_ticked_in_several_goes_and_accepted_once_complete(self):
        """Post-compulsory Secretariat warning: email (sent on the 15th) and eNotum (the 16th)."""
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        enotum = case_file.current_check_ids.filtered(lambda check: check.code == 'enotum').with_user(
            self.secretary_user)
        with self._on(date(2042, 1, 15)):
            self._contact(case_file, self.secretary_user, date(2042, 1, 15)).action_confirm()
        with self._on(date(2042, 1, 16)):
            with self.assertRaisesRegex(UserError, 'eNotum'):
                case_file.with_user(self.secretary_user).action_accept_step()
            enotum.write({'done': True, 'date': date(2042, 1, 16)})
            case_file.with_user(self.secretary_user).action_accept_step()
        self.assertEqual(case_file.current_step_id.code, 'direction_approval')
        body = case_file.message_ids[0].body
        self.assertIn('01/15/2042', body)
        self.assertIn('01/16/2042', body)

    def test_nothing_is_touched_before_the_step_opens(self):
        """Before its day the block is read-only: no ticks, no notes, no button, no accepting it."""
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        tutor_view = case_file.with_user(self.tutor_user)
        phone = case_file.current_check_ids
        with self._on(date(2041, 3, 10)):
            self.assertFalse(tutor_view._ems_current_step_open())
            self.assertIn('03/11/2041', tutor_view.current_step_timing)
            with self.assertRaises(UserError):
                phone.with_user(self.tutor_user).write({'done': True, 'date': date(2041, 3, 10)})
            with self.assertRaises(UserError):
                case_file.current_step_id.with_user(self.tutor_user).write({'notes': 'Too early'})
        with self._on(date(2041, 3, 10)), self.assertRaises(UserError):
            tutor_view.with_context(call_outcome='reached').action_open_contact()
        with self._on(date(2041, 3, 10)), self.assertRaises(UserError):
            tutor_view.action_accept_step()
        self.assertFalse(case_file.step_ids[0].done_date)
        with self._on(date(2041, 3, 11)):
            self.assertTrue(tutor_view._ems_current_step_open())
            self.assertTrue(tutor_view.call_pending)

    def test_a_check_day_is_neither_future_nor_before_the_first_absence(self):
        """A check ticked by hand (the eNotum) keeps a real day."""
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        enotum = case_file.current_check_ids.filtered(lambda check: check.code == 'enotum').with_user(
            self.secretary_user)
        with self._on(date(2042, 1, 15)):
            with self.assertRaises(ValidationError):
                enotum.write({'done': True, 'date': date(2042, 1, 16)})
            with self.assertRaises(ValidationError):
                enotum.write({'done': True, 'date': date(2041, 12, 16)})
            enotum.write({'done': True, 'date': date(2042, 1, 15)})
        self.assertTrue(enotum.done)

    def test_the_responsible_gets_instructions_everybody_else_whose_turn(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        with self._on(date(2042, 1, 8)):
            tutor_view = case_file.with_user(self.tutor_user)
            self.assertIn('Contact with the family', tutor_view.current_step_instructions)
            self.assertIn('voluntary withdrawal', tutor_view.current_step_instructions)
            self.assertIn('01/15/2042', tutor_view.current_step_timing, "Before the next step's day")
            self.assertIn('Tick each action', tutor_view.current_step_notices)
            self.assertFalse(tutor_view.waiting_message)
            secretary_view = case_file.with_user(self.secretary_user)
            self.assertFalse(secretary_view.current_step_instructions)
            self.assertIn('Tutor', secretary_view.waiting_message)
            self.assertIn('01/08/2042', secretary_view.waiting_message)

    def test_history_shows_done_and_pending_steps(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        with self._on(date(2042, 1, 8)):
            case_file.current_step_id.with_user(self.tutor_user).notes = 'Father will call back'
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        history = case_file.history_html
        self.assertIn('EOW Tutor', history)
        self.assertIn('Phone call to the family (reached them): 01/08/2042', history)
        self.assertIn('Father will call back', history)
        self.assertIn('Green light from Direction', history, "Pending steps are listed too")
        self.assertIn('text-muted', history)

    # --- a late step moves the following ones -------------------------------------------------

    def test_a_late_step_keeps_the_protocols_waits(self):
        """The tutor's step (due 8 January) is accepted on Monday 20 January: the Secretariat gets its
        five school days from then, and Direction five more; the withdrawal stays on Direction's day."""
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 20))
        self.assertEqual(case_file.step_ids.mapped('planned_date'), [
            date(2042, 1, 8), date(2042, 1, 15), date(2042, 1, 22), date(2042, 1, 22)])
        self.assertEqual(case_file.step_ids.mapped('due_date'), [
            date(2042, 1, 8), date(2042, 1, 27), date(2042, 2, 3), date(2042, 2, 3)])
        with self.assertRaises(UserError, msg="The Secretariat's wait counts from the tutor's real day"):
            self._accept(case_file, self.secretary_user, date(2042, 1, 24))
        self.assertIn('protocol: 01/15/2042', case_file.history_html)

    def test_a_step_on_time_moves_nothing(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        self.assertEqual(case_file.step_ids.mapped('due_date'), case_file.step_ids.mapped('planned_date'))
        self.assertNotIn('protocol:', case_file.history_html)

    def test_compulsory_waits_are_calendar_days_between_protocol_days(self):
        """Tutor (7 days) accepted on 20 March instead of the 11th: Coexistence keeps its 8 days
        (28 March), the notice to the family its 16 more (13 April)."""
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2041, 3, 20))
        dues = {step.code: step.due_date for step in case_file.step_ids}
        self.assertEqual(dues['coexistence_contact'], date(2041, 3, 28))
        self.assertEqual(dues['secretariat_notice'], date(2041, 4, 13))
        self.assertEqual(dues['social_services'], date(2041, 4, 13), "Same protocol day: no wait between them")

    # --- who may open one and for whom --------------------------------------------------------

    def test_new_case_file_offers_only_the_users_students(self):
        Partner = self.env['res.partner']
        other_group = create_level_study_group(self, 'TEOWO', level={'education_stage': 'compulsory'})[2]
        other_group.tutor_id = self.other_tutor_user.employee_id
        other_student = self._student('EOW Other Student', other_group)
        students = (self.post_student | self.comp_student | self.none_student | other_student).ids
        for user, expected in ((self.tutor_user, self.post_student | self.comp_student),
                               (self.other_tutor_user, other_student),
                               (self.head_of_studies, self.post_student | self.comp_student),
                               (self.other_head_of_studies, self.env['res.partner']),
                               (self.admin_user, self.post_student | self.comp_student | other_student),
                               (self.settings_admin_user, self.post_student | self.comp_student | other_student)):
            domain = eval(self.Withdrawal.with_user(user).new({}).student_domain)
            found = Partner.with_user(user).search(domain + [('id', 'in', students)])
            self.assertEqual(found, expected, user.login)

    def test_student_form_requests_an_ex_officio_withdrawal(self):
        self.assertTrue(self.post_student.with_user(self.tutor_user).can_request_ex_officio_withdrawal)
        for user in (self.department_chief, self.head_of_studies, self.admin_user, self.settings_admin_user):
            self.assertTrue(self.post_student.with_user(user).can_request_ex_officio_withdrawal, user.login)
        # A Head of Studies only opens within their own chain (developer, 2026-11-04).
        for user in (self.other_tutor_user, self.other_head_of_studies, self.secretary_user, self.coexistence_user):
            self.assertFalse(self.post_student.with_user(user).can_request_ex_officio_withdrawal, user.login)
            with self.assertRaises(UserError):
                self.post_student.with_user(user).action_request_ex_officio_withdrawal()
        self.assertFalse(self.none_student.with_user(self.tutor_user).can_request_ex_officio_withdrawal,
                         "A level without circuit")
        action = self.post_student.with_user(self.tutor_user).action_request_ex_officio_withdrawal()
        self.assertEqual(action['res_model'], 'ems.ex_officio_withdrawal')
        self.assertEqual(action['context']['default_student_id'], self.post_student.id)
        self._open(self.post_student, date(2041, 12, 17))
        self.post_student.invalidate_recordset()
        self.assertFalse(self.post_student.with_user(self.tutor_user).can_request_ex_officio_withdrawal,
                         "It already has an open case file")

    # --- phase 3: emails to the family, texts to copy, the case file PDF ----------------------

    def _contact(self, case_file, user, day, outcome=None):
        with self._on(day):
            action = case_file.with_user(user).with_context(call_outcome=outcome).action_open_contact()
            return self.env[action['res_model']].with_user(user).with_context(action['context']).create({})

    def _mails(self, case_file):
        return self.env['mail.mail'].search([('model', '=', case_file._name), ('res_id', '=', case_file.id)])

    def _comp_case_on_notice(self):
        """A compulsory case file whose current step is the Secretariat's notice (due 4 April)."""
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2041, 3, 11))
        self._accept(case_file, self.coexistence_user, date(2041, 3, 19))
        return case_file

    def test_family_email_is_sent_on_request_ticks_the_check_and_stays_in_the_case_file(self):
        case_file = self._comp_case_on_notice()
        self.assertEqual(case_file.current_step_id.code, 'secretariat_notice')
        self.assertFalse(self._mails(case_file), "Nothing is sent on its own")
        wizard = self._contact(case_file, self.secretary_user, date(2041, 4, 4))
        self.assertEqual(wizard.recipient_ids, self.comp_student)
        self.assertIn('EOW Comp Student', wizard.body)
        wizard.body = '<p>An edited text for the family</p>'
        with self._on(date(2041, 4, 4)):
            wizard.action_confirm()
        mail = self._mails(case_file)
        self.assertEqual(mail.email_to, self.comp_student.email)
        self.assertIn('An edited text for the family', mail.body_html)
        check = case_file.current_check_ids
        self.assertTrue(check.done)
        self.assertEqual(check.date, date(2041, 4, 4))
        self.assertIn('An edited text for the family', case_file.message_ids[0].body)
        self.assertIn(self.comp_student.email, case_file.message_ids[0].body)

    def _post_tutor_step(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        return case_file, case_file.with_user(self.tutor_user)

    def test_reached_confirms_the_call_and_sends_the_confirmation(self):
        """Post-compulsory tutor: "I reached them" asks the day of the call and sends the
        confirmation, which ticks both the call (with how it went) and the email."""
        case_file, tutor_view = self._post_tutor_step()
        self.assertEqual(case_file.current_check_ids.mapped('code'), ['phone', 'family_email'])
        phone, email = case_file.current_check_ids
        self.assertIn('buttons above', phone.with_context(lang='en_US').label, "Nothing said yet")
        with self._on(date(2042, 1, 9)):
            self.assertEqual(tutor_view.family_email_state, 'ready')
            self.assertTrue(tutor_view.call_pending)
            with self.assertRaises(UserError, msg="Never ticked by hand"):
                phone.with_user(self.tutor_user).write({'done': True})
            with self.assertRaises(UserError, msg="How the call went comes first"):
                tutor_view.action_open_contact()
            with self.assertRaises(UserError, msg="The step needs the call and the email"):
                tutor_view.action_accept_step()
        wizard = self._contact(case_file, self.tutor_user, date(2042, 1, 9), outcome='reached')
        self.assertEqual(wizard.template_id, self.env.ref('ems.email_template_ex_officio_withdrawal_tutor_confirmation'))
        self.assertIn('withdrawn ex officio', wizard.with_context(lang='en_US').template_id.body_html)
        wizard.call_date = date(2042, 1, 8)
        with self._on(date(2042, 1, 9)):
            wizard.action_confirm()
            tutor_view.invalidate_recordset()
            self.assertEqual(tutor_view.family_email_state, 'sent')
            self.assertIn('confirmation of the phone call', tutor_view.family_email_sent)
            with self.assertRaises(UserError, msg="Only one email"):
                tutor_view.with_context(call_outcome='reached').action_open_contact()
        self.assertEqual((phone.done, phone.date, phone.call_outcome), (True, date(2042, 1, 8), 'reached'))
        phone.invalidate_recordset(['label'])
        self.assertIn('and reached them on', phone.with_context(lang='en_US').label)
        self.assertEqual((email.done, email.date), (True, date(2042, 1, 9)))
        self.assertIn('reached them', case_file.with_context(lang='en_US').history_html)
        self._accept(case_file, self.tutor_user, date(2042, 1, 9), tick=False)
        self.assertEqual(case_file.current_step_id.code, 'secretariat_warning')
        with self._on(date(2042, 1, 16)):
            self.assertFalse(case_file.with_user(self.secretary_user).call_step)
            self.assertEqual(self._contact(case_file, self.secretary_user, date(2042, 1, 16)).template_id,
                             self.env.ref('ems.email_template_ex_officio_withdrawal_family_warning'))

    def test_not_reached_sends_the_notice_or_tries_again_the_next_school_day(self):
        case_file, tutor_view = self._post_tutor_step()
        wizard = self._contact(case_file, self.tutor_user, date(2042, 1, 9), outcome='not_reached')
        self.assertEqual(wizard.template_id, self.env.ref('ems.email_template_ex_officio_withdrawal_tutor_unreachable'))
        with self._on(date(2042, 1, 9)):
            self.Withdrawal._cron_ems_due_step_tasks()
            self.assertTrue(case_file.activity_ids)
            wizard.action_try_again()  # Friday 10 January is the next school day
        self.assertFalse(self._mails(case_file), "Trying again sends nothing")
        self.assertFalse(case_file.activity_ids, "The task comes back on the new day")
        step = case_file.current_step_id
        self.assertEqual(step.due_date, date(2042, 1, 10))
        attempt = step.check_ids.filtered(lambda check: check.code == 'phone_attempt')
        self.assertEqual((attempt.done, attempt.date), (True, date(2042, 1, 9)))
        self.assertIn('01/10/2042', case_file.message_ids[0].body)
        with self._on(date(2042, 1, 9)):
            self.assertFalse(tutor_view._ems_current_step_open(), "Nothing more to do today")
        wizard = self._contact(case_file, self.tutor_user, date(2042, 1, 10), outcome='not_reached')
        with self._on(date(2042, 1, 10)):
            wizard.action_confirm()
        phone = step.check_ids.filtered(lambda check: check.code == 'phone')
        self.assertEqual((phone.date, phone.call_outcome), (date(2042, 1, 10), 'not_reached'))
        self.assertIn('and did not reach them on', phone.with_context(lang='en_US').label)
        self.assertEqual(len(self._mails(case_file)), 1)
        self._accept(case_file, self.tutor_user, date(2042, 1, 10), tick=False)
        self.assertEqual(case_file.current_step_id.code, 'secretariat_warning')

    def test_the_call_day_is_neither_future_nor_before_the_first_absence(self):
        case_file, _tutor_view = self._post_tutor_step()
        for day in (date(2042, 1, 10), date(2041, 12, 16)):
            wizard = self._contact(case_file, self.tutor_user, date(2042, 1, 9), outcome='reached')
            wizard.call_date = day
            with self._on(date(2042, 1, 9)), self.assertRaises(ValidationError):
                wizard.action_confirm()

    def test_only_the_steps_responsible_emails_the_family(self):
        case_file = self._comp_case_on_notice()
        with self._on(date(2041, 4, 4)):
            self.assertFalse(case_file.with_user(self.tutor_user).family_email_state)
            with self.assertRaises(UserError):
                case_file.with_user(self.tutor_user).action_open_contact()
        with self._on(date(2041, 4, 3)), self.assertRaises(UserError, msg="Not before the step's day"):
            case_file.with_user(self.secretary_user).action_open_contact()

    def test_social_services_and_inspection_texts_are_ready_to_copy(self):
        case_file = self._comp_case_on_notice()
        with self._on(date(2041, 4, 4)):
            self._contact(case_file, self.secretary_user, date(2041, 4, 4)).action_confirm()
            case_file.with_user(self.secretary_user).action_accept_step()
        coexistence_view = case_file.with_user(self.coexistence_user)
        with self._on(date(2041, 4, 4)):
            text = coexistence_view.copy_text
        self.assertTrue(text)
        self.assertIn('EOW Comp Student', text)
        self.assertIn(case_file.group_id.name, text)
        lines = case_file.with_env(self.env['res.company']._ems_centre_env())._ems_done_step_lines()
        self.assertEqual(len(lines), 3, "Tutor, Coexistence and the notice to the family")
        for line in lines:
            self.assertIn(f"- {line}", text.splitlines(), "One line per step done")
        self.assertFalse(case_file.with_user(self.secretary_user).copy_text, "Only for its responsible")
        self.assertFalse(coexistence_view.can_print_for_inspection)
        for user, day in ((self.coexistence_user, date(2041, 4, 4)), (self.secretary_user, date(2041, 4, 19))):
            self._accept(case_file, user, day)
        self.assertEqual(case_file.current_step_id.code, 'direction_approval')
        with self._on(date(2041, 5, 4)):
            director_view = case_file.with_user(self.director_user)
            self.assertTrue(director_view.can_print_for_inspection)
            self.assertIn('EOW Comp Student', director_view.copy_text)

    def test_the_case_file_pdf_lists_every_step(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        action = case_file.with_user(self.tutor_user).action_print_case_file()
        self.assertEqual(action['report_name'], 'ems.report_ex_officio_withdrawal')
        html = self.env['ir.actions.report']._render_qweb_html(
            'ems.action_report_ex_officio_withdrawal', case_file.ids)[0].decode()
        self.assertIn(case_file.name, html)
        self.assertIn('EOW Tutor', html)

    def test_every_phone_call_says_how_it_went_even_without_an_email(self):
        """Compulsory tutor and Coexistence: the call window has no email; not reached can be tried
        again the next school day (Monday, after a Friday call)."""
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        phone = case_file.current_check_ids
        self.assertTrue(phone.by_button)
        wizard = self._contact(case_file, self.tutor_user, date(2041, 3, 15), outcome='not_reached')
        self.assertFalse(wizard.template_id, "No email in this step")
        self.assertFalse(wizard.recipient_ids)
        with self._on(date(2041, 3, 15)):
            wizard.action_try_again()
        self.assertEqual(case_file.current_step_id.due_date, date(2041, 3, 18))
        wizard = self._contact(case_file, self.tutor_user, date(2041, 3, 18), outcome='reached')
        with self._on(date(2041, 3, 18)):
            wizard.action_confirm()
        self.assertEqual((phone.done, phone.date, phone.call_outcome), (True, date(2041, 3, 18), 'reached'))
        self.assertFalse(self._mails(case_file), "Nothing sent")
        self.assertIn('reached them', case_file.with_context(lang='en_US').message_ids[0].body)
        self._accept(case_file, self.tutor_user, date(2041, 3, 18), tick=False)
        self.assertEqual(case_file.current_step_id.code, 'coexistence_contact')
        due = case_file.current_step_id.due_date  # moved on: the tutor's was done a week late
        with self._on(due):
            self.assertTrue(case_file.with_user(self.coexistence_user).call_pending)
        self._accept(case_file, self.coexistence_user, due)
        self.assertEqual(case_file.step_ids[1].check_ids.call_outcome, 'reached')

    # --- phase 4: Direction and the Secretariat close it --------------------------------------

    def _post_case_at_withdrawal(self):
        """A post-compulsory case file whose current step is the withdrawal (due 22 January)."""
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        self._accept(case_file, self.secretary_user, date(2042, 1, 15))
        self._accept(case_file, self.director_user, date(2042, 1, 22))
        return case_file

    def _withdrawal_wizard(self, user, context):
        return self.env['ems.withdrawal_wizard'].with_user(user).with_context(context).create({})

    def test_the_secretariat_processes_the_ex_officio_withdrawal(self):
        case_file = self._post_case_at_withdrawal()
        secretary_view = case_file.with_user(self.secretary_user)
        with self._on(date(2042, 1, 22)):
            self.assertTrue(secretary_view.can_accept_step, "The Secretariat ticks its last step")
            self.assertFalse(secretary_view.can_process_withdrawal, "Not before every action is ticked")
            with self.assertRaises(UserError):
                secretary_view.action_accept_step()
            with self.assertRaises(UserError):
                secretary_view.action_open_withdrawal_wizard()
            case_file.current_check_ids.filtered(lambda check: not check.by_button).with_user(
                self.secretary_user).write({'done': True, 'date': date(2042, 1, 22)})
        wizard = self._contact(case_file, self.secretary_user, date(2042, 1, 22))
        self.assertEqual(wizard.template_id, self.env.ref('ems.email_template_ex_officio_withdrawal_done'))
        with self._on(date(2042, 1, 22)):
            wizard.action_confirm()
            secretary_view.invalidate_recordset()
            self.assertTrue(secretary_view.can_process_withdrawal)
            self.assertFalse(case_file.with_user(self.tutor_user).can_process_withdrawal)
            action = secretary_view.action_open_withdrawal_wizard()
            withdrawal_wizard = self._withdrawal_wizard(self.secretary_user, action['context'])
            self.assertEqual(withdrawal_wizard.withdrawal_mode, 'ex_officio')
            self.assertIn(case_file.name, withdrawal_wizard.exit_reason)
            withdrawal_wizard.action_apply()
        self.assertEqual((case_file.state, case_file.closed_date), ('done', date(2042, 1, 22)))
        self.assertEqual(case_file.step_ids[-1].done_by_id, self.secretary_user)
        self.assertFalse(case_file.activity_ids)
        student = self.post_student.with_context(active_test=False)
        self.assertEqual((student.exit_type, student.withdrawal_mode), ('withdrawal', 'ex_officio'))
        self.assertFalse(student.withdrawal_expected, "The withdrawal is registered: the mark has done its job")

    def test_an_ex_officio_withdrawal_only_comes_from_its_case_file(self):
        self._open(self.post_student, date(2041, 12, 17)).action_start()
        wizard = self._withdrawal_wizard(self.secretary_user, {
            'active_model': 'res.partner', 'active_ids': self.post_student.ids,
            'default_withdrawal_mode': 'ex_officio'})
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertEqual(self.post_student.contact_type, 'student')

    def test_direction_closes_the_case_file_without_a_withdrawal(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        self._accept(case_file, self.secretary_user, date(2042, 1, 15))
        with self._on(date(2042, 1, 22)):
            self.Withdrawal._cron_ems_due_step_tasks()
            self.assertFalse(case_file.with_user(self.secretary_user).can_close_without_withdrawal)
            self.assertTrue(case_file.with_user(self.director_user).can_close_without_withdrawal)
            action = case_file.with_user(self.director_user).action_open_close_wizard()
            wizard = self.env[action['res_model']].with_user(self.director_user).with_context(action['context']).create(
                {'close_reason': 'came_back', 'note': 'Back in class since Monday'})
            self.assertFalse(wizard.is_proposal)
            wizard.action_confirm()
        self.assertEqual((case_file.state, case_file.cancel_reason), ('cancelled', 'came_back'))
        self.assertEqual(case_file.cancel_note, 'Back in class since Monday')
        self.assertFalse(case_file.activity_ids)
        self.assertFalse(self.post_student.withdrawal_expected)

    def test_a_voluntary_withdrawal_cancels_the_open_case_file(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._withdrawal_wizard(self.secretary_user, {
            'active_model': 'res.partner', 'active_ids': self.post_student.ids}).action_apply()
        self.assertEqual((case_file.state, case_file.cancel_reason), ('cancelled', 'voluntary'))
        student = self.post_student.with_context(active_test=False)
        self.assertEqual((student.exit_type, student.withdrawal_mode), ('withdrawal', 'voluntary'))

    def test_an_expulsion_cancels_the_open_case_file(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self._withdrawal_wizard(self.secretary_user, {
            'active_model': 'res.partner', 'active_ids': self.post_student.ids,
            'default_exit_kind': 'expulsion'}).action_apply()
        self.assertEqual((case_file.state, case_file.cancel_reason), ('cancelled', 'expelled'))
        self.assertFalse(case_file.activity_ids)
        student = self.post_student.with_context(active_test=False)
        self.assertEqual((student.exit_type, student.withdrawal_mode), ('expulsion', False))

    # --- phase 5: detection in the roll-calls -------------------------------------------------

    def _roll_call(self, student, day, *statuses):
        """One roll-call of `student` on `day` per status in `statuses` (xmlid suffixes: 'miss',
        'attended', 'justified', 'delayed_severe'...), each at its own hour."""
        if not getattr(self, '_detection_template', None):
            subject = self.env['ems.subject'].create({
                'code': 'TEOW001', 'acronym': 'TEOW', 'name': 'EOW Subject',
                'study_ids': [(6, 0, (self.post_study | self.comp_study | self.none_study).ids)]})
            self._detection_space = self.env['ems.space'].create({
                'code': 'TEOW-A', 'name': 'EOW Space', 'space_type_id': self.env.ref('ems.space_type_classroom').id,
                'work_location_id': self.env.ref('ems.work_location_main').id})
            self._detection_template = self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, self.tutor.ids)], 'study_ids': [(6, 0, (self.post_study | self.comp_study | self.none_study).ids)],
                'subject_id': subject.id, 'group_ids': [(6, 0, (self.post_group | self.comp_group | self.none_group).ids)],
                'start_date': date(2040, 1, 1), 'end_date': date(2042, 12, 31)})
            self._detection_schedules, self._detection_sessions = {}, {}
            # A justified miss is written straight on the line, as a centre allowing it does.
            self.env.company.attendance_manual_justified = True
        for hour, status in enumerate(statuses, start=8):
            key = (day.weekday(), hour)
            if key not in self._detection_schedules:
                self._detection_schedules[key] = self.env['ems.attendance_schedule'].create({
                    'attendance_template_id': self._detection_template.id, 'weekday': str(day.weekday()),
                    'start_time': hour, 'end_time': hour + 1, 'space_id': self._detection_space.id,
                    'student_ids': [(6, 0, (self.post_student | self.comp_student | self.none_student).ids)]})
            line = {'student_id': student.id, 'status_id': self.env.ref(f'ems.attendance_status_{status}').id}
            session = self._detection_sessions.get((day, hour))
            if session:
                session.attendance_session_line_ids = [(0, 0, line)]
            else:
                self._detection_sessions[(day, hour)] = self.env['ems.attendance_session_header'].create({
                    'attendance_schedule_id': self._detection_schedules[key].id, 'date': day, 'mode': 'scheduled',
                    'session_teacher_id': self.tutor.id, 'attendance_session_line_ids': [(0, 0, line)]})

    def _detect(self, day):
        with self._on(day):
            self.Withdrawal._cron_ems_detect()
        return self.Withdrawal.search([('student_id', 'in', (self.post_student | self.comp_student).ids)])

    def _missed_week(self, student, monday, skip=()):
        for offset in range(5):
            if offset not in skip:
                self._roll_call(student, monday + timedelta(days=offset), 'miss', 'miss')

    def test_detection_opens_a_proposal_after_five_missed_school_days(self):
        self._roll_call(self.post_student, date(2041, 3, 1), 'attended')
        self._missed_week(self.post_student, date(2041, 3, 4))
        self._missed_week(self.comp_student, date(2041, 3, 4), skip=(4,))
        case_file = self._detect(date(2041, 3, 11))
        self.assertEqual(case_file.student_id, self.post_student, "Four days are not enough")
        self.assertEqual((case_file.origin, case_file.state, case_file.first_absence_date),
                         ('detected', 'proposal', date(2041, 3, 4)))
        self.assertTrue(self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_proposal'))
        self.assertIn('5', case_file.message_ids[:1].body)
        self.assertEqual(self._detect(date(2041, 3, 11)), case_file, "Running again opens nothing new")

    def test_detection_skips_days_without_roll_call_or_justified_and_never_counts_today(self):
        # Mon-Tue missed, Wed no roll-call, Thu justified (in part), Fri, next Mon and Tue missed.
        monday = date(2041, 3, 4)
        self._missed_week(self.post_student, monday, skip=(2, 3))
        self._roll_call(self.post_student, monday + timedelta(days=3), 'miss', 'justified')
        self._roll_call(self.post_student, date(2041, 3, 11), 'miss')
        self.assertFalse(self._detect(date(2041, 3, 12)), "Four missed days so far")
        self._roll_call(self.post_student, date(2041, 3, 12), 'miss')
        self.assertFalse(self._detect(date(2041, 3, 12)), "Today's roll-calls are still being taken")
        case_file = self._detect(date(2041, 3, 13))
        self.assertEqual(case_file.first_absence_date, monday)

    def test_detection_run_breaks_on_any_attendance_or_severe_delay(self):
        monday = date(2041, 3, 4)
        self._missed_week(self.post_student, monday, skip=(2,))
        self._roll_call(self.post_student, monday + timedelta(days=2), 'miss', 'attended')
        self._missed_week(self.comp_student, monday, skip=(2,))
        self._roll_call(self.comp_student, monday + timedelta(days=2), 'delayed_severe', 'miss')
        self.assertFalse(self._detect(date(2041, 3, 11)))
        self._roll_call(self.post_student, date(2041, 3, 11), 'miss')
        self._roll_call(self.post_student, date(2041, 3, 12), 'miss')
        self._roll_call(self.post_student, date(2041, 3, 13), 'miss')
        self.assertEqual(self._detect(date(2041, 3, 14)).first_absence_date, date(2041, 3, 7),
                         "The run starts again after the day they came")

    def test_detection_counts_only_the_days_after_a_closed_case_file(self):
        self._missed_week(self.post_student, date(2041, 3, 4))
        case_file = self._detect(date(2041, 3, 11))
        with self._on(date(2041, 3, 11)):
            case_file.with_user(self.tutor_user).action_dismiss("They are ill, the family will bring a note")
        self.assertEqual(case_file.closed_date, date(2041, 3, 11))
        self._missed_week(self.post_student, date(2041, 3, 11))
        self.assertEqual(self._detect(date(2041, 3, 18)), case_file, "Only four days after the dismissal")
        self._roll_call(self.post_student, date(2041, 3, 18), 'miss')
        new = self._detect(date(2041, 3, 19)) - case_file
        self.assertEqual(new.first_absence_date, date(2041, 3, 12))

    def test_detection_leaves_out_expected_withdrawals_exits_and_levels_without_circuit(self):
        for student in (self.post_student, self.comp_student, self.none_student):
            self._missed_week(student, date(2041, 3, 4))
        self.post_student.sudo().write({'withdrawal_expected': True})
        self.comp_student.sudo().write({'exit_type': 'withdrawal', 'exit_date': date(2041, 3, 8)})
        self.assertFalse(self._detect(date(2041, 3, 11)))
        self.assertFalse(self.Withdrawal.search([('student_id', '=', self.none_student.id)]))

    # --- phase 6: the roll-calls of a case file's days ---------------------------------------

    def _at_night(self, day):
        """Today is `day` and every session of it is over (22:00 UTC)."""
        stack = ExitStack()
        stack.enter_context(self._on(day))
        stack.enter_context(patch.object(fields.Datetime, 'now', return_value=datetime(day.year, day.month, day.day, 22)))
        return stack

    def _collect(self, day):
        with self._at_night(day):
            self.Withdrawal._cron_ems_detect()

    def _started(self, student=None, first_absence=date(2041, 3, 4)):
        case_file = self._open(student or self.post_student, first_absence)
        case_file.action_start()
        return case_file

    def _line_of(self, student, day):
        return self.env['ems.attendance_session_line'].search([('student_id', '=', student.id), ('date', '=', day)])

    def test_an_attendance_stops_the_case_file_until_the_tutor_checks_it(self):
        case_file = self._started()
        self._roll_call(self.post_student, date(2041, 3, 6), 'attended')
        self._collect(date(2041, 3, 7))
        self.assertTrue(case_file.attendance_pending)
        self.assertEqual(case_file.attendance_review_ids.date, date(2041, 3, 6))
        self.assertTrue(self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_attendance'))
        with self._on(date(2041, 3, 11)), self.assertRaises(UserError):
            case_file.with_user(self.tutor_user).action_accept_step()

        # A mistake: the roll-call becomes the absence it was, noted on the line.
        case_file.attendance_review_ids.with_user(self.tutor_user).action_mark_absent()
        line = self._line_of(self.post_student, date(2041, 3, 6))
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_miss'))
        self.assertIn(case_file.name, line.notes)
        self.assertFalse(case_file.attendance_pending)
        self.assertFalse(self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_attendance'))
        self._collect(date(2041, 3, 8))
        self.assertFalse(case_file.attendance_pending, "A corrected roll-call is not checked again")

        # They did come: the case file closes, and detection counts from the next day.
        self._roll_call(self.post_student, date(2041, 3, 10), 'delayed')
        self._collect(date(2041, 3, 10))
        with self._on(date(2041, 3, 11)):
            case_file.attendance_review_ids.with_user(self.tutor_user).action_came_back()
        self.assertEqual((case_file.state, case_file.cancel_reason, case_file.closed_date),
                         ('cancelled', 'came_back', date(2041, 3, 11)))
        self.assertFalse(case_file.activity_ids)

    def test_a_teacher_correcting_the_roll_call_drops_the_check(self):
        case_file = self._started()
        self._roll_call(self.post_student, date(2041, 3, 6), 'delayed_severe')
        self._collect(date(2041, 3, 6))
        self.assertTrue(case_file.attendance_pending)
        self._line_of(self.post_student, date(2041, 3, 6)).status_id = self.env.ref('ems.attendance_status_miss')
        self._collect(date(2041, 3, 7))
        self.assertFalse(case_file.review_ids)
        self.assertFalse(self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_attendance'))

    def test_a_session_still_running_is_not_checked(self):
        case_file = self._started()
        self._roll_call(self.post_student, date(2041, 3, 6), 'attended')
        with self._on(date(2041, 3, 6)), patch.object(fields.Datetime, 'now', return_value=datetime(2041, 3, 6, 7, 30)):
            self.Withdrawal._cron_ems_detect()
        self.assertFalse(case_file.review_ids, "Until its end a line is 'attended' by default")

    def test_a_case_file_opened_by_hand_checks_the_earlier_attendances_before_starting(self):
        self._roll_call(self.post_student, date(2041, 3, 5), 'attended')
        with self._at_night(date(2041, 3, 11)):
            case_file = self._open(self.post_student, date(2041, 3, 4), user=self.tutor_user)
        self.assertTrue(case_file.attendance_pending)
        with self.assertRaises(UserError):
            case_file.with_user(self.tutor_user).action_start()
        with self._at_night(date(2041, 3, 11)):
            case_file.with_user(self.tutor_user).first_absence_date = date(2041, 3, 6)
        self.assertFalse(case_file.attendance_pending, "From a later first day of absence")
        case_file.with_user(self.tutor_user).action_start()

    def test_justified_absences_are_reviewed_without_stopping_the_case_file(self):
        case_file = self._started()
        self._roll_call(self.post_student, date(2041, 3, 6), 'justified')
        self._collect(date(2041, 3, 6))
        self.assertTrue(case_file.justification_pending)
        self.assertFalse(case_file.attendance_pending)
        self.assertTrue(self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_justification'))
        case_file.with_user(self.tutor_user).action_keep_justified()
        self.assertFalse(case_file.justification_pending)
        self.assertFalse(self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_justification'))
        self.assertEqual(case_file.state, 'in_progress')

        self._roll_call(self.post_student, date(2041, 3, 7), 'justified')
        self._collect(date(2041, 3, 7))
        with self._on(date(2041, 3, 8)):
            case_file.with_user(self.tutor_user).action_cancel_justified()
        self.assertEqual((case_file.state, case_file.cancel_reason), ('cancelled', 'justified'))
        self.assertIn(format_date(self.env, date(2041, 3, 7)), case_file.cancel_note)

    def test_only_the_tutor_scope_reviews_the_roll_calls(self):
        case_file = self._started()
        self._roll_call(self.post_student, date(2041, 3, 6), 'attended')
        self._collect(date(2041, 3, 6))
        review = case_file.attendance_review_ids
        self.assertFalse(case_file.with_user(self.secretary_user).can_review)
        with self.assertRaises(UserError):
            review.with_user(self.secretary_user).action_mark_absent()
        with self.assertRaises(AccessError):
            review.with_user(self.other_tutor_user).read(['date'])
        self.assertTrue(case_file.with_user(self.head_of_studies).can_review)
        review.with_user(self.admin_user).action_mark_absent()
        self.assertEqual(review.state, 'corrected')
