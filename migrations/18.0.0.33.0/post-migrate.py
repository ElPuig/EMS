import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError

from odoo.addons.ems import _disable_login_presence_control, _fix_native_presence_translations

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


def _align_user_names_with_employees(env):
    """Issue #542: a name fixed on the employee form never reached its EMS user (native hr only
    syncs user -> employee), nor its Google account. Give every user whose name drifted the
    employee's name, which is the one the centre maintains, and queue the same fix for the
    Google account. post-migrate: goes through the ORM (see CLAUDE.md, Migrations)."""
    employees = env['hr.employee'].with_context(active_test=False).search([('user_id', '!=', False)])
    renamed = employees.filtered(lambda employee: employee.user_id.name != employee.name)
    for employee in renamed:
        _logger.info("EMS user %s renamed from %r to %r.",
                     employee.user_id.login, employee.user_id.name, employee.name)
    renamed._sync_user_name()
    renamed._gw_enqueue_rename()


# (model, many2many relation table, its column pointing at the model)
ATTACHMENT_RELATIONS = [
    ('ems.attendance_justification', 'ems_attendance_justification_ir_attachment_rel', 'ems_attendance_justification_id'),
    ('ems.study', 'ems_study_ir_attachment_rel', 'ems_study_id'),
]


def _link_attachments(cr):
    """Issue #553: the files attached to an attendance justification or a study were stored
    without a res_id, so Odoo only let their uploader (or a system admin) read them. Ties each
    one to its record, the same way both models' create()/write() now do; a file shared by
    several records goes to the first one."""
    for model, relation, column in ATTACHMENT_RELATIONS:
        cr.execute(f"""
            UPDATE ir_attachment attachment
               SET res_model = %s, res_id = rel.record_id
              FROM (SELECT ir_attachment_id, MIN({column}) AS record_id
                      FROM {relation}
                  GROUP BY ir_attachment_id) rel
             WHERE rel.ir_attachment_id = attachment.id
               AND COALESCE(attachment.res_id, 0) = 0
        """, [model])
        _logger.info("%s attachments linked to their record: %d.", model, cr.rowcount)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {'active_test': True})
    lines = env['ems.attendance_schedule'].search([('attendance_template_id.active', '=', True)])
    _drop_non_students_from_rosters(env, lines)
    _custom_schedules_from_hand_edited_rosters(env, lines)
    _align_user_names_with_employees(api.Environment(cr, SUPERUSER_ID, {}))
    _link_attachments(cr)
    # Issue #555: the presence dot follows the attendance check-in/out only, never whether someone
    # has EMS open in a browser. Fresh installs get the same from post_init_hook.
    env = api.Environment(cr, SUPERUSER_ID, {})
    _disable_login_presence_control(env)
    _logger.info("Migration 18.0.0.33.0: disabled login-based presence control for every company.")
    _fix_native_presence_translations(env)
    _logger.info("Migration 18.0.0.33.0: fixed the presence dot's missing/wrong ca_ES/es_ES labels.")
