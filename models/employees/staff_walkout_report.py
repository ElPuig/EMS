# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..attendance.absence_coverage import overlaps
from ..shared.schedule_report_mixin import HOUR_EPSILON
from .employee import employee_types


class EmsStaffWalkoutReport(models.TransientModel):
    """Issue #813: the staff on walkout so far on a day, per staff type and contract type, which
    the Director reports to the Departament about every hour. Nobody declares the walkout in EMS:
    whoever has not checked in at all that day counts from the first period of their own schedule
    that has started and that no absence request covers (sick leave, a permission, training...),
    and keeps counting for the rest of the day, so each figure is cumulative. Whoever checked in or
    is on a justified absence is expected to work but not on walkout. Checking in at any
    time takes them out: they may have arrived late because of the walkout, which is no walkout.

    Shown as a pivot of transient lines (ems.staff_walkout_report.line) rather than a custom table: its
    columns (one per contract type) depend on the data, and the pivot already gives the names
    behind each figure (clicking it) and the spreadsheet download the Director relies on."""
    _name = 'ems.staff_walkout_report'
    _description = "Staff walkout report"

    date = fields.Date(string="Date", required=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    line_ids = fields.One2many(string="Lines", comodel_name='ems.staff_walkout_report.line', inverse_name='report_id')

    def action_open_report(self):
        self.ensure_one()
        self.line_ids = [fields.Command.create(values) for values in self._get_line_values()]
        return {
            'type': 'ir.actions.act_window',
            'name': self._get_title(),
            'res_model': 'ems.staff_walkout_report.line',
            'view_mode': 'pivot,list',
            'views': [(False, 'pivot'), (False, 'list')],
            'domain': [('report_id', '=', self.id)],
            'target': 'current',
        }

    def _get_title(self):
        """The pivot's title. Today's carries the time the figures were read at: the lines are
        computed once, on Show, so reloading the page shows them again, and the time is what tells
        the Director they are no longer current."""
        local_now = self.env['ems.datetime_utils'].get_local_datetime()
        day = self.date.strftime('%d/%m/%Y')
        if self.date == local_now.date():
            return _("Staff walkouts on %(day)s at %(time)s", day=day, time=local_now.strftime('%H:%M'))
        return _("Staff walkouts on %s", day)

    def _get_line_values(self):
        """One line per period of the day already started and per member of staff expected to
        work by then (a period of their schedule had started), telling whether they were on walkout
        at that point."""
        utils = self.env['ems.datetime_utils']
        local_now = utils.get_local_datetime()
        if self.date > local_now.date():
            raise UserError(_("Choose today or a day already over."))
        holiday = self.env['resource.calendar.leaves']._ems_public_holiday_on(self.date)
        if holiday:
            raise UserError(_("%s is a public holiday.", holiday.name))
        now = utils.time_to_float(local_now) if self.date == local_now.date() else 24.0
        staff = self.env['hr.employee'].sudo().search([
            ('employee_type', 'in', ('teacher', 'asp')), ('schedule_import_code', '=', False)])
        periods = self.env['ems.absence_pending']._ems_scheduled_periods(self.date, staff)
        staff = staff.filtered(lambda employee: employee.id in periods)
        expected, on_walkout = self._get_start_hours(staff, periods, now)
        if not expected:
            raise UserError(_("Nobody was expected to work on this day yet."))
        bounds = sorted({hour for employee_periods in periods.values() for period in employee_periods for hour in period})
        format_time = self.env['ems.schedule_report_mixin']._format_report_time
        return [{
            'period': f"{format_time(hour_from)}-{format_time(hour_to)}",
            'employee_id': employee.id,
            'employee_type': employee.employee_type,
            'contract_type_id': employee.contract_type_id.id,
            'on_walkout': int(employee.id in on_walkout and on_walkout[employee.id] <= hour_from + HOUR_EPSILON),
        } for hour_from, hour_to in zip(bounds, bounds[1:]) if hour_from <= now + HOUR_EPSILON
            for employee in staff if employee.id in expected and expected[employee.id] <= hour_from + HOUR_EPSILON]

    def _get_start_hours(self, staff, periods, now):
        """Two `{employee.id: hour}`: from when each of `staff` was expected to work (the start of
        their first period already started at `now`) and, for those who have not checked in at all,
        from when they count as on walkout (the start of their first such period that no absence
        request covers). Whoever is on a justified absence is expected but not on walkout."""
        arrivals = self.env['hr.attendance']._ems_first_check_in_hours(self.date, staff)
        leaves = self.env['ems.course']._get_guard_duty_leave_intervals(self.date, staff)
        expected, on_walkout = {}, {}
        for employee in staff:
            started = [(start, stop) for start, stop in periods[employee.id] if start <= now + HOUR_EPSILON]
            if not started:
                continue
            expected[employee.id] = min(start for start, _stop in started)
            missed = [start for start, stop in started
                      if not any(overlaps(start, stop, *leave[:2]) for leave in leaves.get(employee.id, ()))]
            if missed and employee.id not in arrivals:
                on_walkout[employee.id] = min(missed)
        return expected, on_walkout


class EmsStaffWalkoutReportLine(models.TransientModel):
    """A member of staff expected to work by a period of the walkout report's day (see
    ems.staff_walkout_report), and whether they were on walkout by then."""
    _name = 'ems.staff_walkout_report.line'
    _description = "Staff walkout report line"
    _order = 'period, employee_id'

    report_id = fields.Many2one(string="Report", comodel_name='ems.staff_walkout_report', required=True, ondelete='cascade')
    period = fields.Char(string="Period", required=True)
    employee_id = fields.Many2one(string="Employee", comodel_name='hr.employee', required=True, ondelete='cascade')
    employee_type = fields.Selection(string="Staff", selection=employee_types)
    contract_type_id = fields.Many2one(string="Contract Type", comodel_name='hr.contract.type')
    on_walkout = fields.Integer(string="On walkout", aggregator='sum')
    not_on_walkout = fields.Integer(string="Not on walkout", compute='_compute_walkout_figures', store=True, aggregator='sum')
    expected = fields.Integer(string="Expected to work", default=1, aggregator='sum')
    # 100 or 0 per line, averaged: in each cell, the share of those expected to work who are on walkout.
    walkout_percentage = fields.Float(string="% on walkout", compute='_compute_walkout_figures', store=True,
                                     aggregator='avg', digits=(16, 1))

    @api.depends('on_walkout')
    def _compute_walkout_figures(self):
        for line in self:
            line.not_on_walkout = 1 - line.on_walkout
            line.walkout_percentage = 100.0 * line.on_walkout
