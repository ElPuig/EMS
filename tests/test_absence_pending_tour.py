# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestAbsencePendingTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'absence_pending_tour_teacher')
        cls.teacher = teacher = create_role_employee(cls, cls.teacher_user, name='Tour Pending Teacher')
        # The least-privileged role with access: the teacher's own Department Chief (issue #604),
        # logging in as themselves (see rule_absence_pending_hierarchy).
        create_head_of_studies_branch(cls, 'APT', teacher)

    def test_absence_pending_tour(self):
        self.start_tour("/odoo", "ems_absence_pending", login=self.department_chief.login)

    def test_teacher_requests_their_detected_absence_tour(self):
        """Issue #696: the least-privileged reader, the teacher themselves, from the reminder's
        link (the record's own URL). Issue #698: they answer on it from the chatter."""
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        absence = Pending.create({
            'employee_id': self.teacher.id, 'origin': 'check_in', 'note': 'Not for the teacher',
            'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 11.0)[1],
        })
        # Issue #707: only once their Head of Studies asks them to justify it.
        absence.with_user(self.head_of_studies).action_request_justification()
        # Issue #698: they answer on it, as any real user, with an email.
        self.teacher_user.email = 'pending.tour.teacher@example.com'
        self.start_tour(f"/odoo/ems.absence_pending/{absence.id}", "ems_absence_pending_teacher",
                        login=self.teacher_user.login)
        # Issue #735: no attendance that day, none picked; the times typed with a comma and
        # without a separator.
        self.assertFalse(absence.correction_ids.attendance_id)
        self.assertEqual(absence.correction_ids.mapped(lambda correction: (
            correction.requested_check_in, round(correction.requested_check_out, 4))), [(9.25, round(11 + 4 / 60, 4))])

    def test_teacher_finds_their_absences_to_regularize_tour(self):
        """Issue #735: from the Absences menu, the teacher's own entries still asked by default."""
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        asked, resolved = Pending.create([{
            'employee_id': self.teacher.id, 'origin': 'check_in',
            'date_from': Pending._utc_bounds(day, 0.0, start)[1], 'date_to': Pending._utc_bounds(day, 0.0, stop)[1],
        } for start, stop in ((9.0, 10.0), (11.0, 12.0))])
        (asked | resolved).with_user(self.head_of_studies).action_request_justification()
        resolved.sudo().state = 'corrected'
        self.start_tour("/odoo/action-hr_holidays.hr_leave_action_my", "ems_absence_pending_teacher_menu",
                        login=self.teacher_user.login)

    def test_teacher_sees_a_corrected_absence_tour(self):
        """Issue #735: a final state other than Requested is shown alone."""
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        absence = Pending.create({
            'employee_id': self.teacher.id, 'origin': 'check_in',
            'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 10.0)[1],
        })
        absence.with_user(self.head_of_studies).action_request_justification()
        absence.sudo().state = 'corrected'
        self.start_tour(f"/odoo/ems.absence_pending/{absence.id}", "ems_absence_pending_corrected",
                        login=self.teacher_user.login)

    def test_refused_request_reopens_the_detected_absence_tour(self):
        """Issue #735: the absence prepared for the teacher, sent by them, then refused by their
        Head of Studies: the detected absence is back to the review."""
        # Refusing posts the reason to the teacher as them: like any real user, they have an email.
        self.head_of_studies.email = 'refuse.hos@example.com'
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        absence = Pending.create({
            'employee_id': self.teacher.id, 'origin': 'check_in',
            'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 11.0)[1],
        })
        absence.with_user(self.head_of_studies)._ems_prepare_absences(self.env.ref('ems.leave_type_justified'))
        context = absence.with_user(self.teacher_user).action_request_absence()['context']
        leave = self.env['hr.leave'].with_user(self.teacher_user).create({
            **{key.removeprefix('default_'): value for key, value in context.items()},
            'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        self.assertEqual(absence.state, 'linked')

        self.start_tour(f"/odoo/hr.leave/{leave.id}", "ems_absence_pending_refuse_request",
                        login=self.head_of_studies.login)
        self.assertEqual(absence.state, 'pending')
        self.start_tour("/odoo/action-ems.action_absence_pending", "ems_absence_pending_reopened",
                        login=self.head_of_studies.login)

    def test_head_of_studies_reviews_detected_absences_tour(self):
        """Issue #707: the reviewer, the teacher's Head of Studies (the least-privileged role that
        reviews). Five teachers of their branch, each with a detected absence of yesterday."""
        # Approving the absence it creates posts as them: like any real user, they have an email.
        self.head_of_studies.email = 'review.hos@example.com'
        Pending = self.env['ems.absence_pending']
        day = Pending.get_local_today() - timedelta(days=1)
        for letter in 'ABCDE':
            teacher = self.env['hr.employee'].create({
                'name': f'Review Teacher {letter}', 'employee_type': 'teacher',
                'parent_id': self.teacher.parent_id.id})
            Pending.create({
                'employee_id': teacher.id, 'origin': 'check_in',
                'date_from': Pending._utc_bounds(day, 0.0, 9.0)[1], 'date_to': Pending._utc_bounds(day, 0.0, 11.0)[1],
            })
        self.start_tour("/odoo", "ems_absence_pending_review", login=self.head_of_studies.login)
