# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from pytz import UTC

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class EmsSpaceReservationWizard(models.TransientModel):
    """Reserving a space (issue #475). Two ways in, both reading the same answer
    ('ems.space._get_space_busy()'):
    - by date: a day, a start and an end -> the spaces that are free, to choose one;
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
    # Real records (not a computed list): the radio button of a row needs the row to exist.
    line_ids = fields.One2many(
        string="Results", comodel_name="ems.space_reservation_wizard.line", inverse_name="wizard_id")
    selected_line_id = fields.Many2one(
        string="Chosen result", comodel_name="ems.space_reservation_wizard.line", ondelete='set null')

    # By space. Its own slot fields, so each mode lays out its form on its own.
    space_id = fields.Many2one(string="Space", comodel_name="ems.space", domain="[('reservable', '=', True)]")
    show_grid = fields.Boolean(string="Show the occupation")
    space_day = fields.Date(string="Day to reserve")
    space_start = fields.Float(string="Start of the slot", default=10.0)
    space_end = fields.Float(string="End of the slot", default=11.0)
    space_reason = fields.Char(string="Reason of the reservation")

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for wizard in self:
            wizard.duration = wizard.end_time - wizard.start_time

    def write(self, vals):
        # What was found no longer answers what is typed now. The web client saves the chosen row
        # in the same write as the change (Search pressed after choosing a row and editing the
        # hour): the row is about to go, so the choice goes too.
        if vals.keys() & {'mode', 'date', 'start_time', 'end_time', 'space_type_id'}:
            self.line_ids.unlink()
            vals = {**vals, 'selected_line_id': False}
        if vals.keys() & {'mode', 'space_id'}:
            vals = {**vals, 'show_grid': False}
        return super().write(vals)

    def _slot(self, day, start_time, end_time):
        """(start, end) of the slot on `day`, as naive UTC datetimes."""
        if not day or end_time <= start_time or end_time > 24:
            raise UserError(_("Choose a day and a start and an end, the end after the start."))
        midnight = datetime.combine(day, time.min, tzinfo=self.current_tz())
        return tuple(
            self.local_datetime_to_utc(midnight + timedelta(hours=hour)).replace(tzinfo=None)
            for hour in (start_time, end_time))

    def action_search(self):
        """By date: fills the results with the spaces that are free. By space: shows the grid."""
        self.ensure_one()
        if self.mode == 'date':
            self.line_ids.unlink()
            self.line_ids = self._free_spaces_lines()
        else:
            if not self.space_id:
                raise UserError(_("Choose a space."))
            self.show_grid = True
        return {
            'type': 'ir.actions.act_window', 'name': _("Reserve a space"), 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new', 'context': {'dialog_size': 'large'},
        }

    def _free_spaces_lines(self):
        start, end = self._slot(self.date, self.start_time, self.end_time)
        spaces = self.env['ems.space'].search([('reservable', '=', True)] + (
            [('space_type_id', '=', self.space_type_id.id)] if self.space_type_id else []))
        busy = spaces._get_space_conflicts(start, end)
        return [Command.create({'space_id': space_id}) for space_id in spaces.ids if space_id not in busy]

    def action_reserve(self):
        """Reserves what the wizard has: the result chosen in the list (by date) or the slot of the
        chosen space (by space)."""
        self.ensure_one()
        if self.mode == 'date':
            if not self.selected_line_id:
                raise UserError(_("Choose one of the results."))
            space, day, start_time, end_time, reason = (
                self.selected_line_id.space_id, self.date, self.start_time, self.end_time, self.reason)
        else:
            if not self.space_id or not self.space_day:
                raise UserError(_("Choose a space and a free time of its week."))
            space, day, start_time, end_time, reason = (
                self.space_id, self.space_day, self.space_start, self.space_end, self.space_reason)
        start, end = self._slot(day, start_time, end_time)
        if start < fields.Datetime.now():
            raise UserError(_("A reservation cannot start in the past."))
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


class EmsSpaceReservationWizardLine(models.TransientModel):
    _name = "ems.space_reservation_wizard.line"
    _description = "A result of the reservation wizard: a space that is free for the time asked."
    _order = "id"

    wizard_id = fields.Many2one(comodel_name="ems.space_reservation_wizard", required=True, ondelete='cascade')
    space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
    space_type_id = fields.Many2one(string="Type", related="space_id.space_type_id")
    # Only hosts the radio button column (widget ems_radio_row): the choice is wizard.selected_line_id.
    selected = fields.Boolean(string="Choose")
