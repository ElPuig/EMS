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
            cls._create_request(name, 'ems.leave_type_atri', day + timedelta(days=offset)).action_approve()

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
