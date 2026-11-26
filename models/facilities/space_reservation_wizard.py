# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class EmsSpaceReservationWizard(models.TransientModel):
    """Reserving a space (issue #475): say the day, the start and the duration and either see the
    spaces that are free for it (and reserve one), or name the space needed and see what holds it
    that day. Both read the same answer, 'ems.space._get_space_busy()'."""
    _name = "ems.space_reservation_wizard"
    _description = "Reserve a space: by date (the free spaces) or by space (what holds it)."
    _inherit = ['ems.datetime_utils']

    date = fields.Date(string="Day", required=True, default=lambda self: self.get_local_today())
    start_time = fields.Float(string="Start", required=True, default=10.0)
    duration = fields.Float(string="Duration", required=True, default=1.0, help="In hours.")
    space_type_id = fields.Many2one(string="Type", comodel_name="ems.space_type")
    space_id = fields.Many2one(
        string="Space", comodel_name="ems.space", domain="[('reservable', '=', True)]",
        help="Leave it empty to see the spaces that are free; choose one to see what holds it that day.")
    reason = fields.Char(string="Reason")
    start_datetime = fields.Datetime(string="Starts at", compute="_compute_start_datetime")
    # Real records (not a computed list): a row's Reserve button needs the row to exist.
    line_ids = fields.One2many(
        string="Free spaces", comodel_name="ems.space_reservation_wizard.line", inverse_name="wizard_id")
    space_is_free = fields.Boolean(string="Space is free", compute="_compute_space_occupation")
    occupation_html = fields.Html(string="That day", compute="_compute_space_occupation", sanitize=False)

    @api.depends('date', 'start_time')
    def _compute_start_datetime(self):
        tz = self.current_tz()
        for wizard in self:
            wizard.start_datetime = wizard.date and self.local_datetime_to_utc(
                datetime.combine(wizard.date, time.min, tzinfo=tz) + timedelta(hours=wizard.start_time)
            ).replace(tzinfo=None)

    def _span(self):
        """(start, end) as naive UTC datetimes, or None while what was typed makes no span."""
        self.ensure_one()
        if not self.start_datetime or self.duration <= 0:
            return None
        return self.start_datetime, self.start_datetime + timedelta(hours=self.duration)

    def write(self, vals):
        # What was found no longer answers what is typed now.
        if vals.keys() & {'date', 'start_time', 'duration', 'space_type_id', 'space_id'}:
            self.line_ids.unlink()
        return super().write(vals)

    def action_search(self):
        """Lists the spaces that are free for the span typed (the wizard opens again with them)."""
        self.ensure_one()
        span = self._span()
        if not span:
            raise UserError(_("Choose a day, a start and a duration greater than zero."))
        Space = self.env['ems.space']
        spaces = Space.search([('reservable', '=', True)] + (
            [('space_type_id', '=', self.space_type_id.id)] if self.space_type_id else []))
        busy = spaces._get_space_conflicts(*span)
        self.line_ids.unlink()
        self.line_ids = [Command.create({'space_id': space_id}) for space_id in spaces.ids if space_id not in busy]
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
        }

    @api.depends('start_datetime', 'duration', 'date', 'space_id')
    def _compute_space_occupation(self):
        tz = self.current_tz()
        for wizard in self:
            wizard.space_is_free = False
            wizard.occupation_html = False
            span = wizard._span()
            if not wizard.space_id or not span:
                continue
            wizard.space_is_free = not wizard.space_id._get_space_conflicts(*span)
            midnight = datetime.combine(wizard.date, time.min, tzinfo=tz)
            day_start = self.local_datetime_to_utc(midnight).replace(tzinfo=None)
            day_end = self.local_datetime_to_utc(midnight + timedelta(days=1)).replace(tzinfo=None)
            holders = sorted(wizard.space_id._get_space_busy(day_start, day_end), key=lambda holder: holder['start'])
            wizard.occupation_html = self.env['ems.base'].build_html_list([
                Markup("<b>{}-{}</b> {}").format(
                    holder['start'].strftime('%H:%M'), holder['end'].strftime('%H:%M'),
                    (_("Reserved by %(who)s") if holder['is_reservation'] else _("Weekly schedule: %(who)s"))
                    % {'who': holder['who']})
                for holder in holders
            ]) or Markup("<p>{}</p>").format(_("Nothing holds this space that day."))

    def action_reserve(self):
        """Reserves the space chosen in the wizard."""
        self.ensure_one()
        return self._reserve(self.space_id)

    def _reserve(self, space):
        self.ensure_one()
        span = self._span()
        if not span:
            raise UserError(_("Choose a day, a start and a duration greater than zero."))
        if span[0] < fields.Datetime.now():
            raise UserError(_("A reservation cannot start in the past."))
        reservation = self.env['ems.space_reservation'].create({
            'space_id': space.id, 'start_datetime': span[0], 'duration': self.duration, 'reason': self.reason})
        return {
            'type': 'ir.actions.act_window', 'res_model': reservation._name, 'res_id': reservation.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current',
        }


class EmsSpaceReservationWizardLine(models.TransientModel):
    _name = "ems.space_reservation_wizard.line"
    _description = "A space that is free for the span chosen in the reservation wizard."

    wizard_id = fields.Many2one(comodel_name="ems.space_reservation_wizard", required=True, ondelete='cascade')
    space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
    space_type_id = fields.Many2one(string="Type", related="space_id.space_type_id")

    def action_reserve(self):
        self.ensure_one()
        return self.wizard_id._reserve(self.space_id)
