import logging

_logger = logging.getLogger(__name__)

# The columns of the single change a timetable-change notice used to carry before issue #652.
OLD_COLUMNS = ('absence_change_type', 'absence_change_hour', 'absence_change_hour_to')


def migrate(cr, version):
    _move_absence_changes_to_list(cr)


def _move_absence_changes_to_list(cr):
    """Issue #652: a timetable-change notice (ems.notice sent from the guard duty board) can now
    tell several changes at once, kept in the 'absence_changes' JSON list - one [change type,
    hour] (or, for a break, [change type, hour from, hour to]) per change - instead of its single
    change's own three columns. Each existing notice gets its change as a one-item list, so the
    board keeps reading what was communicated. post-migrate: 'absence_changes' is new in this
    version. The old columns are left in place (Odoo never drops a removed field's column), only
    no longer read. A clean install has no such notice: nothing to do there."""
    cr.execute("""
        SELECT COUNT(*) FROM information_schema.columns
         WHERE table_name = 'ems_notice' AND column_name IN %s
    """, (OLD_COLUMNS,))
    if cr.fetchone()[0] != len(OLD_COLUMNS):
        return
    cr.execute("""
        UPDATE ems_notice
           SET absence_changes = CASE
                   WHEN absence_change_type IN ('long_break', 'normal_break')
                       THEN jsonb_build_array(jsonb_build_array(
                           absence_change_type, COALESCE(absence_change_hour, 0), COALESCE(absence_change_hour_to, 0)))
                   ELSE jsonb_build_array(jsonb_build_array(absence_change_type, COALESCE(absence_change_hour, 0)))
               END
         WHERE absence_change_type IS NOT NULL AND absence_changes IS NULL
    """)
    _logger.info("Issue #652: timetable change of %s notice(s) moved to their list of changes", cr.rowcount)
