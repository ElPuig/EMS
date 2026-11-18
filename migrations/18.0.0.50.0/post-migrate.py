import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# The staff criteria whose points changed on 2026-11-18 (adriamt: favour job shadowings and teaching
# over courses): the mobility plan gained the activity of proposal A (max 3), and the last staff
# mobility and the centre projects went down to max 1.
STAFF_SCORE_FIELDS = ('score_plan', 'score_last_mobility', 'score_projects', 'score_total', 'score_complete',
                      'is_eligible')


def _drop_stale_plan_score_translations(cr):
    """The rating's "Score (max 2)" became "Score (max 3)". The upgrade writes the new English
    label, but loads the .po files without overwriting existing values, so the Catalan and Spanish
    labels kept "max. 2". Dropping those two keys here (post-migrate runs before the translations
    load) lets the .po fill them in again."""
    cr.execute("""
        UPDATE ir_model_fields
           SET field_description = field_description - 'ca_ES' - 'es_ES'
         WHERE model = 'ems.erasmus.plan_rating' AND name = 'score'
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.50.0: reset the translations of the plan rating's score.")


def _recompute_staff_scores(env):
    """The stored staff scores were computed with the old maximums: recompute them. The lines of a
    published resolution are a frozen copy and keep what was published."""
    applications = env['ems.erasmus.application'].with_context(active_test=False).search(
        [('call_id.audience', '=', 'staff')])
    if not applications:
        return
    for name in STAFF_SCORE_FIELDS:
        env.add_to_compute(applications._fields[name], applications)
    applications.flush_recordset()
    _logger.info("Migration 18.0.0.50.0: recomputed the scores of %s staff applications.", len(applications))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _drop_stale_plan_score_translations(cr)
    _recompute_staff_scores(env)
