# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

DEFAULT_COLOR = "#3A8DDE"

# Odoo's own fixed color_picker palette (web/static/src/scss/secondary_variables.scss
# $o-colors), index 0-11 - used to remap ems_attendance_template's pre-existing integer
# values (which came from that same palette, via the kanban_color_picker/color_picker
# widgets) to their closest hex equivalent, so distinct existing rows stay distinct
# instead of all collapsing to one flat default color.
ODOO_PALETTE = [
    '#A2A2A2', '#EE2D2D', '#DC8534', '#E8BB1D', '#5794DD', '#9F628F',
    '#DB8865', '#41A9A2', '#304BE0', '#EE2F8A', '#61C36E', '#9872E6',
]


def _column_is_integer(cr, table, column):
    cr.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    row = cr.fetchone()
    return bool(row) and row[0] == 'integer'


def _migrate_role_color(cr):
    # ems.role.color moves from a fixed-palette Integer index to a free-pick hex Char.
    # Any existing value is not a valid hex code, so it can't carry meaning across the
    # type change - reset every row to a neutral default here; data/cat/ems.role.csv
    # (noupdate=False) reloads right after and gives the built-in roles their real,
    # distinct colors back. Centre-defined custom roles simply keep the default until
    # an admin repicks them with the new color widget.
    if not _column_is_integer(cr, 'ems_role', 'color'):
        return

    cr.execute(
        "ALTER TABLE ems_role ALTER COLUMN color TYPE varchar USING %s",
        (DEFAULT_COLOR,),
    )
    _logger.info("Migration 18.0.0.22.0: converted ems_role.color from integer to hex varchar.")


def _migrate_attendance_template_color(cr):
    # ems.attendance_template.color moves the same way, but these rows are live,
    # permanently-created user data (no fixture file reloads them afterwards, unlike
    # ems.role) - remap each existing integer through Odoo's own former palette (mod 12,
    # matching how the color_picker/kanban widgets already interpreted it) instead of
    # collapsing every row to one flat color.
    if not _column_is_integer(cr, 'ems_attendance_template', 'color'):
        return

    case_sql = " ".join(
        f"WHEN {index} THEN '{hex_color}'" for index, hex_color in enumerate(ODOO_PALETTE)
    )
    cr.execute(f"""
        ALTER TABLE ems_attendance_template ALTER COLUMN color TYPE varchar
        USING (CASE COALESCE(color, 0) % {len(ODOO_PALETTE)} {case_sql} END)
    """)
    _logger.info("Migration 18.0.0.22.0: converted ems_attendance_template.color from integer to hex varchar.")


def migrate(cr, _version):
    _migrate_role_color(cr)
    _migrate_attendance_template_color(cr)
