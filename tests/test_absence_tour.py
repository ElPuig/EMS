# -*- coding: utf-8 -*-

import base64
from datetime import timedelta

from odoo import Command

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import mock_outgoing_email


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
        employee = cls.env['hr.employee'].create({
            'name': 'Tour Absent Teacher', 'employee_type': 'teacher',
        })
        window = cls.env.company.current_course_id.date_range()
        day = window[0] + timedelta(days=30)
        while day.weekday() != 0:
            day += timedelta(days=1)
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
        # something to try to delete. Deliberately of a type that requires no document, and
        # approved below: Odoo hides the attachment on either count, and the tour is what proves
        # neither condition is left on the inherited form.
        documented = cls.env['hr.leave'].create({
            'employee_id': cls.env['hr.employee'].create({
                'name': 'Tour Documented Teacher', 'employee_type': 'teacher',
            }).id,
            'holiday_status_id': cls.env.ref('ems.leave_type_justified').id,
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

    def test_absence_request_tour(self):
        self.start_tour("/odoo", "ems_absence_request", login="admin")

    def test_absence_dashboard_tour(self):
        self.start_tour("/odoo", "ems_absence_dashboard", login="admin")

    def test_absence_submit_tour(self):
        self.start_tour("/odoo", "ems_absence_submit", login="admin")

    def test_absence_report_tour(self):
        self.start_tour("/odoo", "ems_absence_report", login="admin")

    def test_absence_monthly_report_tour(self):
        self.start_tour("/odoo", "ems_absence_monthly_report", login="admin")

    def test_absence_justification_removal_tour(self):
        self.start_tour("/odoo", "ems_absence_justification", login="admin")

    def test_absence_refuse_confirm_tour(self):
        self.start_tour("/odoo", "ems_absence_refuse_confirm", login="admin")
