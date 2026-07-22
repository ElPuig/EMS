# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

DEFAULT_COLOR = "#3A8DDE"


def migrate(cr, _version):
    # ems.role.color moves from a fixed-palette Integer index to a free-pick hex Char.
    # Any existing value is not a valid hex code, so it can't carry meaning across the
    # type change - reset every row to a neutral default here; data/cat/ems.role.csv
    # (noupdate=False) reloads right after and gives the built-in roles their real,
    # distinct colors back. Centre-defined custom roles simply keep the default until
    # an admin repicks them with the new color widget.
    cr.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'ems_role' AND column_name = 'color'
    """)
    row = cr.fetchone()
    if not row or row[0] != 'integer':
        return

    cr.execute(
        "ALTER TABLE ems_role ALTER COLUMN color TYPE varchar USING %s",
        (DEFAULT_COLOR,),
    )
    _logger.info("Migration 18.0.0.22.0: converted ems_role.color from integer to hex varchar.")
