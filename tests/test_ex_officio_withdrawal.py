# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common import (create_head_of_studies_branch, create_level_study_group, create_role_employee,
                     create_role_user, next_student_id)

POST_COMPULSORY_CODES = ['tutor_contact', 'secretariat_warning', 'direction_approval', 'withdrawal']
COMPULSORY_CODES = ['tutor_contact', 'coexistence_contact', 'secretariat_notice', 'social_services',
                    'secretariat_warning', 'direction_approval', 'withdrawal']


@tagged('post_install', '-at_install')
class TestExOfficioWithdrawal(TransactionCase):
    """Issue #726, phase 1: the case file opened by hand, its steps and deadlines, and who sees
    and decides it."""

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
