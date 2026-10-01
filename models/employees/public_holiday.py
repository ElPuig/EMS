# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.osv.expression import OR


class EmsPublicHoliday(models.Model):
    """Public holidays (resource.calendar.leaves with no resource) and the "absence" technical
    attendances they make obsolete. See docs/en/developers/employees/absence.md, "Public
    holidays"."""
    _inherit = 'resource.calendar.leaves'

    @api.model_create_multi
    def create(self, vals_list):
        """A public holiday always applies to every schedule: every teacher has a personal one,
        so tying it to a single schedule (the default the "Public Time Off" button of a
        schedule's form puts in the context) leaves everybody else out."""
        for vals in vals_list:
            if not vals.get('resource_id'):
                vals['calendar_id'] = False
        leaves = super().create(vals_list)
        leaves._unlink_technical_attendances_without_expected_hours()
        return leaves

    def write(self, vals):
        result = super().write(vals)
        tied_holidays = self.filtered(lambda leave: not leave.resource_id and leave.calendar_id)
        if tied_holidays:
            super(EmsPublicHoliday, tied_holidays).write({'calendar_id': False})
        self._unlink_technical_attendances_without_expected_hours()
        return result

    def _unlink_technical_attendances_without_expected_hours(self):
        """Delete the technical attendances hr.attendance._cron_absence_detection() created on
        the days these leaves cover, when those days are now left with no expected hours at all.
        Odoo recomputes the overtime of those days itself, but leaves the (red) attendance
        behind; it would have deleted it on creation had the leave already existed. A real
        attendance, or a day with hours still expected (a partial leave), is kept."""
        employee_dates = self._get_employee_dates()
        if not employee_dates:
            return
        attendance_model = self.env['hr.attendance'].sudo()
        technical_attendances = attendance_model.search([
            ('in_mode', '=', 'technical'),
        ] + OR([
            [('employee_id', '=', employee.id), ('check_in', 'in', [day_start for day_start, _day in dates])]
            for employee, dates in employee_dates.items()
        ]))
        obsolete = attendance_model
        for attendance in technical_attendances:
            employee = attendance.employee_id
            day = attendance_model._get_day_start_and_day(employee, attendance.check_in)[1]
            if not employee._get_expected_attendances(*employee._ems_local_day_bounds(day)):
                obsolete |= attendance
        obsolete.unlink()
