import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _migrate_absence_document_state(env):
    """Issue #536: the supporting document is now the Head's step, between acknowledging a request
    and validating it, instead of a state of Direction's own check. Post-migrate: the
    'ems_document_state' column is new in this version.

    - Every request the Head had already approved counts as validated by them: the Head's
      approval meant exactly that until now.
    - Direction's former "Missing document" becomes "Awaiting documentation": the request goes back
      to the employee, and Direction's own check back to pending.
    Then the two stored status columns are recomputed (they depend on the new column, which does
    not recompute existing rows on its own), and the employee gets the activity asking for the
    document on the requests now awaiting it."""
    env.cr.execute("""
        UPDATE hr_leave
           SET ems_document_state = CASE WHEN ems_direction_state = 'missing_doc'
                                         THEN 'awaiting' ELSE 'validated' END
         WHERE state IN ('validate', 'validate1') AND ems_document_state IS NULL
    """)
    env.cr.execute("""
        UPDATE hr_leave SET ems_direction_state = 'not_done' WHERE ems_direction_state = 'missing_doc'
    """)
    leaves = env['hr.leave'].with_context(active_test=False).search([])
    for field_name in ('ems_head_state', 'ems_status'):
        env.add_to_compute(leaves._fields[field_name], leaves)
    leaves.flush_recordset(['ems_head_state', 'ems_status'])
    awaiting = leaves.filtered(lambda leave: leave.ems_status == 'pending_document')
    awaiting._ems_update_activities()
    _logger.info("Migration 18.0.0.31.0: recomputed the status of %s absences, %s now awaiting "
                 "their supporting document.", len(leaves), len(awaiting))


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_absence_document_state(env)
