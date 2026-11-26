# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmsSpaceReservation(models.Model):
    # NOTE: a model of its own on purpose (issue #475). Odoo Community has no room booking (the
    # 'Meeting Rooms' app is Enterprise-only) and OCA's 'resource_booking' books combinations of
    # 'resource.resource' against a 'resource.calendar', while here a space is not a resource and
    # what occupies it lives in the teachers' schedule blocks ('resource.calendar.attendance.space_id'),
    # so it would need a mirrored calendar per space plus calendar events and invitation emails.
    # What is busy is decided by one place only: 'ems.space._get_space_busy()'.
    _name = "ems.space_reservation"
    _description = "Space reservation: a space held for a time span by a teacher or a meeting."
    _order = "start_datetime desc, id"

    space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True, index=True, ondelete='restrict')
    start_datetime = fields.Datetime(string="Start", required=True, index=True, default=fields.Datetime.now)
    duration = fields.Float(string="Duration", required=True, default=1.0, help="In hours.")
    end_datetime = fields.Datetime(string="End", compute="_compute_end_datetime", store=True, index=True)
    reason = fields.Char(string="Reason")
    user_id = fields.Many2one(
        string="Reserved by", comodel_name="res.users", required=True, index=True, ondelete='restrict',
        default=lambda self: self.env.user)
    minute_id = fields.Many2one(
        string="Meeting", comodel_name="ems.minute", index=True, ondelete='cascade', copy=False,
        help="Set when the reservation was made by a meeting's minute: it follows the minute.")
    # The spaces that are free for the span typed so far: the form only offers these.
    available_space_ids = fields.Many2many(
        string="Available spaces", comodel_name="ems.space", compute="_compute_available_space_ids")
    # Whether the current user may change it: the form shows someone else's reservation, or a
    # meeting's (it follows its minute), read only instead of failing on save.
    can_edit = fields.Boolean(string="Can edit", compute="_compute_can_edit")

    @api.depends('start_datetime', 'duration')
    def _compute_end_datetime(self):
        for reservation in self:
            reservation.end_datetime = reservation.start_datetime and reservation.start_datetime + timedelta(
                hours=max(reservation.duration, 0.0))

    @api.depends('start_datetime', 'duration')
    def _compute_available_space_ids(self):
        Space = self.env['ems.space']
        for reservation in self:
            # A meeting's room is not a request to reserve a space: any room, reservable or not.
            spaces = Space.search([] if reservation.minute_id else [('reservable', '=', True)])
            if not reservation.start_datetime or reservation.duration <= 0:
                reservation.available_space_ids = spaces
                continue
            end = reservation.start_datetime + timedelta(hours=reservation.duration)
            reservation.available_space_ids = spaces._filter_free(
                reservation.start_datetime, end, exclude_reservations=reservation._origin)

    @api.depends('user_id', 'minute_id')
    @api.depends_context('uid')
    def _compute_can_edit(self):
        # The record rules decide (one check for the whole batch), never a copy of them here.
        writable = self._origin._filtered_access('write')
        for reservation in self:
            reservation.can_edit = not reservation.minute_id and (
                not reservation._origin or reservation._origin in writable)

    @api.depends('space_id', 'reason', 'start_datetime')
    def _compute_display_name(self):
        for reservation in self:
            reservation.display_name = " - ".join(filter(None, [reservation.space_id.display_name, reservation.reason]))

    @api.constrains('duration')
    def _check_duration(self):
        for reservation in self:
            if reservation.duration <= 0:
                raise ValidationError(_("The duration of a reservation must be greater than zero."))

    @api.constrains('space_id', 'minute_id')
    def _check_space_is_reservable(self):
        for reservation in self:
            if not reservation.minute_id and not reservation.space_id.reservable:
                raise ValidationError(_("%(space)s cannot be reserved.", space=reservation.space_id.display_name))

    @api.constrains('space_id', 'start_datetime', 'duration')
    def _check_space_is_free(self):
        for reservation in self:
            conflicts = reservation.space_id._get_space_conflicts(
                reservation.start_datetime, reservation.end_datetime, exclude_reservations=reservation)
            if conflicts.get(reservation.space_id.id):
                raise ValidationError(_(
                    "%(space)s is not free:\n%(conflicts)s",
                    space=reservation.space_id.display_name,
                    conflicts="\n".join(conflicts[reservation.space_id.id])))

    def unlink(self):
        # Clear messages instead of the record rules' generic access error. The minute removes its
        # own reservation under sudo() when its room goes.
        if not self.env.su:
            if self.filtered('minute_id'):
                raise UserError(_("A meeting's room reservation follows its meeting: change or remove the room in the meeting."))
            if self - self._filtered_access('unlink'):
                raise UserError(_("You can only change your own reservations."))
        return super().unlink()
