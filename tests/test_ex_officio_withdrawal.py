# -*- coding: utf-8 -*-

from datetime import date, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common import (create_head_of_studies_branch, create_level_study_group, create_role_employee,
                     create_role_user, next_student_id)

POST_COMPULSORY_CODES = ['tutor_contact', 'secretariat_warning', 'direction_approval', 'withdrawal']
COMPULSORY_CODES = ['tutor_contact', 'coexistence_contact', 'secretariat_notice', 'social_services',
                    'secretariat_warning', 'direction_approval', 'withdrawal']


@tagged('post_install', '-at_install')
class TestExOfficioWithdrawal(TransactionCase):
    """Issue #726: the case file opened by hand, its steps and deadlines, who sees and decides it
    (phase 1), and the steps done one after another, each its responsible's task (phase 2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Withdrawal = cls.env['ems.ex_officio_withdrawal']
        cls.post_level, cls.post_study, cls.post_group = create_level_study_group(
            cls, 'TEOWP', level={'withdrawal_circuit': 'post_compulsory'})
        cls.comp_level, cls.comp_study, cls.comp_group = create_level_study_group(
            cls, 'TEOWC', level={'withdrawal_circuit': 'compulsory'})
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
            'main_group_id': group.id,
        })

    def _on(self, day):
        """Run as if today were `day` in the company's calendar."""
        return patch.object(type(self.env['ems.datetime_utils']), 'get_local_today', return_value=day)

    def _tasks(self, case_file, xmlid):
        return case_file.activity_ids.filtered(lambda activity: activity.activity_type_id == self.env.ref(xmlid))

    def _accept(self, case_file, user, day, **checks):
        """`user` ticks `checks` on the current step and accepts it on `day`, the hourly job
        having run first."""
        with self._on(day):
            self.Withdrawal._cron_ems_due_step_tasks()
            if checks:
                case_file.current_step_id.with_user(user).write(checks)
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
        steps = {step.code: step for step in case_file.step_ids}
        self.assertTrue(steps['tutor_contact'].needs_phone)
        self.assertFalse(steps['tutor_contact'].needs_enotum)
        self.assertTrue(steps['secretariat_warning'].needs_enotum)
        self.assertTrue(steps['social_services'].needs_external_email)
        self.assertTrue(steps['withdrawal'].needs_esfera)
        self.assertFalse(steps['withdrawal'].needs_saga)

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

    def test_level_without_circuit_is_refused(self):
        with self.assertRaises(UserError):
            self._open(self.none_student, date(2041, 3, 4))

    def test_one_open_case_file_per_student(self):
        first = self._open(self.post_student, date(2041, 12, 17))
        with self.assertRaises(ValidationError):
            self._open(self.post_student, date(2041, 12, 18))
        first.action_dismiss('A test reason')
        self._open(self.post_student, date(2041, 12, 18))

    def test_start_moves_to_in_progress_once(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        self.assertEqual(case_file.state, 'in_progress')
        self.assertEqual(case_file.current_step_id.code, 'tutor_contact')
        with self.assertRaises(UserError):
            case_file.action_start()

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
        self._open(self.post_student, date(2041, 12, 17), user=self.department_chief)

    def test_who_decides_the_proposal(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        for user in (self.tutor_user, self.department_chief, self.head_of_studies):
            self.assertTrue(case_file.with_user(user).can_decide_proposal, user.login)
        for user in (self.coexistence_user, self.secretary_user):
            self.assertFalse(case_file.with_user(user).can_decide_proposal, user.login)
            with self.assertRaises(UserError):
                case_file.with_user(user).action_start()
        case_file.with_user(self.tutor_user).action_start()
        self.assertEqual(case_file.state, 'in_progress')

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
        self._accept(case_file, self.tutor_user, date(2042, 1, 8), phone_done=True)
        tutor_step = case_file.step_ids[0]
        self.assertEqual(tutor_step.done_by_id, self.tutor_user)
        self.assertTrue(tutor_step.done_date)
        self.assertEqual(case_file.current_step_id.code, 'secretariat_warning')
        self.assertFalse(self._tasks(case_file, step_task), "The Secretariat's step is due on the 15th")

        self._accept(case_file, self.secretary_user, date(2042, 1, 15), enotum_done=True)
        self.assertEqual(case_file.state, 'direction')
        self._accept(case_file, self.director_user, date(2042, 1, 22))
        self.assertEqual(case_file.state, 'secretariat')
        self.assertEqual(case_file.current_step_id.code, 'withdrawal')
        task = self._tasks(case_file, step_task)
        self.assertIn(self.secretary_user, task.user_id)
        self.assertFalse(case_file.with_user(self.secretary_user).can_accept_step,
                         "The withdrawal itself is made from the student's withdrawal wizard")

    def test_compulsory_coexistence_step_goes_to_the_tutors_branch_coordinator(self):
        case_file = self._open(self.comp_student, date(2041, 3, 4))
        case_file.action_start()
        self._accept(case_file, self.tutor_user, date(2041, 3, 11), phone_done=True)
        with self._on(date(2041, 3, 19)):
            self.Withdrawal._cron_ems_due_step_tasks()
        task = self._tasks(case_file, 'ems.mail_activity_ex_officio_withdrawal_step')
        self.assertEqual(task.user_id, self.coexistence_user)
        self.assertFalse(case_file.with_user(self.other_coexistence_user).can_accept_step)
        self._accept(case_file, self.coexistence_user, date(2041, 3, 19), phone_done=True)
        self.assertEqual(case_file.current_step_id.code, 'secretariat_notice')

    def test_no_step_is_done_before_its_day(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        with self.assertRaises(UserError):
            self._accept(case_file, self.tutor_user, date(2042, 1, 7), phone_done=True)
        self.assertFalse(case_file.step_ids[0].done_date)

    def test_who_does_each_step(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        for user in (self.tutor_user, self.department_chief, self.head_of_studies, self.director_user,
                     self.admin_user):
            self.assertTrue(case_file.with_user(user).can_accept_step, user.login)
        for user in (self.other_tutor_user, self.secretary_user, self.coexistence_user):
            self.assertFalse(case_file.with_user(user).can_accept_step, user.login)
        with self.assertRaises(UserError):
            case_file.current_step_id.with_user(self.secretary_user).write({'phone_done': True})
        self._accept(case_file, self.tutor_user, date(2042, 1, 8), phone_done=True)
        self.assertFalse(case_file.with_user(self.tutor_user).can_accept_step)
        self.assertTrue(case_file.with_user(self.secretary_user).can_accept_step)

    def test_a_step_changes_only_its_checks_and_notes(self):
        case_file = self._open(self.post_student, date(2041, 12, 17))
        case_file.action_start()
        step = case_file.current_step_id.with_user(self.tutor_user)
        step.write({'phone_done': True, 'notes': 'Mother answered'})
        with self.assertRaises(UserError):
            step.write({'due_date': date(2041, 12, 18)})
        self._accept(case_file, self.tutor_user, date(2042, 1, 8))
        self.assertIn('Mother answered', case_file.message_ids[0].body)
        with self.assertRaises(UserError, msg="A step already done is closed"):
            case_file.step_ids[0].with_user(self.tutor_user).write({'notes': 'Changed afterwards'})
