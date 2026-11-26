# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, time, timedelta

from pytz import UTC

from odoo import _, models


class EmsSpaceAvailability(models.Model):
    _inherit = 'ems.space'

    def _get_space_busy(self, start, end, exclude_reservations=None):
        """What holds these spaces between `start` and `end` (naive UTC datetimes, how Odoo stores
        them): a reservation (a meeting's included, it makes its own) or a weekly schedule block
        (classes and duties, read in the company's timezone; breaks never hold a space). Returns a
        list of dicts, one per holder: 'space_id', 'start' and 'end' (the company's local datetimes),
        'who' (the person, or the calendar when it has none) and 'is_reservation'.

        Two searches for any number of spaces and any length of span, under sudo(): whether a room
        is taken is a fact about the whole centre, not about what the acting user may read.
        Everything that asks whether a space is free goes through here."""
        busy = []
        if not self or not start or not end or start >= end:
            return busy
        utils = self.env['ems.datetime_utils']
        tz = utils.current_tz()
        local = lambda moment: utils.utc_datetime_to_local(UTC.localize(moment))
        start_local, end_local = local(start), local(end)

        reservations = self.env['ems.space_reservation'].sudo().search([
            ('space_id', 'in', self.ids),
            ('start_datetime', '<', end),
            ('end_datetime', '>', start),
            ('id', 'not in', (exclude_reservations or self.env['ems.space_reservation']).ids),
        ])
        for reservation in reservations:
            busy.append({
                'space_id': reservation.space_id.id, 'is_reservation': True, 'who': reservation.user_id.name,
                'start': local(reservation.start_datetime), 'end': local(reservation.end_datetime)})

        # One search for the whole span, then the days are walked in memory: a span of weeks (the
        # days a space is free) costs the same two queries as an hour.
        days = [start_local.date() + timedelta(days=offset) for offset in range((end_local.date() - start_local.date()).days + 1)]
        blocks = self.env['resource.calendar.attendance'].sudo().with_context(active_test=True).search([
            ('space_id', 'in', self.ids),
            ('calendar_id.active', '=', True),
            ('dayofweek', 'in', sorted({str(day.weekday()) for day in days})),
            ('non_teaching_is_break', '=', False),
            '|', ('date_from', '=', False), ('date_from', '<=', days[-1]),
            '|', ('date_to', '=', False), ('date_to', '>=', days[0]),
        ])
        for block in blocks:
            for day in days:
                if str(day.weekday()) != block.dayofweek or (block.date_from and block.date_from > day) \
                        or (block.date_to and block.date_to < day):
                    continue
                midnight = datetime.combine(day, time.min, tzinfo=tz)
                block_start, block_end = midnight + timedelta(hours=block.hour_from), midnight + timedelta(hours=block.hour_to)
                if block_start < end_local and block_end > start_local:
                    busy.append({
                        'space_id': block.space_id.id, 'is_reservation': False,
                        'who': block.employee_id.name or block.calendar_id.name, 'start': block_start, 'end': block_end})
        return busy
        utils = self.env['ems.datetime_utils']
        tz = utils.current_tz()
        local = lambda moment: utils.utc_datetime_to_local(UTC.localize(moment))
        start_local, end_local = local(start), local(end)

        reservations = self.env['ems.space_reservation'].sudo().search([
            ('space_id', 'in', self.ids),
            ('start_datetime', '<', end),
            ('end_datetime', '>', start),
            ('id', 'not in', (exclude_reservations or self.env['ems.space_reservation']).ids),
        ])
        for reservation in reservations:
            busy.append({
                'space_id': reservation.space_id.id, 'is_reservation': True, 'who': reservation.user_id.name,
                'start': local(reservation.start_datetime), 'end': local(reservation.end_datetime)})

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
            midnight = datetime.combine(day, time.min, tzinfo=tz)
            for block in blocks:
                busy.append({
                    'space_id': block.space_id.id, 'is_reservation': False,
                    'who': block.employee_id.name or block.calendar_id.name,
                    'start': midnight + timedelta(hours=block.hour_from), 'end': midnight + timedelta(hours=block.hour_to)})
            day += timedelta(days=1)
        return busy

    def _get_space_conflicts(self, start, end, exclude_reservations=None):
        """The same, as {space id: [one text per holder]} for the busy spaces only: a space missing
        from it is free. For messages (a reservation that clashes)."""
        conflicts = defaultdict(list)
        for holder in self._get_space_busy(start, end, exclude_reservations):
            args = {'who': holder['who'], 'day': holder['start'].strftime('%d/%m/%Y'),
                    'start': holder['start'].strftime('%H:%M'), 'end': holder['end'].strftime('%H:%M')}
            conflicts[holder['space_id']].append(
                _("reserved by %(who)s on %(day)s from %(start)s to %(end)s", **args) if holder['is_reservation']
                else _("in the weekly schedule of %(who)s on %(day)s from %(start)s to %(end)s", **args))
        return conflicts
