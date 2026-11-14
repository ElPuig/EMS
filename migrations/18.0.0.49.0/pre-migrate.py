# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


# Inheriting views whose stored arch (the previous version's) uses a field that this version
# removes. Odoo validates the whole tree of a parent view when it reloads it, before the data file
# that holds the child reloads, so the stale child makes the parent fail ("Field ... does not exist
# in model"). They are dropped before the data files reload and recreated from the new files.
STALE_CHILD_VIEWS = (
    'view_erasmus_project_form_economy',  # economy_document_ids left the project (issue #784)
)


def migrate(cr, version):
    _drop_stale_child_views(cr)
    _rename_walkout_justification_reason(cr)


def _drop_stale_child_views(cr):
    """Drops the EMS views of STALE_CHILD_VIEWS (and what inherits them) so the data files recreate
    them with the new arch. A clean install has none of them: nothing to do."""
    cr.execute("""
        WITH RECURSIVE tree AS (
            SELECT v.id FROM ir_ui_view v
              JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id AND d.module = 'ems'
             WHERE d.name IN %s
            UNION
            SELECT c.id FROM ir_ui_view c JOIN tree t ON c.inherit_id = t.id
        )
        SELECT id FROM tree
    """, [STALE_CHILD_VIEWS])
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        return
    cr.execute("DELETE FROM ir_ui_view WHERE id IN %s", [tuple(ids)])
    cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id IN %s", [tuple(ids)])
    _logger.info("Migration: dropped %s stale inheriting view(s) before the data files reload.", len(ids))


def _rename_walkout_justification_reason(cr):
    """Issue #800: the justification reason "Labour strike" is the student walkout's: its xmlid
    becomes attendance_justification_reason_walkout (before the data files reload, which reference
    the new one) and its English name "Student walkout", so that "strike" only means the
    disciplinary record (ems.strike). The record is noupdate, so the file cannot rename it: only
    while the English name is still the seeded one (a centre that renamed it keeps its name). The
    Catalan and Spanish names do not change."""
    cr.execute("""
        UPDATE ir_model_data SET name = 'attendance_justification_reason_walkout'
         WHERE module = 'ems' AND name = 'attendance_justification_reason_strike'
        RETURNING res_id
    """)
    row = cr.fetchone()
    if not row:
        return
    cr.execute("""
        UPDATE ems_attendance_justification_reason
           SET name = jsonb_set(name, '{en_US}', '"Student walkout"')
         WHERE id = %s AND name->>'en_US' = 'Labour strike'
    """, [row[0]])
    _logger.info("Migration #800: justification reason renamed to Student walkout.")
