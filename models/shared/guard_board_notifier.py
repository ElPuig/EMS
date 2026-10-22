# -*- coding: utf-8 -*-

from pytz import UTC

from odoo import api, models

# The bus channel the guard duty board listens on (issue #692). A plain string any client can
# subscribe to, the guard room's kiosk included (#591/#642): the message only says which days
# changed, never what or whose.
GUARD_BOARD_CHANNEL = 'ems.guard_duty_board'
GUARD_BOARD_CHANGED = 'ems.guard_duty_board/changed'


class EmsGuardBoardNotifier(models.AbstractModel):
    """Tells every open guard duty board that something it shows changed (issue #692): a check-in,
    a guard sent or released, an absence, an expected absence, a timetable change told to the
    families. The board reloads when it hears about the day it is showing, instead of asking the
    server again and again. Sent on commit through the bus, so a rolled-back change says nothing.

    A model using it sets `_guard_board_fields` (the fields whose change matters; empty = any) and
    implements `_guard_board_spans()`."""
    _name = 'ems.guard_board_notifier'
    _description = 'Guard duty board change notifier'

    _guard_board_fields = ()

    def _guard_board_spans(self):
        """`{(date_from, date_to)}`: the days of the board these records appear on."""
        raise NotImplementedError

    def _guard_board_local_date(self, value):
        """A UTC datetime field as the company's calendar day."""
        if not value:
            return None
        return self.env['ems.datetime_utils'].utc_datetime_to_local(value.replace(tzinfo=UTC)).date()

    def _notify_guard_board(self):
        bus = self.env['bus.bus'].sudo()
        for date_from, date_to in {span for span in self._guard_board_spans() if all(span)}:
            bus._sendone(GUARD_BOARD_CHANNEL, GUARD_BOARD_CHANGED,
                         {'date_from': str(date_from), 'date_to': str(date_to)})

    def _guard_board_relevant(self, vals):
        return not self._guard_board_fields or bool(vals.keys() & set(self._guard_board_fields))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_guard_board()
        return records

    def write(self, vals):
        relevant = self._guard_board_relevant(vals)
        if relevant:
            self._notify_guard_board()  # the days it leaves
        result = super().write(vals)
        if relevant:
            self._notify_guard_board()  # the days it moves to
        return result

    def unlink(self):
        self._notify_guard_board()
        return super().unlink()
