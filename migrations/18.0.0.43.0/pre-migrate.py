import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _drop_convalidation_notice_activities(cr)


def _drop_convalidation_notice_activities(cr):
    """Issue #733: a completed convalidation tells the subject's teachers and the group's tutor
    with a notice instead of an activity, so the activity type goes. Its open activities are
    removed first, without marking them as done (that would post a message on each student): only
    then can Odoo delete the type, which is no longer in the data files. Raw SQL, so pre-migrate.
    A clean install never creates the type, so it needs no post_init_hook counterpart."""
    cr.execute("""
        DELETE FROM mail_activity
         WHERE activity_type_id IN (SELECT res_id FROM ir_model_data
                                     WHERE module = 'ems' AND model = 'mail.activity.type'
                                       AND name = 'mail_activity_convalidation_notice')
    """)
    if cr.rowcount:
        _logger.info("Removed %s open convalidated-subject activities", cr.rowcount)
