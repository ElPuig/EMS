from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study


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
        cls.student = cls.env['res.partner'].create({'name': 'Test Student (Enrollment)', 'contact_type': 'student'})
        cls.other_student = cls.env['res.partner'].create({'name': 'Test Student B (Enrollment)', 'contact_type': 'student'})

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
