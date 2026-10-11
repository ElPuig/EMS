import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# xmlid (module '__import__') -> (name it had, corrected name)
_SUBJECT_RENAMES = {
    'subject_175_2022_FIQ2': ("Física i Química (1r)", "Física i Química (2n)"),
    'subject_175_2022_FIQ3': ("Física i Química (2n)", "Física i Química (3r)"),
    'subject_175_2022_FIQ4': ("Física i Química (3r)", "Física i Química (4t)"),
    'subject_175_2022_ROB3': ("Robòtica (2n)", "Robòtica (3r)"),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _revoke_stale_attendance_admin(env)
    _archive_past_courses_attendance(env)
    _rename_eso_subjects(env)


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


def _rename_eso_subjects(env):
    """These ESO subjects were named one course too low. This version's pre-migrate freezes every
    data/custom/ record, so the corrected names in data/custom/eso/ems.subject.csv no longer
    reach an existing installation by themselves. Through the ORM, so the subject's product is
    renamed with it; a subject already renamed through the app is left alone."""
    for xmlid, (old_name, new_name) in _SUBJECT_RENAMES.items():
        subject = env.ref(f'__import__.{xmlid}', raise_if_not_found=False)
        if subject and subject.name == old_name:
            subject.name = new_name
            _logger.info("Migration 18.0.0.36.0: subject %s renamed to '%s'.", subject.code, new_name)
