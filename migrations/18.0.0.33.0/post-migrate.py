import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def _drop_non_students_from_rosters(env, lines):
    """A few rosters carried partners that aren't students at all (e.g. Odoo's own archived
    'Default User Template', base.default_user_res_partner), added by hand through the many2many
    widget."""
    dropped = 0
    # active_test=False: such a partner is usually archived, and a plain read of the roster hides it.
    for line in lines.with_context(active_test=False):
        intruders = line.student_ids.filtered(lambda partner: partner.contact_type != 'student')
        if intruders:
            line.student_ids = [(3, partner.id) for partner in intruders]
            dropped += len(intruders)
    _logger.info("Issue #534: removed %d non-student entries from attendance rosters.", dropped)


def _custom_schedules_from_hand_edited_rosters(env, lines):
    """Issue #534: a session's roster can no longer be edited by hand - it follows the enrollments,
    custom schedules (ems.enrollment.slot) included. Every hand edit still in place becomes the
    equivalent custom schedule, so nobody's attendance changes with the upgrade: a student taken
    out of every session of a subject becomes 'not in person', and one moved between groups gets
    slots for exactly the sessions they are in now."""
    Enrollment = env['ems.enrollment']
    Slot = env['ems.enrollment.slot']
    actual = defaultdict(lambda: env['ems.attendance_schedule'])
    expected = defaultdict(lambda: env['ems.attendance_schedule'])
    for line in lines:
        subject = line.attendance_template_id.subject_id
        for student in line.student_ids:
            actual[(student, subject)] |= line
        for student in line._ems_expected_students():
            expected[(student, subject)] |= line

    converted, skipped = 0, 0
    for student, subject in set(actual) | set(expected):
        attended = actual[(student, subject)]
        if attended == expected[(student, subject)]:
            continue
        enrollment = Enrollment.search([('student_id', '=', student.id), ('subject_id', '=', subject.id)])
        if len(enrollment) != 1:
            _logger.warning("Issue #534: left as is, %s in %s's sessions has %d enrollments in it (review by hand).",
                            subject.display_name, student.display_name, len(enrollment))
            skipped += 1
            continue
        try:
            with env.cr.savepoint():
                if attended:
                    seen = set()
                    vals_list = []
                    for line in attended:
                        vals = {'enrollment_id': enrollment.id, 'attendance_schedule_id': line.id,
                                'group_id': Slot._ems_group_of(line, enrollment.group_id).id}
                        key = (vals['group_id'], line.weekday, line.start_time, line.end_time)
                        if key not in seen:
                            seen.add(key)
                            vals_list.append(vals)
                    Slot.create(vals_list)
                else:
                    enrollment.is_remote = True
                student.custom_schedule = True
            converted += 1
        except ValidationError as error:
            _logger.warning("Issue #534: left as is, %s's hand-edited sessions of %s can't be a custom schedule: %s",
                            student.display_name, subject.display_name, error)
            skipped += 1
    _logger.info("Issue #534: %d hand-edited rosters turned into custom schedules, %d left as is.", converted, skipped)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {'active_test': True})
    lines = env['ems.attendance_schedule'].search([('attendance_template_id.active', '=', True)])
    _drop_non_students_from_rosters(env, lines)
    _custom_schedules_from_hand_edited_rosters(env, lines)
