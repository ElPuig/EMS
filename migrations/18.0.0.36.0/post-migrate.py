import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _revoke_stale_attendance_admin(env)
    _archive_past_courses_attendance(env)


def _revoke_stale_attendance_admin(env):
    """Issue #543: the Head of Studies' group no longer implies hr_attendance's Administrator one
    (they see their own branch's attendance, not the whole centre's), but the users who already
    held it through that implication keep it until it is taken away explicitly."""
    logins = env['res.users']._ems_revoke_stale_attendance_admin()
    _logger.info("Issue #543: hr_attendance Administrator group revoked from %s Head(s) of Studies: %s",
                 len(logins), ", ".join(logins) or "-")


def _archive_past_courses_attendance(env):
    """Issue #543: from now on a course transition archives the staff's attendance of the course
    left behind (hr.attendance._ems_archive_before_course). This catches up with the courses
    already over: everything before the current course started. A database with no current course
    yet has nothing to archive against. A clean install needs neither step: it has no attendance
    and no user holding a group through the old implication."""
    course = env.company.current_course_id
    if not course:
        return
    archived = env['hr.attendance']._ems_archive_before_course(course)
    _logger.info("Issue #543: %s attendance record(s) from before course %s archived.", archived, course.name)
