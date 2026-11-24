# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _cancel_orphan_notification_jobs(cr)


def _cancel_orphan_notification_jobs(cr):
    """Issue #816: a family notification whose attendance issue was deleted (by the database
    cascade, which never cancelled its job) ended as a failed job with "Record does not exist".
    There is nothing left to send, so cancel the ones already failed. Only those whose record is
    really gone; a job failed for any other reason stays as it is."""
    cr.execute("""
        UPDATE queue_job job
           SET state = 'cancelled', date_cancelled = now() AT TIME ZONE 'UTC',
               exc_info = NULL, result = 'Cancelled: its attendance issue no longer exists (issue #816).'
         WHERE job.model_name = 'ems.attendance_issue_status'
           AND job.method_name = 'send_notification'
           AND job.state = 'failed'
           AND NOT EXISTS (
               SELECT 1 FROM ems_attendance_issue_status status
                WHERE status.id = (job.records::json->'ids'->>0)::int)
    """)
    _logger.info("Cancelled %s failed notification job(s) of deleted attendance issues", cr.rowcount)
