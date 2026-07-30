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


def _rename_old_status_columns(cr):
    """ems_attendance_session_line.status / ems_attendance_issue_status.attendance_status
    (both Selection) become Many2one status_id/attendance_status_id in this version - see
    docs/en/developers/attendance/attendance_status.md. The post-migrate backfill needs to
    read the old string values, but confirmed empirically on a dev box: as soon as this
    module's schema sync runs (right after pre-migrate), Odoo's own ir.model.fields
    cleanup for the now-removed field drops the physical column outright - there is no
    window where the old column and the new one coexist unless the old one is moved out
    of the way first. Renaming here (before schema sync ever runs) sidesteps that: Odoo's
    cleanup only knows to drop a column literally named "status"/"attendance_status" (via
    the stale ir.model.fields record for that exact name), so the renamed copies are never
    a target and survive through to post-migrate, which reads them and drops them itself
    once the backfill is done.
    """
    if _column_exists(cr, 'ems_attendance_session_line', 'status'):
        cr.execute("ALTER TABLE ems_attendance_session_line RENAME COLUMN status TO status_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_attendance_session_line.status as status_old for the post-migrate backfill.")

    if _column_exists(cr, 'ems_attendance_issue_status', 'attendance_status'):
        cr.execute("ALTER TABLE ems_attendance_issue_status RENAME COLUMN attendance_status TO attendance_status_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_attendance_issue_status.attendance_status as attendance_status_old for the post-migrate backfill.")


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _rename_old_special_columns(cr):
    """ems_limesurvey_block.special_wpi_enrolled/special_subject_enrolled (both Boolean)
    become a single special_type Selection in this version - see
    plans/limesurvey_block_special_mutual_exclusion_asymmetry.md (now resolved). Same
    rename-before-schema-sync gotcha as _rename_old_status_columns above: renaming here
    (before the fields are removed from the model) keeps the old values reachable for the
    post-migrate backfill, since Odoo's own field-removal cleanup would otherwise drop the
    columns outright.
    """
    if _column_exists(cr, 'ems_limesurvey_block', 'special_wpi_enrolled'):
        cr.execute("ALTER TABLE ems_limesurvey_block RENAME COLUMN special_wpi_enrolled TO special_wpi_enrolled_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_limesurvey_block.special_wpi_enrolled as special_wpi_enrolled_old for the post-migrate backfill.")

    if _column_exists(cr, 'ems_limesurvey_block', 'special_subject_enrolled'):
        cr.execute("ALTER TABLE ems_limesurvey_block RENAME COLUMN special_subject_enrolled TO special_subject_enrolled_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_limesurvey_block.special_subject_enrolled as special_subject_enrolled_old for the post-migrate backfill.")


def _dedupe_ems_enrollment(cr):
    """ems.enrollment gets a new UNIQUE(student_id, group_id, subject_id) constraint in
    this version (see plans/enrollment_junction_duplicate_constraint.md) - the schema sync
    right after pre-migrate would fail to create it while duplicate rows still exist. All
    42 duplicate rows found in production (21 triples) were confirmed field-identical
    within their pair (only id/timestamps differ), so keeping the lowest id per triple and
    dropping the rest loses no information. Deleted directly via SQL, not ORM unlink() -
    unlink()'s _ems_sync_grade_session_remove has no still-enrolled guard (unlike its
    sibling _ems_sync_attendance_template_remove - see
    plans/grade_session_remove_missing_still_enrolled_guard.md), so going through the ORM
    here would risk wiping the surviving student's grade lines for an open session.
    """
    cr.execute("""
        DELETE FROM ems_enrollment a
        USING ems_enrollment b
        WHERE a.student_id = b.student_id
          AND a.group_id = b.group_id
          AND a.subject_id = b.subject_id
          AND a.id > b.id
    """)
    if cr.rowcount:
        _logger.info(
            "Migration 18.0.0.22.0: removed %d duplicate ems_enrollment row(s) "
            "(student_id, group_id, subject_id) ahead of the new unique constraint.",
            cr.rowcount)


def migrate(cr, _version):
    _migrate_role_color(cr)
    _migrate_attendance_template_color(cr)
    _rename_old_status_columns(cr)
    _rename_old_special_columns(cr)
    _dedupe_ems_enrollment(cr)
