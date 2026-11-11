# -*- coding: utf-8 -*-
"""Regenerates the screenshot of the staff strike report in the Director's absences manual (issue
#813). Tagged '-standard' on purpose - see the NOTE in test_docs_screenshots.py. Run it by hand:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsStaffStrike' --stop-after-init -c /etc/odoo/odoo.conf"

Writes the PNG to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR); copy it into
docs/assets/head_of_studies/ by hand afterwards.
"""
from datetime import timedelta

from odoo.tests.common import HttpCase, tagged

from .common import (
    DocsScreenshotMixin, create_role_user, make_working_day, mock_outgoing_email, shift_ems_clock)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsStaffStrike(HttpCase, DocsScreenshotMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        day = shift_ems_clock(cls, hour=10.0, weekdays=(1, 2, 3, 4)).date() - timedelta(days=1)
        make_working_day(cls, day)
        # Only the made-up staff below may count: this database's own staff keep their schedules
        # out of the report for the rolled-back length of the test.
        cls.env.cr.execute("UPDATE resource_calendar SET active = FALSE WHERE employee_id IS NOT NULL")
        cls.env.invalidate_all()
        cls.director = create_role_user(cls, 'director', 'doc_shot_director', lang='ca_ES', name='Directora Exemple')
        civil_servant, interim = cls.env['hr.contract.type'].create([
            {'name': 'Funcionari/a', 'sequence': -2}, {'name': 'Interí/na', 'sequence': -1}])
        morning = ((8.0, 9.0), (9.0, 10.0), (10.0, 11.0), (11.0, 12.0))
        staff = {}
        for name, employee_type, contract_type, periods in (
                ('Anna Exemple', 'teacher', civil_servant, morning),
                ('Biel Exemple', 'teacher', civil_servant, morning),
                ('Carla Exemple', 'teacher', civil_servant, morning[1:]),
                ('Dani Exemple', 'teacher', civil_servant, morning),
                ('Elna Exemple', 'teacher', interim, morning[1:]),
                ('Ferran Exemple', 'teacher', interim, morning),
                ('Gina Exemple', 'asp', civil_servant, ((8.0, 12.0),))):
            employee = cls.env['hr.employee'].create({
                'name': name, 'employee_type': employee_type, 'contract_type_id': contract_type.id})
            employee.resource_calendar_id = cls.env['resource.calendar'].create({
                'name': name, 'employee_id': employee.id,
                'attendance_ids': [(5, 0, 0)] + [
                    (0, 0, {'name': f'{name} {start}', 'dayofweek': str(day.weekday()),
                            'hour_from': start, 'hour_to': stop}) for start, stop in periods],
            })
            staff[name] = employee
        Pending = cls.env['ems.absence_pending']
        for name, hour in (('Biel Exemple', 7.9), ('Ferran Exemple', 8.5), ('Gina Exemple', 7.8)):
            cls.env['hr.attendance'].create({
                'employee_id': staff[name].id, 'check_in': Pending._utc_bounds(day, 0.0, hour)[1],
                'check_out': Pending._utc_bounds(day, 0.0, 14.0)[1]})
        leave = cls.env['hr.leave'].create({
            'employee_id': staff['Dani Exemple'].id, 'holiday_status_id': cls.env.ref('ems.leave_type_justified').id,
            'request_date_from': day, 'request_date_to': day, 'ems_full_day': True,
            'ems_submitted': True, 'ems_responsible_declaration': True})
        leave.sudo().state = 'validate'
        report = cls.env['ems.staff_strike_report'].with_user(cls.director).create({'date': day})
        opened = report.action_open_report()
        cls.action = cls.env['ir.actions.act_window'].create({
            'name': opened['name'], 'res_model': opened['res_model'], 'view_mode': 'pivot,list',
            'domain': opened['domain'],
        })

    def test_capture_staff_strike_report(self):
        self._capture(
            '/odoo/action-%d' % self.action.id, '.o_pivot table', 'hos-staff-strike-report.png',
            login='doc_shot_director', wait_for='.o_pivot td.o_pivot_cell_value', viewport_width=1700)
