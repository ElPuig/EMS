# -*- coding: utf-8 -*-
"""Shared test utilities - see docs/en/developers/shared/testing.md for the rationale
(extracted after the DTON rollout found the same fixture/mock boilerplate hand-written
identically across dozens of test files)."""

import base64
import itertools
from unittest.mock import patch


_test_student_id_sequence = itertools.count(1)


def next_student_id():
    """A fresh Student ID (IDALU) for a test fixture student (issue #460).

    Every student-lifecycle contact needs one to be created, and it must be unique across the
    whole database, archived contacts included. The 'TEST' prefix can never match a real IDALU
    (digits only), so a fixture never collides with the development data test shards clone."""
    return f"TEST{next(_test_student_id_sequence):06d}"


def create_level_study(cls, prefix, **overrides):
    """Creates a level+study pair with `prefix`-derived unique codes.
    overrides: optional 'level'/'study' sub-dicts to override any field."""
    level = cls.env['ems.level'].create({
        'acronym': prefix, 'name': f'Test {prefix} Level', **overrides.get('level', {}),
    })
    study = cls.env['ems.study'].create({
        'code': f'{prefix}-01', 'acronym': prefix, 'name': f'Test {prefix} Study',
        'date': '2026-01-01', 'deprecated': False, 'level_id': level.id,
        **overrides.get('study', {}),
    })
    return level, study


def create_level_study_group(cls, prefix, **overrides):
    """Creates a level+study+group triple with `prefix`-derived unique codes.
    overrides: optional 'level'/'study'/'group' sub-dicts to override any field."""
    level, study = create_level_study(cls, prefix, level=overrides.get('level', {}), study=overrides.get('study', {}))
    group = cls.env['ems.group'].create({
        'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
        **overrides.get('group', {}),
    })
    return level, study, group


def mock_outgoing_email(cls):
    """Neutralizes real SMTP delivery for the duration of the test class - see CLAUDE.md's
    'Email safety in tests'. Call once from setUpClass. Returns the mock (e.g. to later assert
    on call count with cls.mail_transport.assert_not_called() / .reset_mock())."""
    patcher = patch(
        'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
        return_value='test-message-id',
    )
    mock = patcher.start()
    cls.addClassCleanup(patcher.stop)
    return mock


def force_user_language_to_english(test, user):
    """Force `user`'s language to en_US for the duration of the current test only, restored
    via test.addCleanup() (on top of the test's own transaction rollback, for clarity since
    this mutates a real, pre-existing user rather than one created fresh in the test).

    Required by any tour/HttpCase test that logs in as a real, pre-existing account (e.g.
    base.user_admin, login="admin") and asserts on literal English button/field text - this
    box's real accounts are not guaranteed to have lang='en_US' (this dev DB's admin is
    'es_ES'), and a freshly created res.users record without an explicit 'lang' key isn't
    guaranteed en_US either (confirmed on this box: defaults to 'ca_ES'). See CLAUDE.md's
    "Tour tests and language" testing convention."""
    original_lang = user.lang
    user.lang = 'en_US'
    test.addCleanup(lambda: user.write({'lang': original_lang}))


def make_synchronous_run_in_thread(record):
    """A run_in_thread() replacement that runs setup/compute/store/callback synchronously
    against `record`, for tests that need run_action()'s wiring without real threading or a
    real LimesurveyApi call. Use as: patch.object(type(record), 'run_in_thread',
    side_effect=make_synchronous_run_in_thread(record), autospec=True)."""
    def fake_run_in_thread(self_record, setup, compute, store, callback, *args, **kwargs):
        setup(record)
        compute()
        store(record)
        callback(record)
    return fake_run_in_thread


# Maps a short role name to its ems.group_* xmlid - see security/groups.xml and
# docs/en/developers/employees/role_hierarchy.md for the full implication chain. Used by
# create_role_user() so tours/tests can log in as any EMS role without repeating xmlids.
ROLE_GROUP_XMLIDS = {
    'teacher': 'ems.group_teacher',
    'tutor': 'ems.group_tutor',
    'department_chief': 'ems.group_department_chief',
    'head_of_studies': 'ems.group_head_of_studies',
    'director': 'ems.group_director',
    'academic_admin': 'ems.group_academic_admin',
    'secretary': 'ems.group_secretary',
    'secretary_admin': 'ems.group_secretary_admin',
    'quality': 'ems.group_quality',
    'quality_admin': 'ems.group_quality_admin',
    'coexistence': 'ems.group_coexistence',
    'coexistence_admin': 'ems.group_coexistence_admin',
    'tac': 'ems.group_tac',
    'tac_admin': 'ems.group_tac_admin',
    'orientation': 'ems.group_orientation',
    'orientation_admin': 'ems.group_orientation_admin',
    'settings': 'ems.group_settings',
    'settings_admin': 'ems.group_settings_admin',
}


def create_role_user(cls, role, login, **overrides):
    """Creates a res.users with `role`'s group (see ROLE_GROUP_XMLIDS) plus base.group_user.

    'lang' is set to 'en_US' at creation - required by any tour asserting on English labels,
    since a freshly created res.users does not reliably default to en_US (see CLAUDE.md's "Tour
    tests and language"). `login` doubles as the password, matching start_tour()'s own
    convention. Extracted after the same ~15-line res.users.create() block was hand-written in
    9+ tour test files (e.g. test_student_data_reader_tour.py, test_employee_teacher_kanban_tour.py).

    overrides: any res.users field to override/add (e.g. 'name', 'email')."""
    vals = {
        'name': overrides.pop('name', f'Test {role.replace("_", " ").title()} User'),
        'login': login,
        'password': login,
        'lang': 'en_US',
        'groups_id': [
            (4, cls.env.ref('base.group_user').id),
            (4, cls.env.ref(ROLE_GROUP_XMLIDS[role]).id),
        ],
        **overrides,
    }
    return cls.env['res.users'].with_context(no_reset_password=True).create(vals)


def create_role_employee(cls, user, employee_type='teacher', **overrides):
    """Creates an hr.employee linked to `user`.

    `employee_type` defaults to 'teacher' since most EMS roles that need a paired employee
    (teacher, tutor, orientation, coexistence, tac - all imply ems.group_teacher) are teaching
    roles; pass employee_type='asp' for secretary/settings/quality-style roles. The '0000 '
    name prefix sorts first among the pre-existing teachers in this dev DB's list views, same
    trick used across the existing employee tours (e.g. test_employee_teacher_kanban_tour.py).

    overrides: any hr.employee field to override/add."""
    vals = {
        'name': overrides.pop('name', f'0000 {user.name}'),
        'employee_type': employee_type,
        'user_id': user.id,
        **overrides,
    }
    return cls.env['hr.employee'].create(vals)


def create_student_academic_file(cls, prefix, group, course=None, student=None):
    """Seeds the data the student form's Secretary and Academic history tabs render.

    An EMS enrolment is a `sale.order`, and the Secretary tab's authorizations are resolved
    from it by `res.partner._ems_enrollment_in_force()` - which reads the *running* course, so
    the enrolment has to hang off that one to be found. Returns a dict with every record, so a
    test can assert on any of them.

    Extracted after issue #393 needed the exact same fixture in a TransactionCase and in a tour.
    """
    Course = cls.env['ems.course']
    # Mirrors _ems_enrollment_in_force()'s own two-tier fallback exactly (is_current, then
    # is_enrollment_default) - a plain "first course found" fallback picked whichever course
    # sorts first under ems.course's own _order ('start desc', the LATEST one), which silently
    # never matches what that method falls back to (is_enrollment_default, seeded onto the
    # EARLIEST course when no course is current - see _ems_seed_enrollment_default) on a fresh
    # install with no current course configured. Found 2026-09-09 via CI: this enrolment's own
    # course never matched the one the Secretary tab's lookup resolved to, so it rendered empty
    # on a clean install despite passing on a dev database that already had a current course.
    course = course or Course.search([('is_current', '=', True)], limit=1) \
        or Course.search([('is_enrollment_default', '=', True)], limit=1) \
        or Course.create({'start': 2098, 'end': 2099})

    student = student or cls.env['res.partner'].create({
        'name': f'Test {prefix} Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'student_email': f'test_{prefix.lower()}_student@example.com',
        'main_group_id': group.id,
    })

    order = cls.env['sale.order'].create({
        'partner_id': student.id, 'ems_study_id': group.study_id.id, 'ems_course_id': course.id,
    })
    # Creating the template applies it to every matching draft enrolment, which is what
    # produces the ems.authorization record the Secretary tab lists.
    template = cls.env['ems.authorization.template'].create({
        'name': f'Test {prefix} Image Rights', 'legal_text': '<p>Text</p>', 'auth_type': 'image',
    })
    authorization = order.ems_authorization_ids.filtered(
        lambda auth: auth.template_id == template)
    # Signing needs the PDF in the same write - see ems.authorization.write().
    authorization.write({'status': 'yes',
                         'signed_document': base64.b64encode(b'%PDF-1.4 test'),
                         'signed_document_name': 'signed.pdf'})

    benefit = cls.env['ems.student.benefit'].create({
        'student_id': student.id, 'benefit_type': 'scholarship',
        'document': base64.b64encode(b'%PDF-1.4 test'), 'document_name': 'test.pdf',
    })
    year_record = cls.env['ems.student.year_record'].create({
        'student_id': student.id, 'course_id': course.id,
    })
    return {'student': student, 'course': course, 'order': order, 'auth_template': template,
            'authorization': authorization, 'benefit': benefit, 'year_record': year_record}
