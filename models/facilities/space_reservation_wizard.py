# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from pytz import UTC

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

# The most days "which days is this space free" looks at in one go.
MAX_DAYS = 62


class EmsSpaceReservationWizard(models.TransientModel):
    """Reserving a space (issue #475). Two ways in, both reading the same answer
    ('ems.space._get_space_busy()'):
    - by date: a day, a start and a duration -> the spaces that are free;
    - by space: a space, a range of days, a start and a duration -> the days it is free (and what
      holds it the days it is not)."""
    _name = "ems.space_reservation_wizard"
    _description = "Reserve a space: by date (the free spaces) or by space (the days it is free)."
    _inherit = ['ems.datetime_utils']

    mode = fields.Selection(
        string="Search by", selection=[('date', "Date: which spaces are free"), ('space', "Space: which days it is free")],
        required=True, default='date')
    date = fields.Date(string="Day", default=lambda self: self.get_local_today())
    date_from = fields.Date(string="From", default=lambda self: self.get_local_today())
    date_to = fields.Date(string="To", default=lambda self: self.get_local_today() + timedelta(days=13))
    start_time = fields.Float(string="Start", required=True, default=10.0)
    duration = fields.Float(string="Duration", required=True, default=1.0, help="In hours.")
    space_type_id = fields.Many2one(
        string="Type", comodel_name="ems.space_type", domain="[('reservable', '=', True)]",
        help="Narrows the spaces looked at to those of this type.")
    space_id = fields.Many2one(string="Space", comodel_name="ems.space", domain="[('reservable', '=', True)]")
    reason = fields.Char(string="Reason")
    # Real records (not a computed list): a row's Reserve button needs the row to exist.
    line_ids = fields.One2many(
        string="Results", comodel_name="ems.space_reservation_wizard.line", inverse_name="wizard_id")

    def write(self, vals):
        # What was found no longer answers what is typed now.
        if vals.keys() & {'mode', 'date', 'date_from', 'date_to', 'start_time', 'duration', 'space_type_id', 'space_id'}:
            self.line_ids.unlink()
        return super().write(vals)

    def _slot(self, day):
        """(start, end) of the slot on `day`, as naive UTC datetimes; None while no duration is typed."""
        self.ensure_one()
        if not day or self.duration <= 0:
            raise UserError(_("Choose a day, a start and a duration greater than zero."))
        local = datetime.combine(day, time.min, tzinfo=self.current_tz()) + timedelta(hours=self.start_time)
        start = self.local_datetime_to_utc(local).replace(tzinfo=None)
        return start, start + timedelta(hours=self.duration)

    def action_search(self):
        """Fills the results (the free spaces or the days) and opens the wizard again with them."""
        self.ensure_one()
        self.line_ids.unlink()
        self.line_ids = self._free_spaces_lines() if self.mode == 'date' else self._free_days_lines()
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
        }

    def _free_spaces_lines(self):
        start, end = self._slot(self.date)
        spaces = self.env['ems.space'].search([('reservable', '=', True)] + (
            [('space_type_id', '=', self.space_type_id.id)] if self.space_type_id else []))
        busy = spaces._get_space_conflicts(start, end)
        return [Command.create({'space_id': space_id}) for space_id in spaces.ids if space_id not in busy]

    def _free_days_lines(self):
        """One line per day of the range (never before today, nor a slot already started): free, or
        what holds the space that day. The whole range is asked once."""
        if not self.space_id:
            raise UserError(_("Choose a space."))
        if not self.date_from or not self.date_to or self.date_to < self.date_from:
            raise UserError(_("Choose a range of days: the last one cannot be before the first one."))
        if (self.date_to - self.date_from).days >= MAX_DAYS:
            raise UserError(_("Choose at most %(days)s days at a time.", days=MAX_DAYS))
        now = fields.Datetime.now()
        slots = {}
        for offset in range((self.date_to - self.date_from).days + 1):
            day = self.date_from + timedelta(days=offset)
            slot = self._slot(day)
            if slot[0] >= now:
                slots[day] = slot
        if not slots:
            return []
        first, last = min(slot[0] for slot in slots.values()), max(slot[1] for slot in slots.values())
        holders = self.space_id._get_space_busy(first, last)
        utc = self.env['ems.datetime_utils']
        lines = []
        for day, (start, end) in slots.items():
            start_local, end_local = utc.utc_datetime_to_local(UTC.localize(start)), utc.utc_datetime_to_local(UTC.localize(end))
            holding = [holder for holder in holders if holder['start'] < end_local and holder['end'] > start_local]
            lines.append(Command.create({
                'date': day, 'weekday': format_date(self.env, day, date_format='EEEE'), 'is_free': not holding,
                'detail': "; ".join(
                    "%s-%s %s" % (holder['start'].strftime('%H:%M'), holder['end'].strftime('%H:%M'),
                                  (_("Reserved by %(who)s") if holder['is_reservation'] else _("Weekly schedule: %(who)s"))
                                  % {'who': holder['who']})
                    for holder in sorted(holding, key=lambda holder: holder['start'])) or False,
            }))
        return lines

    def _reserve(self, space, day):
        self.ensure_one()
        start, _end = self._slot(day)
        if start < fields.Datetime.now():
            raise UserError(_("A reservation cannot start in the past."))
        reservation = self.env['ems.space_reservation'].create({
            'space_id': space.id, 'start_datetime': start, 'duration': self.duration, 'reason': self.reason})
        return {
            'type': 'ir.actions.act_window', 'res_model': reservation._name, 'res_id': reservation.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current',
        }


class EmsSpaceReservationWizardLine(models.TransientModel):
    _name = "ems.space_reservation_wizard.line"
    _description = "A result of the reservation wizard: a free space, or a day a space is free or not."
    _order = "date, id"

    wizard_id = fields.Many2one(comodel_name="ems.space_reservation_wizard", required=True, ondelete='cascade')
    # By date: a free space.
    space_id = fields.Many2one(string="Space", comodel_name="ems.space")
    space_type_id = fields.Many2one(string="Type", related="space_id.space_type_id")
    # By space: a day.
    date = fields.Date(string="Day")
    weekday = fields.Char(string="Day of the week")
    is_free = fields.Boolean(string="Is free")
    detail = fields.Char(string="What holds it")

    def action_reserve(self):
        self.ensure_one()
        wizard = self.wizard_id
        return wizard._reserve(self.space_id or wizard.space_id, self.date or wizard.date)
