# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import HttpCase, tagged

from .common import (create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email,
                     next_student_id, shift_ems_clock)


@tagged('post_install', '-at_install')
class TestExOfficioWithdrawalTour(HttpCase):
    """Issue #726: the tutor (least privileged role that opens one) creates and starts a case file
    in the browser, list and form, or requests it from the student's form; the Secretariat does its
    step (phase 2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        _level, _study, group = create_level_study_group(
            cls, 'TEOWT', level={'education_stage': 'post_compulsory'})
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_eow_tour_tutor', name='EOW Tour Tutor')
        group.tutor_id = create_role_employee(cls, cls.tutor_user)
        cls.student = cls.env['res.partner'].create({
            'name': 'EOW Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id, 'email': 'eow.tour.student@example.com',
        })
        # Another tutor's student, never offered to this tutor.
        _level, _study, other_group = create_level_study_group(
            cls, 'TEOWU', level={'education_stage': 'post_compulsory'})
        other_tutor = create_role_user(cls, 'tutor', 'test_eow_tour_other_tutor', name='EOW Tour Other Tutor')
        other_group.tutor_id = create_role_employee(cls, other_tutor)
        cls.env['res.partner'].create({
            'name': 'EOW Tour Other Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': other_group.id,
        })
        # The same fictitious Christmas break as the backend test, so the due date is known.
        utils = cls.env['ems.datetime_utils']
        cls.env['resource.calendar.leaves'].create({
            'name': 'EOW Tour Christmas break',
            'date_from': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(date(2041, 12, 23), 0.0)),
            'date_to': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(date(2042, 1, 8), 0.0)),
        })

    def test_tutor_opens_and_starts_a_case_file(self):
        self.start_tour("/odoo/action-ems.action_ex_officio_withdrawal", "ems_ex_officio_withdrawal_tutor",
                        login=self.tutor_user.login)
        case_file = self.env['ems.ex_officio_withdrawal'].search([('student_id', '=', self.student.id)])
        self.assertEqual(case_file.state, 'in_progress')
        self.assertEqual(case_file.first_absence_date, date(2041, 12, 17))
        self.assertEqual(len(case_file.step_ids), 4)

    def test_tutor_requests_it_from_the_students_form(self):
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_ex_officio_withdrawal_request",
                        login=self.tutor_user.login)
        case_file = self.env['ems.ex_officio_withdrawal'].search([('student_id', '=', self.student.id)])
        self.assertEqual(case_file.state, 'proposal')
        self.assertEqual(case_file.first_absence_date, date(2041, 12, 17))

    def test_secretariat_does_its_step(self):
        today = shift_ems_clock(self).date()
        secretary = create_role_user(self, 'secretary', 'test_eow_tour_secretary', name='EOW Step Tour Secretary')
        # Long enough ago for every step to be due, whatever breaks the calendar has.
        case_file = self.env['ems.ex_officio_withdrawal'].create({
            'student_id': self.student.id, 'first_absence_date': today - timedelta(days=200)})
        case_file.action_start()
        case_file.current_check_ids.done = True
        case_file.action_accept_step()
        # Accepted today, the tutor's step moved the Secretariat's five school days on: bring it
        # back to today, as if the tutor had done theirs on time.
        case_file.step_ids[1].due_date = today
        self.start_tour(f"/odoo/action-ems.action_ex_officio_withdrawal/{case_file.id}",
                        "ems_ex_officio_withdrawal_secretariat_step", login=secretary.login)
        self.assertEqual(case_file.state, 'direction')
        self.assertEqual(case_file.step_ids[1].done_by_id, secretary)
        self.assertTrue(all(case_file.step_ids[1].check_ids.mapped('done')))
        self.assertTrue(self.env['mail.mail'].search([('model', '=', case_file._name), ('res_id', '=', case_file.id),
                                                     ('email_to', '=', 'eow.tour.student@example.com')]))
        self.assertEqual(case_file.step_ids[1].check_ids.mapped('date'), [today, today])

    def test_tutor_emails_the_family_from_the_steps_text(self):
        today = shift_ems_clock(self).date()
        case_file = self.env['ems.ex_officio_withdrawal'].create({
            'student_id': self.student.id, 'first_absence_date': today - timedelta(days=200)})
        case_file.action_start()
        self.start_tour(f"/odoo/action-ems.action_ex_officio_withdrawal/{case_file.id}",
                        "ems_ex_officio_withdrawal_tutor_email", login=self.tutor_user.login)
        phone, email = case_file.current_check_ids
        self.assertTrue(phone.done and email.done)
        self.assertEqual(phone.call_outcome, 'not_reached')
        self.assertEqual(email.email_template_id,
                         self.env.ref('ems.email_template_ex_officio_withdrawal_tutor_unreachable'))

    def _case_at(self, code):
        """A post-compulsory case file whose current step is `code`, open today."""
        today = shift_ems_clock(self).date()
        director = create_role_user(self, 'director', 'test_eow_tour_director', name='EOW Tour Director')
        case_file = self.env['ems.ex_officio_withdrawal'].create({
            'student_id': self.student.id, 'first_absence_date': today - timedelta(days=200)})
        case_file.action_start()
        while case_file.current_step_id.code != code:
            step = case_file.current_step_id
            step.due_date = today
            step.check_ids.write({'done': True, 'date': today})
            accepting = case_file.with_user(director) if step.code == 'direction_approval' else case_file
            accepting.action_accept_step()
        case_file.current_step_id.due_date = today
        return case_file, director

    def test_secretariat_processes_the_withdrawal(self):
        case_file, _director = self._case_at('withdrawal')
        secretary = create_role_user(self, 'secretary', 'test_eow_tour_secretary2', name='EOW Tour Secretary')
        self.start_tour(f"/odoo/action-ems.action_ex_officio_withdrawal/{case_file.id}",
                        "ems_ex_officio_withdrawal_process", login=secretary.login)
        self.assertEqual(case_file.state, 'done')
        student = self.student.with_context(active_test=False)
        self.assertEqual((student.exit_type, student.withdrawal_mode), ('withdrawal', 'ex_officio'))

    def test_direction_closes_without_a_withdrawal(self):
        case_file, director = self._case_at('direction_approval')
        self.start_tour(f"/odoo/action-ems.action_ex_officio_withdrawal/{case_file.id}",
                        "ems_ex_officio_withdrawal_direction_close", login=director.login)
        self.assertEqual((case_file.state, case_file.cancel_reason), ('cancelled', 'came_back'))
