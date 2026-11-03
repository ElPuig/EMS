# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestExOfficioWithdrawalTour(HttpCase):
    """Issue #726, phase 1: the tutor (least privileged role that opens one) creates and starts a
    case file in the browser, list and form."""

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
