import logging

_logger = logging.getLogger(__name__)


def _mark_reported_attendance_issues(cr):
    """Issue #527: the tutor's attendance issues report now carries every issue not reported yet
    ('ems.attendance_issue_status.tutor_notified', new in this version, hence post-migrate).
    Everything recorded before this version counts as reported, except the issues whose day's
    report job has not run yet: otherwise the first report after the upgrade would list the whole
    course again (failed or cancelled reports included)."""
    cr.execute("""
        UPDATE ems_attendance_issue_status status
           SET tutor_notified = TRUE
          FROM ems_attendance_issue_student student
          JOIN ems_attendance_issue_tutor tutor ON tutor.id = student.attendance_issue_tutor_id
     LEFT JOIN queue_job job ON job.id = tutor.notification_id
         WHERE status.attendance_issue_student_id = student.id
           AND (job.id IS NULL OR job.state NOT IN ('wait_dependencies', 'pending', 'enqueued', 'started'))
    """)
    _logger.info("Attendance issues already reported to the tutor: %d.", cr.rowcount)


def migrate(cr, version):
    _mark_reported_attendance_issues(cr)
