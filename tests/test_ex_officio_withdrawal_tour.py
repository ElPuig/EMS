# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, next_student_id, shift_ems_clock


@tagged('post_install', '-at_install')
class TestExOfficioWithdrawalTour(HttpCase):
    """Issue #726: the tutor (least privileged role that opens one) creates and starts a case file
    in the browser, list and form, or requests it from the student's form; the Secretariat does its
    step (phase 2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _level, _study, group = create_level_study_group(
            cls, 'TEOWT', level={'withdrawal_circuit': 'post_compulsory'})
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_eow_tour_tutor', name='EOW Tour Tutor')
        group.tutor_id = create_role_employee(cls, cls.tutor_user)
        cls.student = cls.env['res.partner'].create({
            'name': 'EOW Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id,
        })
        # Another tutor's student, never offered to this tutor.
        _level, _study, other_group = create_level_study_group(
            cls, 'TEOWU', level={'withdrawal_circuit': 'post_compulsory'})
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
        self.start_tour(f"/odoo/action-ems.action_ex_officio_withdrawal/{case_file.id}",
                        "ems_ex_officio_withdrawal_secretariat_step", login=secretary.login)
        self.assertEqual(case_file.state, 'direction')
        self.assertEqual(case_file.step_ids[1].done_by_id, secretary)
        self.assertTrue(all(case_file.step_ids[1].check_ids.mapped('done')))
        self.assertEqual(case_file.step_ids[1].check_ids.mapped('date'), [today, today])
