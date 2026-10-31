# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _carry_over_summary_moment(cr)
    _cancel_pending_tutor_reports(cr)


def _carry_over_summary_moment(cr):
    """Issue #644: the tutor's attendance issues report and the pending-tasks digest became one
    daily summary, with one moment for everybody (res.users.ems_digest_moment/_time). The new
    columns are created here, before Odoo would create them with its default, and take the old
    report preference: 'teacher_end' was its default and can't be told apart from a deliberate
    choice, so it becomes the new default (the start of the working day); any other value was
    chosen by the user and is kept. Raw SQL on columns that already existed, so pre-migrate."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'res_users' AND column_name = 'ems_attendance_report_moment'
    """)
    if not cr.fetchone():
        return
    cr.execute("ALTER TABLE res_users ADD COLUMN IF NOT EXISTS ems_digest_moment VARCHAR")
    cr.execute("ALTER TABLE res_users ADD COLUMN IF NOT EXISTS ems_digest_time DOUBLE PRECISION")
    cr.execute("""
        UPDATE res_users
           SET ems_digest_moment = CASE
                   WHEN ems_attendance_report_moment IS NULL OR ems_attendance_report_moment = 'teacher_end'
                   THEN 'teacher_start' ELSE ems_attendance_report_moment END,
               ems_digest_time = ems_attendance_report_time
    """)
    cr.execute("SELECT count(*) FROM res_users WHERE ems_digest_moment != 'teacher_start'")
    _logger.info("Migration #644: daily summary moment carried over; %d user(s) keep a moment of their own.",
                 cr.fetchone()[0])


def _cancel_pending_tutor_reports(cr):
    """The tutor's report is no longer a queue job per tutor: the daily summary's scheduled
    action sends it. A job still pending would call a method that no longer exists; cancelled,
    its issues are still unreported (tutor_notified = False), so they go in the next summary."""
    cr.execute("""
        UPDATE queue_job SET state = 'cancelled'
         WHERE model_name = 'ems.attendance_issue_tutor'
           AND method_name IN ('_send_tutor_report', 'send_notification')
           AND state NOT IN ('done', 'cancelled', 'failed')
    """)
    if cr.rowcount:
        _logger.info("Migration #644: cancelled %d pending tutor report job(s).", cr.rowcount)
