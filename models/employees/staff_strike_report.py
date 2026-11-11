# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..shared.schedule_report_mixin import HOUR_EPSILON
from .employee import employee_types


def _overlaps(start, stop, intervals):
    """Whether (start, stop) shares any time with one of `intervals` ((start, stop, ...) tuples)."""
    return any(other[0] < stop and other[1] > start for other in intervals)


class EmsStaffStrikeReport(models.TransientModel):
    """Issue #813: the staff on strike so far on a day, per staff type and contract type, which
    the Director reports to the Departament about every hour. Nobody declares the strike in EMS:
    whoever has not checked in at all that day counts from the first period of their own schedule
    that has started and that no absence request covers (sick leave, a permission, training...),
    and keeps counting for the rest of the day, so each figure is cumulative. Checking in at any
    time takes them out: they may have arrived late because of the strike, which is no strike.

    Shown as a pivot of transient lines (ems.staff_strike_report.line) rather than a custom table: its
    columns (one per contract type) depend on the data, and the pivot already gives the names
    behind each figure (clicking it) and the spreadsheet download the Director relies on."""
    _name = 'ems.staff_strike_report'
    _description = "Staff strike report"

    date = fields.Date(string="Date", required=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    line_ids = fields.One2many(string="Lines", comodel_name='ems.staff_strike_report.line', inverse_name='report_id')

    def action_open_report(self):
        self.ensure_one()
        self.line_ids = [fields.Command.create(values) for values in self._get_line_values()]
        return {
            'type': 'ir.actions.act_window',
            'name': self._get_title(),
            'res_model': 'ems.staff_strike_report.line',
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
            return _("Staff strikes on %(day)s at %(time)s", day=day, time=local_now.strftime('%H:%M'))
        return _("Staff strikes on %s", day)

    def _get_line_values(self):
        """One line per period of the day already started and per member of staff expected to
        work by then (a period of theirs had started and no absence request covered it), telling
        whether they were on strike at that point."""
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
        expected, on_strike = self._get_start_hours(staff, periods, now)
        if not expected:
            raise UserError(_("Nobody was expected to work on this day yet."))
        bounds = sorted({hour for employee_periods in periods.values() for period in employee_periods for hour in period})
        format_time = self.env['ems.schedule_report_mixin']._format_report_time
        return [{
            'period': f"{format_time(hour_from)}-{format_time(hour_to)}",
            'employee_id': employee.id,
            'employee_type': employee.employee_type,
            'contract_type_id': employee.contract_type_id.id,
            'on_strike': int(employee.id in on_strike and on_strike[employee.id] <= hour_from + HOUR_EPSILON),
        } for hour_from, hour_to in zip(bounds, bounds[1:]) if hour_from <= now + HOUR_EPSILON
            for employee in staff if employee.id in expected and expected[employee.id] <= hour_from + HOUR_EPSILON]

    def _get_start_hours(self, staff, periods, now):
        """Two `{employee.id: hour}`: from when each of `staff` was expected to work (the start of
        their first period already started at `now` that no absence request covers) and, for those
        who have not checked in at all, from when they count as on strike (the same hour)."""
        arrivals = self.env['hr.attendance']._ems_first_check_in_hours(self.date, staff)
        leaves = self.env['ems.course']._get_guard_duty_leave_intervals(self.date, staff)
        expected = {}
        for employee in staff:
            starts = [start for start, stop in periods[employee.id]
                      if start <= now + HOUR_EPSILON and not _overlaps(start, stop, leaves.get(employee.id, ()))]
            if starts:
                expected[employee.id] = min(starts)
        on_strike = {employee_id: hour for employee_id, hour in expected.items() if employee_id not in arrivals}
        return expected, on_strike


class EmsStaffStrikeReportLine(models.TransientModel):
    """A member of staff expected to work by a period of the strike report's day (see
    ems.staff_strike_report), and whether they were on strike by then."""
    _name = 'ems.staff_strike_report.line'
    _description = "Staff strike report line"
    _order = 'period, employee_id'

    report_id = fields.Many2one(string="Report", comodel_name='ems.staff_strike_report', required=True, ondelete='cascade')
    period = fields.Char(string="Period", required=True)
    employee_id = fields.Many2one(string="Employee", comodel_name='hr.employee', required=True, ondelete='cascade')
    employee_type = fields.Selection(string="Staff", selection=employee_types)
    contract_type_id = fields.Many2one(string="Contract Type", comodel_name='hr.contract.type')
    on_strike = fields.Integer(string="On strike", aggregator='sum')
    expected = fields.Integer(string="Expected to work", default=1, aggregator='sum')
