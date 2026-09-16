from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study, next_student_id


class TestEnrollment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TENR', level={'name': 'Test Level (Enrollment)'}, study={
            'code': 'TENR001', 'name': 'Test Study (Enrollment)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TENR001',
            'acronym': 'TENR',
            'name': 'Test Subject (Enrollment)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'TENR001_01RA', 'acronym': 'RA1', 'name': 'Outcome 1', 'subject_id': cls.subject.id,
        })
        cls.planning = cls.env['ems.planning'].create({
            'study_id': cls.study.id,
            'subject_id': cls.subject.id,
            'internal_ponderation': 100.0,
            'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome.id, 'ponderation': 100.0})],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TENR-A',
            'name': 'Test Space (Enrollment)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Enrollment)',
            'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({'name': 'Test Student (Enrollment)', 'contact_type': 'student', 'student_id': next_student_id()})
        cls.other_student = cls.env['res.partner'].create({'name': 'Test Student B (Enrollment)', 'contact_type': 'student', 'student_id': next_student_id()})

    def _create_template(self, groups, weekday='0'):
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, groups)],
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 6, 30),
        })
        # student_ids lives on the schedule line, not the template (see
        # plans/calendar_driven_attendance_templates.md, point 1) - the enrollment sync hooks
        # this test file exercises need a real line to write onto.
        self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': weekday, 'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
        })
        return template

    def _create_session(self, group=None, round_no="1"):
        return self.env['ems.grade_session'].create({
            'group_id': (group or self.group).id,
            'subject_id': self.subject.id,
            'round': round_no,
            'teacher_id': self.teacher.id,
        })

    def _create_enrollment(self, student=None, group=None):
        return self.env['ems.enrollment'].create({
            'student_id': (student or self.student).id,
            'group_id': (group or self.group).id,
            'subject_id': self.subject.id,
        })

    # -- attendance_template sync --

    def test_create_enrollment_adds_student_to_matching_template(self):
        template = self._create_template([self.group.id])
        self._create_enrollment()
        self.assertIn(self.student, template.attendance_schedule_ids.student_ids)

    def test_create_enrollment_without_matching_template_is_noop(self):
        enrollment = self._create_enrollment()
        self.assertTrue(enrollment.id)

    def test_delete_enrollment_removes_student_from_template(self):
        template = self._create_template([self.group.id])
        enrollment = self._create_enrollment()
        self.assertIn(self.student, template.attendance_schedule_ids.student_ids)

        enrollment.unlink()

        self.assertNotIn(self.student, template.attendance_schedule_ids.student_ids)

    def test_delete_enrollment_keeps_student_if_still_covered_by_same_template(self):
        # Template covers both groups (co-teaching); the student is enrolled through both.
        template = self._create_template([self.group.id, self.other_group.id])
        enrollment = self._create_enrollment(group=self.group)
        self._create_enrollment(group=self.other_group)
        self.assertIn(self.student, template.attendance_schedule_ids.student_ids)

        enrollment.unlink()

        self.assertIn(self.student, template.attendance_schedule_ids.student_ids)

    # -- grade_session sync --

    def test_create_enrollment_adds_student_lines_to_open_session(self):
        session = self._create_session()

        self._create_enrollment(student=self.student)

        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertEqual(len(lines), 1)
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertEqual(len(subject_line), 1)

    def test_create_enrollment_does_not_touch_other_students_lines(self):
        session = self._create_session()
        self._create_enrollment(student=self.other_student)
        other_lines_before = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.other_student)
        other_lines_before.write({'score': 7, 'is_scored': True})

        self._create_enrollment(student=self.student)

        other_lines_after = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.other_student)
        self.assertEqual(other_lines_after.score, 7)
        self.assertTrue(other_lines_after.is_scored)

    def test_create_enrollment_ignores_board_or_final_session(self):
        session = self._create_session()
        session.write({'state': 'final'})
        self._create_enrollment()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertFalse(lines)

    def test_delete_enrollment_without_grades_removes_session_lines(self):
        session = self._create_session()
        enrollment = self._create_enrollment()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertTrue(lines)

        enrollment.unlink()

        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertFalse(lines)

    def test_delete_enrollment_with_scored_grades_raises(self):
        session = self._create_session()
        enrollment = self._create_enrollment()
        line = session.grade_outcome_line_ids.filtered(lambda l: l.student_id == self.student)
        line.write({'score': 8, 'is_scored': True})

        with self.assertRaises(UserError):
            enrollment.unlink()

        self.assertTrue(enrollment.exists())

    def test_delete_enrollment_with_scored_grades_does_not_touch_attendance_template(self):
        template = self._create_template([self.group.id])
        session = self._create_session()
        enrollment = self._create_enrollment()
        line = session.grade_outcome_line_ids.filtered(lambda l: l.student_id == self.student)
        line.write({'score': 8, 'is_scored': True})

        with self.assertRaises(UserError):
            enrollment.unlink()

        self.assertIn(self.student, template.attendance_schedule_ids.student_ids)

    def test_delete_enrollment_ignores_board_or_final_session_lines(self):
        session = self._create_session()
        enrollment = self._create_enrollment()
        session.write({'state': 'final'})

        enrollment.unlink()

        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertTrue(lines)

    def test_sync_grade_session_remove_keeps_lines_if_still_enrolled(self):
        # _ems_sync_grade_session_remove() is keyed by (student_id, group_id, subject_id),
        # not by the deleted row's own id - unlike its sibling
        # _ems_sync_attendance_template_remove(), it used to have no guard against a
        # still-enrolled student (see plans/grade_session_remove_missing_still_enrolled_guard.md).
        # The unique(student_id, group_id, subject_id) constraint on ems.enrollment now makes
        # the real trigger (a duplicate row for the exact same triple) unreachable via the
        # ORM, so this calls the sync method directly rather than through unlink() - a
        # white-box test of the guard itself, added for defensive symmetry with the
        # attendance-template sibling and to protect any future caller of this method.
        session = self._create_session()
        enrollment = self._create_enrollment()
        lines_before = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertTrue(lines_before)

        self.env['ems.enrollment']._ems_sync_grade_session_remove(
            self.student.id, self.group.id, self.subject.id)

        lines_after = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student)
        self.assertEqual(lines_before, lines_after)
        self.assertTrue(enrollment.exists())

    # -- _ems_still_enrolled (shared by both unlink() sync hooks above) --------------

    def test_still_enrolled_true_when_a_matching_row_exists(self):
        self._create_enrollment()
        self.assertTrue(self.env['ems.enrollment']._ems_still_enrolled(
            self.student.id, self.subject.id, [self.group.id]))

    def test_still_enrolled_false_without_a_matching_row(self):
        self.assertFalse(self.env['ems.enrollment']._ems_still_enrolled(
            self.student.id, self.subject.id, [self.group.id]))

    def test_still_enrolled_checks_any_of_several_groups(self):
        self._create_enrollment(group=self.other_group)
        self.assertTrue(self.env['ems.enrollment']._ems_still_enrolled(
            self.student.id, self.subject.id, [self.group.id, self.other_group.id]))

    # -- default_get admin guard --

    def test_default_get_blocks_non_admin(self):
        teacher_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Non-Admin (Enrollment)', 'login': 'test_non_admin_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_teacher').id)],
        })
        with self.assertRaises(UserError):
            self.env['ems.enrollment'].with_user(teacher_user).default_get(['user_is_admin'])

    def test_default_get_allows_admin(self):
        admin_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Enrollment)', 'login': 'test_admin_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_academic_admin').id)],
        })
        res = self.env['ems.enrollment'].with_user(admin_user).default_get(['user_is_admin'])
        self.assertTrue(res['user_is_admin'])

    def test_default_get_allows_secretary(self):
        secretary_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Enrollment)', 'login': 'test_secretary_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_secretary').id)],
        })
        # Must not raise UserError, unlike a plain teacher (test_default_get_blocks_non_admin).
        self.env['ems.enrollment'].with_user(secretary_user).default_get(['user_is_admin'])

    def test_default_get_allows_head_of_studies(self):
        hos_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Head of Studies (Enrollment)', 'login': 'test_hos_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_head_of_studies').id)],
        })
        # Must not raise UserError, unlike a plain teacher (test_default_get_blocks_non_admin).
        self.env['ems.enrollment'].with_user(hos_user).default_get(['user_is_admin'])

    def test_default_get_blocks_non_admin_message_is_translated(self):
        # Verifies the .po translation actually loaded and applies at runtime - a msgid
        # existing in the .po file is necessary but not sufficient (see CLAUDE.md's i18n
        # verification rule).
        teacher_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Non-Admin ES (Enrollment)', 'login': 'test_non_admin_enrollment_es',
            'groups_id': [(4, self.env.ref('ems.group_teacher').id)],
        })
        with self.assertRaises(UserError) as cm:
            self.env['ems.enrollment'].with_user(teacher_user).with_context(lang='es_ES').default_get(['user_is_admin'])
        self.assertIn('Solo los administradores, el personal de secretaría y la Jefatura de Estudios', str(cm.exception))

    def test_secretary_can_create_enrollment_manually(self):
        secretary_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary Create (Enrollment)', 'login': 'test_secretary_create_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_secretary').id)],
        })
        enrollment = self.env['ems.enrollment'].with_user(secretary_user).create({
            'student_id': self.other_student.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })
        self.assertTrue(enrollment.id)

    # -- record rules: head of studies (issue #466) --

    def test_head_of_studies_can_create_enrollment_for_non_tutored_student(self):
        hos_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HoS Create (Enrollment)', 'login': 'test_hos_create_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_head_of_studies').id)],
        })
        # other_student has no tutor at all, let alone hos_user - proves the access is
        # centre-wide, not limited to the HoS's own tutorands (rule_enrollment_tutor's scope).
        enrollment = self.env['ems.enrollment'].with_user(hos_user).create({
            'student_id': self.other_student.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })
        self.assertTrue(enrollment.id)

    def test_head_of_studies_can_write_enrollment_for_non_tutored_student(self):
        # Reproduces issue #466: a Head/Deputy Head of Studies editing an enrollment from the
        # student's own form for a student they don't personally tutor.
        other_group = self.other_group
        enrollment = self._create_enrollment(student=self.other_student)
        hos_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HoS Write (Enrollment)', 'login': 'test_hos_write_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_head_of_studies').id)],
        })
        enrollment.with_user(hos_user).write({'group_id': other_group.id})
        self.assertEqual(enrollment.group_id, other_group)

    def test_head_of_studies_can_unlink_enrollment_for_non_tutored_student(self):
        enrollment = self._create_enrollment(student=self.other_student)
        hos_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HoS Unlink (Enrollment)', 'login': 'test_hos_unlink_enrollment',
            'groups_id': [(4, self.env.ref('ems.group_head_of_studies').id)],
        })
        enrollment.with_user(hos_user).unlink()
        self.assertFalse(enrollment.exists())

    # -- inuse_subject_ids --

    def test_inuse_subject_ids_lists_students_other_enrolled_subjects(self):
        other_subject = self.env['ems.subject'].create({
            'code': 'TENR002', 'acronym': 'TENR2', 'name': 'Test Subject 2 (Enrollment)',
            'study_ids': [(6, 0, [self.study.id])],
        })
        self._create_enrollment(student=self.student)
        second = self.env['ems.enrollment'].new({'student_id': self.student.id})
        second._compute_inuse_subject_ids()
        # second is a virtual (.new()) record: Odoo wraps its computed relational values with
        # NewId(origin=...) for onchange-time consistency — compare against the real records.
        self.assertIn(self.subject, second.inuse_subject_ids._origin)
        self.assertNotIn(other_subject, second.inuse_subject_ids._origin)

    def test_inuse_subject_ids_empty_without_student(self):
        enrollment = self.env['ems.enrollment'].new({})
        enrollment._compute_inuse_subject_ids()
        self.assertFalse(enrollment.inuse_subject_ids)

    def test_display_name_is_subject_name(self):
        enrollment = self._create_enrollment()
        self.assertEqual(enrollment.display_name, self.subject.display_name)

    # -- unique (student, group, subject) --------------------------------------

    def test_duplicate_student_group_subject_raises(self):
        # See plans/enrollment_junction_duplicate_constraint.md - 21 duplicate
        # triples were found in production before this constraint existed.
        self._create_enrollment()
        with self.assertRaises(Exception):
            self._create_enrollment()

    def test_same_student_different_group_is_allowed(self):
        self._create_enrollment(group=self.group)
        second = self._create_enrollment(group=self.other_group)
        self.assertTrue(second.id)

    # -- _ems_move_group (issue #395: student's main group changes) ------------

    def test_move_group_repoints_enrollment_to_new_group(self):
        enrollment = self._create_enrollment(group=self.group)
        self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)
        self.assertFalse(enrollment.exists())
        moved = self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.subject.id)])
        self.assertEqual(moved.group_id, self.other_group)

    def test_move_group_leaves_enrollment_in_a_different_group_untouched(self):
        third_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'C', 'level_id': self.level.id, 'study_id': self.study.id})
        untouched = self._create_enrollment(group=third_group)
        self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)
        self.assertTrue(untouched.exists())
        self.assertEqual(untouched.group_id, third_group)

    def test_move_group_skips_duplicate_create_when_target_already_enrolled(self):
        old = self._create_enrollment(group=self.group)
        existing_in_new = self._create_enrollment(group=self.other_group)
        self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)
        self.assertFalse(old.exists())
        self.assertTrue(existing_in_new.exists())
        remaining = self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.subject.id)])
        self.assertEqual(remaining, existing_in_new)

    def test_move_group_raises_if_old_enrollment_has_scored_grades(self):
        session = self._create_session(group=self.group)
        enrollment = self._create_enrollment(group=self.group)
        line = session.grade_outcome_line_ids.filtered(lambda l: l.student_id == self.student)
        line.write({'score': 8, 'is_scored': True})

        with self.assertRaises(UserError):
            self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)

        self.assertTrue(enrollment.exists())
        self.assertEqual(enrollment.group_id, self.group)

    def test_move_group_updates_attendance_schedule_roster(self):
        # Different weekday for the second template - same teacher/room/time would otherwise
        # raise check_overlap's real double-booking guard (these are two unrelated templates,
        # not a co-teaching pair, since they share no group).
        template_old = self._create_template([self.group.id], weekday='0')
        template_new = self._create_template([self.other_group.id], weekday='1')
        self._create_enrollment(group=self.group)
        self.assertIn(self.student, template_old.attendance_schedule_ids.student_ids)

        self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)

        self.assertNotIn(self.student, template_old.attendance_schedule_ids.student_ids)
        self.assertIn(self.student, template_new.attendance_schedule_ids.student_ids)

    def test_move_group_keeps_student_in_shared_co_teaching_template(self):
        shared_template = self._create_template([self.group.id, self.other_group.id])
        self._create_enrollment(group=self.group)
        self.assertIn(self.student, shared_template.attendance_schedule_ids.student_ids)

        self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)

        self.assertIn(self.student, shared_template.attendance_schedule_ids.student_ids)

    def test_move_group_migrates_open_grade_session_lines(self):
        session_old = self._create_session(group=self.group)
        session_new = self._create_session(group=self.other_group)
        self._create_enrollment(group=self.group)
        self.assertTrue(session_old.grade_outcome_line_ids.filtered(lambda l: l.student_id == self.student))

        self.env['ems.enrollment']._ems_move_group(self.student, self.group, self.other_group)

        self.assertFalse(session_old.grade_outcome_line_ids.filtered(lambda l: l.student_id == self.student))
        self.assertTrue(session_new.grade_outcome_line_ids.filtered(lambda l: l.student_id == self.student))


class TestEnrollmentSyncAsRestrictedUser(TransactionCase):
    """Issue #435: the attendance-roster / grade-session cascades fired by ems.enrollment's own
    create()/unlink() must land regardless of who triggers them. Every one of those hooks used
    to run with the acting user's own rights, so a secretary (read-only on
    ems.attendance_template/ems.attendance_schedule) or a teacher (record-rule-scoped to their
    OWN templates, see security/rules/attendance.xml) silently reached zero of the schedule
    lines they had to update - found in production after enrolling seven ex-ESO students into
    SA1A: their ems.enrollment rows were created correctly, but they never appeared in any
    attendance roster."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TESR', level={'name': 'Test Level (Enrollment Sync)'}, study={
            'code': 'TESR001', 'name': 'Test Study (Enrollment Sync)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TESR001', 'acronym': 'TESR', 'name': 'Test Subject (Enrollment Sync)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'TESR001_01RA', 'acronym': 'RA1', 'name': 'Outcome 1', 'subject_id': cls.subject.id,
        })
        cls.planning = cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome.id, 'ponderation': 100.0})],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TESR-A', 'name': 'Test Space (Enrollment Sync)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        # The template's OWN teacher - deliberately NOT the user driving the tests below, so the
        # teacher record rule ('teacher_ids.user_id.id = user.id') excludes it for them.
        cls.other_teacher = cls.env['hr.employee'].create({
            'name': 'Test Other Teacher (Enrollment Sync)', 'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student (Enrollment Sync)', 'contact_type': 'student', 'student_id': next_student_id()})

        # A secretary who is ALSO a teacher: the exact real-world combination behind #435 (a
        # secretary teaching a couple of hours). Their teacher group brings in the record rule
        # that hides every template they don't teach.
        cls.secretary_teacher = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary Teacher (Enrollment Sync)',
            'login': 'test_secretary_teacher_enrollment_sync',
            'email': 'test.secretary.teacher.sync@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.env['hr.employee'].create({
            'name': 'Test Secretary Teacher Employee (Enrollment Sync)', 'employee_type': 'teacher',
            'user_id': cls.secretary_teacher.id,
        })
        # A secretary with no teaching at all: read-only on both attendance models, so the same
        # cascade used to raise an AccessError instead of silently doing nothing.
        cls.secretary = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Enrollment Sync)', 'login': 'test_secretary_enrollment_sync',
            'email': 'test.secretary.sync@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })

    def _create_template(self):
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.other_teacher.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, [self.group.id])],
            'start_date': date(2026, 1, 1), 'end_date': date(2026, 6, 30),
        })
        # Several lines (the real SA1A case had 25): the sync must reach every one of them.
        for weekday in ('0', '1', '2'):
            self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template.id, 'weekday': weekday,
                'start_time': 9.0, 'end_time': 10.0, 'space_id': self.space.id,
            })
        return template

    def _create_enrollment_as(self, user):
        return self.env['ems.enrollment'].with_user(user).create({
            'student_id': self.student.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })

    def test_secretary_teacher_create_fills_every_schedule_line(self):
        template = self._create_template()

        self._create_enrollment_as(self.secretary_teacher)

        for line in template.attendance_schedule_ids:
            self.assertIn(self.student, line.student_ids, f"missing from line {line.weekday}")

    def test_secretary_create_fills_every_schedule_line(self):
        template = self._create_template()

        self._create_enrollment_as(self.secretary)

        for line in template.attendance_schedule_ids:
            self.assertIn(self.student, line.student_ids, f"missing from line {line.weekday}")

    def test_secretary_teacher_unlink_clears_every_schedule_line(self):
        template = self._create_template()
        enrollment = self._create_enrollment_as(self.secretary_teacher)

        enrollment.with_user(self.secretary_teacher).unlink()

        for line in template.attendance_schedule_ids:
            self.assertNotIn(self.student, line.student_ids, f"still on line {line.weekday}")

    def test_secretary_teacher_create_adds_open_grade_session_lines(self):
        session = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': self.subject.id,
            'round': '1', 'teacher_id': self.other_teacher.id,
        })

        self._create_enrollment_as(self.secretary_teacher)

        self.assertTrue(session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student))
        self.assertTrue(session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student))
