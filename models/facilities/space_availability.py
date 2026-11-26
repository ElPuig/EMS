# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import timedelta

from pytz import UTC

from odoo import _, models


class EmsSpaceAvailability(models.Model):
    _inherit = 'ems.space'

    def _get_space_conflicts(self, start, end, exclude_reservations=None):
        """What holds each of these spaces between `start` and `end` (naive UTC datetimes, how Odoo
        stores them): a weekly schedule block (classes and duties, read in the company's timezone)
        or a reservation (a meeting's included, it makes its own). Returns {space id: [one text per
        holder]}, only for the spaces that are busy; a space missing from it is free.

        Two searches for any number of spaces (plus one per calendar day the span touches, almost
        always one), under sudo(): whether a room is taken is a fact about the whole centre, not
        about what the acting user may read."""
        conflicts = defaultdict(list)
        if not self or not start or not end or start >= end:
            return conflicts
        utils = self.env['ems.datetime_utils']
        start_local = utils.utc_datetime_to_local(UTC.localize(start))
        end_local = utils.utc_datetime_to_local(UTC.localize(end))

        reservations = self.env['ems.space_reservation'].sudo().search([
            ('space_id', 'in', self.ids),
            ('start_datetime', '<', end),
            ('end_datetime', '>', start),
            ('id', 'not in', (exclude_reservations or self.env['ems.space_reservation']).ids),
        ])
        for reservation in reservations:
            conflicts[reservation.space_id.id].append(_(
                "reserved by %(user)s on %(day)s from %(start)s to %(end)s",
                user=reservation.user_id.name,
                day=utils.utc_datetime_to_local(UTC.localize(reservation.start_datetime)).strftime('%d/%m/%Y'),
                start=utils.utc_datetime_to_local(UTC.localize(reservation.start_datetime)).strftime('%H:%M'),
                end=utils.utc_datetime_to_local(UTC.localize(reservation.end_datetime)).strftime('%H:%M')))

        Block = self.env['resource.calendar.attendance'].sudo().with_context(active_test=True)
        day = start_local.date()
        while day <= end_local.date():
            hour_from = start_local.hour + start_local.minute / 60.0 if day == start_local.date() else 0.0
            hour_to = end_local.hour + end_local.minute / 60.0 if day == end_local.date() else 24.0
            blocks = Block.search([
                ('space_id', 'in', self.ids),
                ('calendar_id.active', '=', True),
                ('dayofweek', '=', str(day.weekday())),
                ('hour_from', '<', hour_to),
                ('hour_to', '>', hour_from),
                ('non_teaching_is_break', '=', False),
                '|', ('date_from', '=', False), ('date_from', '<=', day),
                '|', ('date_to', '=', False), ('date_to', '>=', day),
            ])
            for block in blocks:
                conflicts[block.space_id.id].append(_(
                    "in the weekly schedule of %(who)s on %(day)s from %(start)s to %(end)s",
                    who=block.employee_id.name or block.calendar_id.name,
                    day=day.strftime('%d/%m/%Y'),
                    start=self._hour_label(block.hour_from),
                    end=self._hour_label(block.hour_to)))
            day += timedelta(days=1)
        return conflicts

    @staticmethod
    def _hour_label(hour):
        """A float hour as HH:MM."""
        minutes = int(round(hour * 60))
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
