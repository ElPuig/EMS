# -*- coding: utf-8 -*-

import base64
from datetime import timedelta

from odoo import Command

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestAbsenceTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # The tour drives the UI by English label ("Done"), but this centre's admin runs the
        # backend in Spanish, so once the Direction check got its ca/es translations the option
        # stopped being found. Pin the language for the run rather than hardcoding a translated
        # label, which would break again the next time a translation is touched.
        cls.env.ref('base.user_admin').lang = 'en_US'
        # The two approvers, each logging in as themselves: 'admin' holds the Director group on
        # this centre's database, and Direction no longer gets the Head's Approve/Refuse buttons
        # on somebody else's request (hr.leave._compute_can_approve).
        # An e-mail each, because approving posts the outcome to the chatter as them.
        create_role_user(cls, 'head_of_studies', 'absence_tour_hos', email='absence_tour_hos@example.com')
        create_role_user(cls, 'director', 'absence_tour_direction',
                         email='absence_tour_direction@example.com')
        # The absent teacher themselves, for the employee's own view of their requests.
        employee_user = create_role_user(cls, 'teacher', 'absence_tour_employee',
                                         email='absence_tour_employee@example.com')
        employee = cls.env['hr.employee'].create({
            'name': 'Tour Absent Teacher', 'employee_type': 'teacher',
            'user_id': employee_user.id,
        })
        # A fresh DB (CI, unlike this box's own dev DB) has no "current course" configured at
        # all, so this must be set explicitly rather than assumed - see test_absence.py's
        # TestAbsenceRequest.setUpClass for the same fix.
        course = cls.env.company.current_course_id
        if not course:
            course = cls.env['ems.course'].create({'start': 1999, 'end': 2000})
        cls.env.company.current_course_id = course
        window = course.date_range()
        day = window[0] + timedelta(days=30)
        while day.weekday() != 0:
            day += timedelta(days=1)
        cls.absent_employee, cls.day = employee, day
        cls.env['hr.leave'].create({
            'employee_id': employee.id,
            'holiday_status_id': cls.env.ref('ems.leave_type_justified').id,
            'request_date_from': day,
            'request_date_to': day,
            'ems_full_day': True,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        })

        # A second request, with a file already on it - the justification-removal tour needs
        # something to try to delete. Deliberately of a type that requires no document (ATRI),
        # and approved below: Odoo hides the attachment on either count, and the tour is what
        # proves neither condition is left on the inherited form.
        documented = cls.env['hr.leave'].create({
            'employee_id': cls.env['hr.employee'].create({
                'name': 'Tour Documented Teacher', 'employee_type': 'teacher',
            }).id,
            'holiday_status_id': cls.env.ref('ems.leave_type_atri').id,
            'request_date_from': day,
            'request_date_to': day,
            'ems_full_day': True,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        })
        documented.supported_attachment_ids = [Command.link(cls.env['ir.attachment'].create({
            'name': 'justificant.txt',
            'datas': base64.b64encode(b'medical certificate'),
            'res_model': 'hr.leave',
            'res_id': documented.id,
        }).id)]
        documented.action_approve()

        # Validated by the Head and waiting for Direction - what Direction's own filter lists.
        # Two of them: Direction sends one back for its document and validates the other. ATRI,
        # which requires no document, so the Head's acknowledgement is already their validation.
        for offset, name in ((7, 'Tour Reviewed Teacher'), (14, 'Tour Validated Teacher')):
            cls._for_direction(cls._create_request(name, 'ems.leave_type_atri', day + timedelta(days=offset)))

        # Acknowledged by the Head, and its supporting document attached since: the Head's own
        # second step, validating it.
        submitted = cls._create_request('Tour Submitted Teacher', 'ems.leave_type_sick_leave',
                                        day + timedelta(days=21))
        submitted.action_approve()
        submitted.supported_attachment_ids = [Command.link(cls.env['ir.attachment'].create({
            'name': 'baixa.txt',
            'datas': base64.b64encode(b'sick leave certificate'),
            'res_model': 'hr.leave',
            'res_id': submitted.id,
        }).id)]

    @staticmethod
    def _for_direction(leave):
        """An ATRI request validated by the Head and confirmed by the employee: Direction's."""
        leave.action_approve()
        leave.action_ems_atri_requested()
        return leave

    @classmethod
    def _create_request(cls, employee_name, type_xmlid, day):
        return cls.env['hr.leave'].create({
            'employee_id': cls.env['hr.employee'].create({
                'name': employee_name, 'employee_type': 'teacher',
            }).id,
            'holiday_status_id': cls.env.ref(type_xmlid).id,
            'request_date_from': day,
            'request_date_to': day,
            'ems_full_day': True,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        })

    def test_absence_request_tour(self):
        self.start_tour("/odoo", "ems_absence_request", login="absence_tour_direction")

    def test_absence_direction_review_tour(self):
        self.start_tour("/odoo", "ems_absence_direction_review", login="absence_tour_direction")

    def test_absence_document_returned_tour(self):
        leave = self.env['hr.leave'].create({
            'employee_id': self.absent_employee.id,
            'holiday_status_id': self.env.ref('ems.leave_type_sick_leave').id,
            'request_date_from': self.day + timedelta(days=28),
            'request_date_to': self.day + timedelta(days=28),
            'ems_full_day': True,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        })
        leave.action_approve()
        leave.supported_attachment_ids = [Command.link(self.env['ir.attachment'].create({
            'name': 'baixa.txt',
            'datas': base64.b64encode(b'sick leave certificate'),
            'res_model': 'hr.leave',
            'res_id': leave.id,
        }).id)]
        leave._ems_return_document("Tour the stamp is missing")
        self.start_tour("/odoo", "ems_absence_document_returned", login="absence_tour_employee")

    def test_absence_head_approval_tour(self):
        self.start_tour("/odoo", "ems_absence_head_approval", login="absence_tour_hos")

    def test_absence_change_message_tour(self):
        """The Head corrected the type the employee picked: deciding on the request asks first
        for a message to the employee, and still ends back on the list (issue #615)."""
        leave = self._create_request('Tour Corrected Teacher', 'ems.leave_type_health',
                                     self.day + timedelta(days=35))
        leave.holiday_status_id = self.env.ref('ems.leave_type_atri')
        leave.ems_full_day = True
        self.start_tour("/odoo", "ems_absence_change_message", login="absence_tour_hos")
        leave.invalidate_recordset()
        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertTrue(leave.message_ids.filtered(
            lambda message: "Tour file it on the portal" in str(message.body)))

    def test_absence_undo_tour(self):
        """The Head takes back a validation from the form's Actions and from the list row
        (issue #614)."""
        leaves = self.env['hr.leave']
        for offset, name in ((42, 'Tour Undone Form Teacher'), (49, 'Tour Undone List Teacher')):
            leave = self._create_request(name, 'ems.leave_type_health', self.day + timedelta(days=offset))
            leave.action_approve()
            leaves |= leave
        action = self.env['ir.actions.act_window'].create({
            'name': 'Tour absences', 'res_model': 'hr.leave', 'view_mode': 'list,form',
            'domain': [('id', 'in', leaves.ids)],
        })
        self.start_tour(f"/odoo/action-{action.id}", "ems_absence_undo", login="absence_tour_hos")
        leaves.invalidate_recordset()
        self.assertEqual(leaves.mapped('ems_status'), ['pending', 'pending'])

    def test_absence_whole_timetable_tour(self):
        """A new request whose times cover the teacher's whole timetable for its day is ticked
        as a whole day by the form itself (issue #613)."""
        calendar = self.absent_employee.resource_calendar_id
        calendar.flexible_hours = False
        for weekday in range(5):
            self.env['resource.calendar.attendance'].create({
                'calendar_id': calendar.id, 'name': 'Tour Lesson', 'dayofweek': str(weekday),
                'hour_from': 9.0, 'hour_to': 11.0, 'day_period': 'morning',
            })
        # The first day from there the teacher is really expected in: a public holiday is not.
        day = self.day + timedelta(days=56)
        while not self.absent_employee._ems_expected_intervals(day):
            day += timedelta(days=1)
        action = self.env['ir.actions.act_window'].create({
            'name': 'Tour new absence', 'res_model': 'hr.leave', 'view_mode': 'form',
            'context': {'default_request_date_from': str(day), 'default_request_date_to': str(day)},
        })
        self.start_tour(f"/odoo/action-{action.id}", "ems_absence_whole_timetable",
                        login="absence_tour_employee")

    def _listing_action(self, leaves):
        return self.env['ir.actions.act_window'].create({
            'name': 'Tour absences', 'res_model': 'hr.leave', 'view_mode': 'list,form',
            'domain': [('id', 'in', leaves.ids)], 'context': {'hide_employee_name': 0},
        })

    def test_absence_atri_requested_tour(self):
        """The employee states their ATRI absence is requested on the portal, from the request
        itself (issue #619)."""
        leave = self.env['hr.leave'].create({
            'employee_id': self.absent_employee.id,
            'holiday_status_id': self.env.ref('ems.leave_type_atri').id,
            'request_date_from': self.day + timedelta(days=70),
            'request_date_to': self.day + timedelta(days=70),
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        leave.action_approve()
        self.assertEqual(leave.ems_status, 'pending_atri')
        self.start_tour(f"/odoo/action-{self._listing_action(leave).id}", "ems_absence_atri_requested",
                        login="absence_tour_employee")
        leave.invalidate_recordset()
        self.assertEqual(leave.ems_status, 'pending_direction')

    def test_absence_atri_missing_tour(self):
        """Direction sends an ATRI absence back as not requested in ATRI, from its row."""
        leave = self._for_direction(
            self._create_request('Tour Atri Teacher', 'ems.leave_type_atri', self.day + timedelta(days=77)))
        self.assertEqual(leave.ems_status, 'pending_direction')
        self.start_tour(f"/odoo/action-{self._listing_action(leave).id}", "ems_absence_atri_missing",
                        login="absence_tour_direction")
        leave.invalidate_recordset()
        self.assertEqual(leave.ems_atri_return_reason, "Tour it is not on the portal")

    def test_absence_atri_document_insufficient_tour(self):
        """Direction finds the documentation of an ATRI absence insufficient: it goes back to
        the employee's ATRI step, not to the supporting document in EMS."""
        leave = self._for_direction(
            self._create_request('Tour Atri Docs Teacher', 'ems.leave_type_atri', self.day + timedelta(days=84)))
        self.assertEqual(leave.ems_status, 'pending_direction')
        self.start_tour(f"/odoo/action-{self._listing_action(leave).id}", "ems_absence_atri_document_insufficient",
                        login="absence_tour_direction")
        leave.invalidate_recordset()
        self.assertEqual(leave.ems_status, 'pending_atri')
        self.assertEqual(leave.ems_atri_return_reason, "Tour the certificate is missing on the portal")

    def test_absence_employee_view_tour(self):
        self.start_tour("/odoo", "ems_absence_employee_view", login="absence_tour_employee")

    def test_absence_dashboard_tour(self):
        self.start_tour("/odoo", "ems_absence_dashboard", login="admin")

    def test_absence_submit_tour(self):
        # The fixture employee, not 'admin': the new request defaults to today, and the real
        # admin of this box may well have an absence of its own today already, which Odoo
        # refuses to overlap.
        self.start_tour("/odoo", "ems_absence_submit", login="absence_tour_employee")

    def test_absence_report_tour(self):
        self.start_tour("/odoo", "ems_absence_report", login="admin")

    def test_absence_monthly_report_tour(self):
        self.start_tour("/odoo", "ems_absence_monthly_report", login="admin")

    def test_absence_justification_removal_tour(self):
        self.start_tour("/odoo", "ems_absence_justification", login="admin")

    def test_absence_refuse_confirm_tour(self):
        self.start_tour("/odoo", "ems_absence_refuse_confirm", login="absence_tour_hos")
        self.env.invalidate_all()
        leave = self.env['hr.leave'].search([('employee_id', '=', self.absent_employee.id)])
        self.assertEqual(leave.ems_refusal_reason, "Tour the exams are that day")

    def test_absence_refusal_reason_tour(self):
        """The employee sees why their request was refused on the request itself."""
        leave = self.env['hr.leave'].create({
            'employee_id': self.absent_employee.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': self.day + timedelta(days=63),
            'request_date_to': self.day + timedelta(days=63),
            'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        leave.with_context(ems_change_message="Tour the timetable does not allow it").action_refuse()
        action = self.env['ir.actions.act_window'].create({
            'name': 'Tour refused absence', 'res_model': 'hr.leave', 'view_mode': 'list,form',
            'domain': [('id', '=', leave.id)],
        })
        self.start_tour(f"/odoo/action-{action.id}", "ems_absence_refusal_reason",
                        login="absence_tour_employee")
