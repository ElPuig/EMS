# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class EmsSpaceReservationWizard(models.TransientModel):
    """Reserving a space (issue #475). Two ways in, both reading the same answer
    ('ems.space._get_space_busy()'):
    - by date: a day, a start and an end -> the spaces that are free (recomputed at every change), to
      choose one;
    - by space: a space -> its week as a grid (what holds it, when it is free), where the slot is
      chosen by dragging over a free time (or typing it)."""
    _name = "ems.space_reservation_wizard"
    _description = "Reserve a space: by date (the free spaces) or by space (when it is free)."
    _inherit = ['ems.datetime_utils']

    mode = fields.Selection(
        string="Search by", selection=[('date', "Date: which spaces are free"), ('space', "Space: when it is free")],
        required=True, default='date')

    # By date.
    date = fields.Date(string="Day", default=lambda self: self.get_local_today())
    start_time = fields.Float(string="Start", required=True, default=10.0)
    end_time = fields.Float(string="End", required=True, default=11.0)
    duration = fields.Float(string="Duration", compute="_compute_duration", help="In hours.")
    space_type_id = fields.Many2one(
        string="Type", comodel_name="ems.space_type", domain="[('reservable', '=', True)]",
        help="Narrows the spaces looked at to those of this type.")
    reason = fields.Char(string="Reason")
    # Recomputed by the form at every change of the day, the hours or the type: no search button.
    free_space_ids = fields.Many2many(
        string="Free spaces", comodel_name="ems.space", compute="_compute_free_space_ids",
        help="The reservable spaces (of the type chosen) that nothing holds at that time.")
    # Kept while the space is still free for what is typed, dropped when it is not.
    chosen_space_id = fields.Many2one(
        string="Chosen space", comodel_name="ems.space", compute="_compute_chosen_space_id", store=True,
        readonly=False)

    # By space. Its own slot fields, so each mode lays out its form on its own.
    space_id = fields.Many2one(string="Space", comodel_name="ems.space", domain="[('reservable', '=', True)]")
    # Only hosts the week grid (widget ems_space_week_grid), which loads itself once there is a space.
    show_grid = fields.Boolean(string="Show the occupation", compute="_compute_show_grid")
    space_day = fields.Date(string="Day to reserve")
    space_start = fields.Float(string="Start of the slot", default=10.0)
    space_end = fields.Float(string="End of the slot", default=11.0)
    space_reason = fields.Char(string="Reason of the reservation")

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for wizard in self:
            wizard.duration = wizard.end_time - wizard.start_time

    @api.depends('mode', 'date', 'start_time', 'end_time', 'space_type_id')
    def _compute_free_space_ids(self):
        for wizard in self:
            wizard.free_space_ids = wizard._free_spaces()

    @api.depends('mode', 'date', 'start_time', 'end_time', 'space_type_id')
    def _compute_chosen_space_id(self):
        for wizard in self:
            # By id: in the form's onchange the chosen space comes as a new record (its _origin is the real one).
            if wizard.chosen_space_id._origin.id not in wizard.free_space_ids._origin.ids:
                wizard.chosen_space_id = False

    @api.depends('space_id')
    def _compute_show_grid(self):
        for wizard in self:
            wizard.show_grid = bool(wizard.space_id)

    @api.onchange('space_day', 'space_start')
    def _onchange_space_slot_not_past(self):
        """By space: a day and a start typed by hand that have already begun are refused on the spot
        (the grid already refuses them when dragging): the day is cleared, so nothing is drawn and
        Reserve stays disabled."""
        if self.mode != 'space' or not self.space_day:
            return None
        midnight = datetime.combine(self.space_day, time.min, tzinfo=self.current_tz())
        start = self.local_datetime_to_utc(midnight + timedelta(hours=self.space_start)).replace(tzinfo=None)
        if start >= fields.Datetime.now():
            return None
        self.space_day = False
        return {'warning': {'title': _("Reserve a space"), 'message': self._past_message()}}

    @api.model
    def _past_message(self):
        return _("A reservation cannot start in the past.")

    def _slot(self, day, start_time, end_time):
        """(start, end) of the slot on `day`, as naive UTC datetimes."""
        if not day or end_time <= start_time or end_time > 24:
            raise UserError(_("Choose a day and a start and an end, the end after the start."))
        midnight = datetime.combine(day, time.min, tzinfo=self.current_tz())
        return tuple(
            self.local_datetime_to_utc(midnight + timedelta(hours=hour)).replace(tzinfo=None)
            for hour in (start_time, end_time))

    def _free_spaces(self):
        """By date: the reservable spaces (of the type chosen) free for the slot typed; none while the
        slot is incomplete or the end is not after the start (the form says so)."""
        self.ensure_one()
        spaces = self.env['ems.space']
        if self.mode != 'date' or not self.date or not 0 <= self.start_time < self.end_time <= 24:
            return spaces
        start, end = self._slot(self.date, self.start_time, self.end_time)
        spaces = spaces.search([('reservable', '=', True)] + (
            [('space_type_id', '=', self.space_type_id.id)] if self.space_type_id else []))
        busy = spaces._get_space_conflicts(start, end)
        return spaces.filtered(lambda space: space.id not in busy)

    def action_reserve(self):
        """Reserves what the wizard has: the result chosen in the list (by date) or the slot of the
        chosen space (by space)."""
        self.ensure_one()
        if self.mode == 'date':
            if not self.chosen_space_id:
                raise UserError(_("Choose one of the free spaces."))
            space, day, start_time, end_time, reason = (
                self.chosen_space_id, self.date, self.start_time, self.end_time, self.reason)
        else:
            if not self.space_id or not self.space_day:
                raise UserError(_("Choose a space and a free time of its week."))
            space, day, start_time, end_time, reason = (
                self.space_id, self.space_day, self.space_start, self.space_end, self.space_reason)
        start, end = self._slot(day, start_time, end_time)
        if start < fields.Datetime.now():
            raise UserError(self._past_message())
        reservation = self.env['ems.space_reservation'].create({
            'space_id': space.id, 'start_datetime': start, 'duration': (end - start).total_seconds() / 3600.0,
            'reason': reason})
        return {
            'type': 'ir.actions.act_window', 'res_model': reservation._name, 'res_id': reservation.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current',
        }

    @api.model
    def get_occupation_week(self, space_id, monday=None):
        """The week of a space for the grid of the by-space mode: the seven days from `monday` (an
        ISO date; the week of today when none), what holds the space in each (hours as floats, in
        the company's timezone) and the hours the grid covers (the school day of the default
        schedule framework, widened to take in anything held outside it)."""
        utils = self.env['ems.datetime_utils']
        today = utils.get_local_today()
        first = fields.Date.to_date(monday) if monday else today - timedelta(days=today.weekday())
        first -= timedelta(days=first.weekday())
        tz = utils.current_tz()
        start = utils.local_datetime_to_utc(datetime.combine(first, time.min, tzinfo=tz)).replace(tzinfo=None)
        end = utils.local_datetime_to_utc(datetime.combine(first + timedelta(days=7), time.min, tzinfo=tz)).replace(tzinfo=None)
        space = self.env['ems.space'].browse(space_id).exists()
        holders = space._get_space_busy(start, end) if space else []
        blocks = []
        for holder in holders:
            day_index = (holder['start'].date() - first).days
            if not 0 <= day_index <= 6:
                continue    # held from the week before: its hours of this week are not drawn
            midnight = datetime.combine(holder['start'].date(), time.min, tzinfo=tz)
            blocks.append({
                'day': day_index,
                'start': (holder['start'] - midnight).total_seconds() / 3600.0,
                'end': min((holder['end'] - midnight).total_seconds() / 3600.0, 24.0),
                'kind': 'reservation' if holder['is_reservation'] else 'schedule',
                'label': (_("Reserved by %(who)s") if holder['is_reservation'] else _("Weekly schedule: %(who)s"))
                % {'who': holder['who']},
            })
        hours = self.env.company.default_schedule_framework_id.attendance_ids
        hour_from = int(min(hours.mapped('hour_from'), default=8.0))
        hour_to = -int(-max(hours.mapped('hour_to'), default=21.0) // 1)
        for block in blocks:
            hour_from = min(hour_from, int(block['start']))
            hour_to = max(hour_to, -int(-block['end'] // 1))
        return {
            'monday': fields.Date.to_string(first), 'today': fields.Date.to_string(today),
            'days': [{'date': fields.Date.to_string(first + timedelta(days=offset)),
                      'label': format_date(self.env, first + timedelta(days=offset), date_format='EEE d/M')}
                     for offset in range(7)],
            'hour_from': hour_from, 'hour_to': min(hour_to, 24), 'blocks': blocks,
        }

