# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _reserve_rooms_of_upcoming_meetings(api.Environment(cr, SUPERUSER_ID, {}))


def _reserve_rooms_of_upcoming_meetings(env):
    """Issue #475: a meeting's room is now held through a reservation of its own. The meetings
    already scheduled in a room (in person or hybrid, from now on) get theirs, oldest first, so
    that when two of them hold the same room at once the earlier one keeps it. A meeting whose room
    is taken (by a schedule block or another meeting) is left without a reservation and logged,
    never failed: the migration must not block data that already existed. Past meetings need none.
    Needs the ORM (post-migrate), after the model's table exists."""
    minutes = env['ems.minute'].search([
        ('space_id', '!=', False),
        ('modality', 'in', ('in-person', 'hybrid')),
        ('start_datetime', '>=', fields.Datetime.now()),
        ('duration', '>', 0),
        ('space_reservation_ids', '=', False),
    ], order='start_datetime, id')
    for minute in minutes:
        try:
            with env.cr.savepoint():
                minute._ems_sync_space_reservation()
        except ValidationError as error:
            _logger.warning("Meeting %s keeps no room reservation, its room is taken: %s",
                            minute.display_name, error.args[0].replace("\n", "; "))
