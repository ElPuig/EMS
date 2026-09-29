# -*- coding: utf-8 -*-

from datetime import time, timedelta

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# The absence states the guard duty board plans around (see guard_duty_board.ABSENCE_STATES): an
# absence in any of them is the teacher's own request taking over from a pending one.
ACTIVE_LEAVE_STATES = ('confirm', 'validate1', 'validate')

# The school day a new entry is prefilled with, in the company's timezone.
DEFAULT_HOUR_FROM = 8.0
DEFAULT_HOUR_TO = 15.0


class EmsAbsencePending(models.Model):
    """An absence the Head of Studies or their Deputy already knows is coming, entered on the
    teacher's behalf until the teacher files the real request (issue #509). It only exists so the
    guard duty board can plan around it: once the teacher's own absence is filed, the two are
    linked for good and the real one is all that counts from then on."""
    _name = "ems.absence_pending"
    _description = "Expected absence"
    _inherit = ["mail.thread", "ems.datetime_utils"]
    _order = "date_from desc, id desc"

    employee_id = fields.Many2one(
        string="Teacher", comodel_name="hr.employee", required=True, tracking=True,
        domain=lambda self: self._domain_employee_id(),
        help="Only the teachers below you in the hierarchy.")
    date_from = fields.Datetime(
        string="From", required=True, tracking=True,
        default=lambda self: self._default_local_hour(DEFAULT_HOUR_FROM))
    date_to = fields.Datetime(
        string="To", required=True, tracking=True,
        default=lambda self: self._default_local_hour(DEFAULT_HOUR_TO))
    note = fields.Text(string="Notes")
    state = fields.Selection(
        string="Status", selection=[('pending', 'Expected'), ('linked', 'Requested')],
        default='pending', required=True, readonly=True, copy=False, tracking=True,
        help="Expected until the teacher requests the absence themselves, then linked to their "
             "request for good: from that moment only the request counts, whatever becomes of it.")
    leave_id = fields.Many2one(
        string="Absence requested", comodel_name="hr.leave", readonly=True, copy=False,
        ondelete="set null")

    def _domain_employee_id(self):
        """The same reach as the record rules: every teacher for a technical administrator
        (rule_absence_pending_system), otherwise the user's own branch of the hierarchy
        (rule_absence_pending_hierarchy)."""
        domain = [('employee_type', '=', 'teacher')]
        if self.env.user.has_group('base.group_system'):
            return domain
        return domain + [('id', 'child_of', self.env.user.employee_ids.ids)]

    def _default_local_hour(self, hour):
        return self.datetime_to_odoo(self.time_float_to_utc_datetime(self.get_local_today(), hour))

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for absence in self:
            if not (absence.employee_id and absence.date_from and absence.date_to):
                absence.display_name = absence.employee_id.name or _("New")
                continue
            start, stop = (self._to_local(value) for value in (absence.date_from, absence.date_to))
            absence.display_name = _(
                "%(teacher)s (%(start)s - %(stop)s)", teacher=absence.employee_id.name,
                start=start.strftime('%d/%m/%Y %H:%M'), stop=stop.strftime('%d/%m/%Y %H:%M'))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for absence in self:
            if absence.date_to <= absence.date_from:
                raise ValidationError(_("The end of an absence must come after its start."))

    def write(self, vals):
        if vals.keys() & {'employee_id', 'date_from', 'date_to'} and 'linked' in self.mapped('state'):
            raise ValidationError(_("This absence has already been requested by the teacher: "
                                    "only their own request counts now."))
        return super().write(vals)

    def _to_local(self, value):
        return self.utc_datetime_to_local(value.replace(tzinfo=UTC))

    def _get_local_hours(self, day):
        """(hour_from, hour_to) of the part of this absence that falls on `day`, in the company's
        timezone, or None when it does not touch that day - the same shape the guard duty board
        reads an hr.leave in."""
        self.ensure_one()
        start, stop = self._to_local(self.date_from), self._to_local(self.date_to)
        if start.date() > day or stop.date() < day or (stop.date() == day and stop.time() == time.min):
            return None
        hour_from = self.time_to_float(start) if start.date() == day else 0.0
        hour_to = self.time_to_float(stop) if stop.date() == day else 24.0
        return hour_from, hour_to

    @api.model
    def _link_to_leaves(self, leaves):
        """Links every pending entry to the teacher's own absence overlapping it. sudo(): the
        teacher filing that absence has no access to this model at all, which is the point of
        it."""
        Pending = self.sudo()
        for leave in leaves.filtered(lambda leave: leave.state in ACTIVE_LEAVE_STATES):
            start, stop = leave._ems_utc_range()
            Pending.search([
                ('state', '=', 'pending'),
                ('employee_id', '=', leave.employee_id.id),
                ('date_from', '<', stop),
                ('date_to', '>', start),
            ]).write({'state': 'linked', 'leave_id': leave.id})

    def _utc_bounds(self, day, hour_from, hour_to):
        """Naive UTC datetimes for `hour_from` on `day` and `hour_to` on `day` (24.0 meaning the
        next day's midnight), in the company's timezone."""
        stop_day, hour_to = (day + timedelta(days=1), 0.0) if hour_to >= 24.0 else (day, hour_to)
        return tuple(self.datetime_to_odoo(self.time_float_to_utc_datetime(when, hour))
                     for when, hour in ((day, hour_from), (stop_day, hour_to)))


class EmsAbsencePendingLeave(models.Model):
    _inherit = "hr.leave"

    ems_pending_absence_ids = fields.One2many(
        string="Expected absences", comodel_name="ems.absence_pending", inverse_name="leave_id",
        readonly=True, groups="ems.group_head_of_studies")

    def _ems_utc_range(self):
        """(start, stop) as naive UTC datetimes, read the same way the guard duty board does: the
        requested hours for a partial one-day absence, whole days in the company's timezone
        otherwise. Not Odoo's own date_from/date_to, which clip a whole day to the employee's
        working hours."""
        self.ensure_one()
        Pending = self.env['ems.absence_pending']
        partial = self.request_unit_hours and self.request_date_from == self.request_date_to
        if partial:
            return Pending._utc_bounds(self.request_date_from, self.request_hour_from, self.request_hour_to)
        start, _stop = Pending._utc_bounds(self.request_date_from, 0.0, 24.0)
        _start, stop = Pending._utc_bounds(self.request_date_to, 0.0, 24.0)
        return start, stop

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        self.env['ems.absence_pending']._link_to_leaves(leaves)
        return leaves

    def write(self, vals):
        result = super().write(vals)
        if vals.keys() & {'employee_id', 'state', 'request_date_from', 'request_date_to',
                          'request_hour_from', 'request_hour_to', 'ems_full_day'}:
            self.env['ems.absence_pending']._link_to_leaves(self)
        return result
