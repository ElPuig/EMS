from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestAttendanceTemplate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TSAT', level={'name': 'Test Level (Attendance Template)'}, study={
            'code': 'TSAT001', 'name': 'Test Study (Attendance Template)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TSAT001',
            'acronym': 'TSAT',
            'name': 'Test Subject (Attendance Template)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'A',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
        })
        cls.other_subject = cls.env['ems.subject'].create({
            'code': 'TSAT002',
            'acronym': 'TSAT2',
            'name': 'Test Subject 2 (Attendance Template)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space_a = cls.env['ems.space'].create({
            'code': 'TSAT-A',
            'name': 'Test Space A (Attendance Template)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.space_b = cls.env['ems.space'].create({
            'code': 'TSAT-B',
            'name': 'Test Space B (Attendance Template)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher_a = cls.env['hr.employee'].create({
            'name': 'Test Teacher A (Attendance Template)',
            'employee_type': 'teacher',
        })
        cls.teacher_b = cls.env['hr.employee'].create({
            'name': 'Test Teacher B (Attendance Template)',
            'employee_type': 'teacher',
        })

    def _create_template(self, teacher, space, start_date=date(2026, 1, 1), end_date=date(2026, 6, 30), subject=None):
        return self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': (subject or self.subject).id,
            'group_ids': [(6, 0, [self.group.id])],
            'space_id': space.id,
            'start_date': start_date,
            'end_date': end_date,
        })

    def _create_schedule(self, template, space, weekday='0', start_time=9.0, end_time=10.0):
        return self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id,
            'weekday': weekday,
            'start_time': start_time,
            'end_time': end_time,
            'space_id': space.id,
        })

    def _create_session(self, schedule, teacher, date_=date(2026, 1, 5)):
        return self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date_,
            'mode': 'scheduled', 'session_teacher_id': teacher.id,
        })

    def test_allowed_subject_ids_resolves_in_unsaved_form_context(self):
        # Regression guard: inside a still-unsaved .new()/onchange context, 'study_ids' holds
        # NewId-wrapped records - using '.id' on one of them (a placeholder, not a real database
        # id) instead of the recordset's own '.ids' silently made this compute always empty,
        # which broke the subject picker's own domain live in the form (caught by
        # ems_attendance_template_crud's own tour, not by any pre-existing backend test).
        template = self.env['ems.attendance_template'].new({'study_ids': [(6, 0, [self.study.id])]})
        # '._origin': allowed_subject_ids reads back NewId-wrapped copies of the assigned
        # records while 'template' itself is unsaved - '._origin' resolves them back to the
        # real, saved records for a meaningful comparison against 'self.subject'.
        self.assertIn(self.subject, template.allowed_subject_ids._origin)

    def test_allowed_subject_ids_intersects_across_several_studies(self):
        other_study = self.env['ems.study'].create({
            'code': 'TSAT003', 'acronym': 'TSAT3', 'name': 'Test Study 2 (Attendance Template)',
            'date': date.today(), 'deprecated': False, 'level_id': self.level.id,
        })
        shared_subject = self.env['ems.subject'].create({
            'code': 'TSAT003', 'acronym': 'TSAT3', 'name': 'Test Subject 3 (Attendance Template)',
            'study_ids': [(6, 0, [self.study.id, other_study.id])],
        })
        template = self.env['ems.attendance_template'].new({
            'study_ids': [(6, 0, [self.study.id, other_study.id])],
        })
        # self.subject only belongs to self.study, not other_study - excluded from the
        # intersection; shared_subject belongs to both - included. '._origin' - see the
        # previous test's own comment on why it's needed here.
        self.assertNotIn(self.subject, template.allowed_subject_ids._origin)
        self.assertIn(shared_subject, template.allowed_subject_ids._origin)

    def test_invalid_subject_for_study_error_identifies_subject_study_group_and_teacher(self):
        # The error must be actionable: which subject, which study it's missing from, and which
        # template (group/teacher) raised it all need to be readable from the message alone -
        # reported by the developer after hitting this in practice with no way to tell which
        # template/study was actually responsible (2026-08-10).
        unrelated_subject = self.env['ems.subject'].create({
            'code': 'TSAT004', 'acronym': 'TSAT4', 'name': 'Test Unrelated Subject (Attendance Template)',
        })
        with self.assertRaises(ValidationError) as capture:
            self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, [self.teacher_a.id])],
                'study_ids': [(6, 0, [self.study.id])],
                'subject_id': unrelated_subject.id,
                'group_ids': [(6, 0, [self.group.id])],
                'space_id': self.space_a.id,
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 6, 30),
            })
        message = str(capture.exception)
        self.assertIn(unrelated_subject.name, message)
        self.assertIn(self.study.display_name, message)
        self.assertIn(self.group.display_name, message)
        self.assertIn(self.teacher_a.display_name, message)

        # Real Catalan translation, verified functionally under a real lang context - this
        # Odoo version reads Python _() code-string translations straight from the module's
        # own checked-in .po file at runtime, with no database column to psql-verify against.
        with self.assertRaises(ValidationError) as ca_capture:
            self.env['ems.attendance_template'].with_context(lang='ca_ES').create({
                'teacher_ids': [(6, 0, [self.teacher_a.id])],
                'study_ids': [(6, 0, [self.study.id])],
                'subject_id': unrelated_subject.id,
                'group_ids': [(6, 0, [self.group.id])],
                'space_id': self.space_a.id,
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 6, 30),
            })
        self.assertIn("no està disponible", str(ca_capture.exception))

    def test_create_default_color(self):
        template = self._create_template(self.teacher_a, self.space_a)
        self.assertEqual(template.color, '#3A8DDE')

    def test_invalid_color_raises(self):
        with self.assertRaises(Exception):
            self._create_template(self.teacher_a, self.space_a).write({'color': 'not-a-color'})

    def test_same_teacher_overlapping_time_raises(self):
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        # subject=other_subject: two templates for the SAME subject/teacher/group would trip the
        # new exact-duplicate check (point 2) - this test is about check_overlap's own space/time
        # logic, which doesn't care about subject identity, so a different subject sidesteps that
        # unrelated check without changing what's actually being tested here.
        template2 = self._create_template(self.teacher_a, self.space_b, subject=self.other_subject)
        with self.assertRaises(ValidationError):
            self._create_schedule(template2, self.space_b, weekday='0', start_time=9.5, end_time=10.5)

    def test_overlap_error_identifies_both_sessions(self):
        # The error must be actionable: both colliding sessions (subject/groups, teacher, space,
        # time) need to be identifiable from the message alone, not just the other one's template.
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        # subject=other_subject: see test_same_teacher_overlapping_time_raises's own comment.
        template2 = self._create_template(self.teacher_a, self.space_b, subject=self.other_subject)
        with self.assertRaises(ValidationError) as capture:
            self._create_schedule(template2, self.space_b, weekday='0', start_time=9.5, end_time=10.5)

        message = str(capture.exception)
        self.assertIn(template1.display_name, message)
        self.assertIn(template2.display_name, message)
        self.assertIn(self.teacher_a.display_name, message)
        self.assertIn('09:00 - 10:00', message)
        self.assertIn('09:30 - 10:30', message)

    def test_same_teacher_non_overlapping_time_allowed(self):
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        # subject=other_subject: see test_same_teacher_overlapping_time_raises's own comment.
        template2 = self._create_template(self.teacher_a, self.space_b, subject=self.other_subject)
        schedule2 = self._create_schedule(template2, self.space_b, weekday='0', start_time=10.0, end_time=11.0)
        self.assertTrue(schedule2.id)

    def test_same_teacher_different_weekday_allowed(self):
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        # subject=other_subject: see test_same_teacher_overlapping_time_raises's own comment. A
        # real same-subject/teacher/group "different weekday" case is instead ONE template with
        # TWO schedule lines (see docs/en/developers/employees/working_schedule.md's own
        # "Co-teaching" section) - not two separate templates, which point 2's new constraint now
        # correctly rejects as a duplicate teaching assignment.
        template2 = self._create_template(self.teacher_a, self.space_b, subject=self.other_subject)
        schedule2 = self._create_schedule(template2, self.space_b, weekday='3', start_time=9.0, end_time=10.0)
        self.assertTrue(schedule2.id)

    def test_different_teacher_same_space_overlapping_time_raises(self):
        # Different subject (not co-teaching — see test_co_teaching_same_subject_and_group_allowed):
        # a genuine, unrelated double-booking of the same room must still raise.
        template1 = self._create_template(self.teacher_a, self.space_a, subject=self.other_subject)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_b, self.space_b)
        with self.assertRaises(ValidationError):
            self._create_schedule(template2, self.space_a, weekday='0', start_time=9.5, end_time=10.5)

    def test_co_teaching_same_subject_and_group_allowed(self):
        # Two teachers legitimately co-teaching the SAME class (same subject, sharing a group) in the
        # same room at the same time must NOT be treated as a conflict.
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_b, self.space_a)
        schedule2 = self._create_schedule(template2, self.space_a, weekday='0', start_time=9.0, end_time=10.0)
        self.assertTrue(schedule2.id)

    def test_different_teacher_different_space_allowed(self):
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_b, self.space_b)
        schedule2 = self._create_schedule(template2, self.space_b, weekday='0', start_time=9.5, end_time=10.5)
        self.assertTrue(schedule2.id)

    def test_non_overlapping_dates_allowed(self):
        template1 = self._create_template(self.teacher_a, self.space_a, start_date=date(2026, 1, 1), end_date=date(2026, 2, 28))
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        # subject=other_subject: see test_same_teacher_overlapping_time_raises's own comment -
        # point 2's new duplicate-assignment constraint is deliberately date-range-agnostic (this
        # system never represents "same assignment, different period" as two coexisting active
        # templates - see that constraint's own docstring), so a same-subject/teacher/group pair
        # here would trip it regardless of the non-overlapping dates being tested.
        template2 = self._create_template(self.teacher_a, self.space_b, subject=self.other_subject, start_date=date(2026, 3, 1), end_date=date(2026, 6, 30))
        schedule2 = self._create_schedule(template2, self.space_b, weekday='0', start_time=9.0, end_time=10.0)
        self.assertTrue(schedule2.id)

    def test_changing_template_teacher_retriggers_check(self):
        # Regression: @api.constrains cannot depend on related-model field paths, so the
        # template must explicitly re-run the schedule's check when its own fields change.
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_b, self.space_b)
        self._create_schedule(template2, self.space_b, weekday='0', start_time=9.5, end_time=10.5)

        with self.assertRaises(ValidationError):
            template2.write({'teacher_ids': [(6, 0, [self.teacher_a.id])]})

    def test_exact_duplicate_teaching_assignment_raises(self):
        # See plans/calendar_driven_attendance_templates.md, point 2.
        self._create_template(self.teacher_a, self.space_a)

        with self.assertRaises(ValidationError):
            self._create_template(self.teacher_a, self.space_b)

    def test_partial_group_overlap_with_different_exact_set_is_allowed(self):
        # Deliberately NOT an "any overlap" check - a real, legitimate "desdoble" pattern exists
        # in production data: the same teacher teaches the same subject to a group alone AND to
        # that same group combined with another, in separate templates whose 'group_ids' genuinely
        # differ (not identical) - see the constraint's own docstring for the full reasoning.
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher_a.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, [self.group.id])],
            'space_id': self.space_a.id,
            'start_date': date(2026, 1, 1), 'end_date': date(2026, 6, 30),
        })

        combined = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher_a.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, [self.group.id, other_group.id])],
            'space_id': self.space_a.id,
            'start_date': date(2026, 1, 1), 'end_date': date(2026, 6, 30),
        })
        self.assertTrue(combined.id)

    def test_archived_duplicate_does_not_block_a_new_active_one(self):
        existing = self._create_template(self.teacher_a, self.space_a)
        # ems_bypass_template_lock: manual archival is otherwise blocked (point 3) - this test is
        # about point 2's own duplicate check, not the archival lock, so bypass it as test setup,
        # same as the calendar-sync pipeline itself does internally.
        existing.with_context(ems_bypass_template_lock=True).action_archive()

        new_template = self._create_template(self.teacher_a, self.space_b)

        self.assertTrue(new_template.id)

    def test_different_teacher_set_is_not_a_duplicate(self):
        self._create_template(self.teacher_a, self.space_a)

        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher_a.id, self.teacher_b.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, [self.group.id])],
            'space_id': self.space_b.id,
            'start_date': date(2026, 1, 1), 'end_date': date(2026, 6, 30),
        })
        self.assertTrue(template.id)

    def test_create_with_several_teachers(self):
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher_a.id, self.teacher_b.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, [self.group.id])],
            'space_id': self.space_a.id,
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 6, 30),
        })
        self.assertEqual(set(template.teacher_ids.ids), {self.teacher_a.id, self.teacher_b.id})

    def test_empty_teacher_ids_raises(self):
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, [])],
                'study_ids': [(6, 0, [self.study.id])],
                'subject_id': self.subject.id,
                'group_ids': [(6, 0, [self.group.id])],
                'space_id': self.space_a.id,
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 6, 30),
            })

    def test_new_schedule_line_defaults_space_from_template_context(self):
        # A new line added via the template's own form defaults its room from the template's
        # (views/attendance/attendance_template/form.xml's own
        # context="{'default_space_id': space_id, ...}" on 'attendance_schedule_ids') - no custom
        # onchange needed on ems.attendance_schedule itself, Odoo's own 'default_<field>' context
        # convention already covers it. Verified here at the model level (context + new()) since
        # Form() can't exercise the template's own view directly: it references 'read_only_user'
        # (a default=-only, non-computed field) in several 'readonly=' expressions without ever
        # declaring it in the arch, tripping a pre-existing Form() modifier-processing limitation
        # (KeyError) unrelated to this change.
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self.env['ems.attendance_schedule'].with_context(
            default_space_id=template.space_id.id
        ).new({'attendance_template_id': template.id})

        self.assertEqual(schedule.space_id, self.space_a)

    def test_has_sessions_false_without_real_session(self):
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self._create_schedule(template, self.space_a)

        self.assertFalse(template.has_sessions)
        self.assertFalse(schedule.has_sessions)

    def test_has_sessions_true_once_session_created(self):
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self._create_schedule(template, self.space_a)

        self._create_session(schedule, self.teacher_a)

        self.assertTrue(template.has_sessions)
        self.assertTrue(schedule.has_sessions)

    def test_write_or_new_version_writes_in_place_without_sessions(self):
        # Direct unit coverage for 'ems.attendance_mixin._write_or_new_version' itself - the
        # manual "Edit" button (action_new_version) that used to be its main entry point was
        # removed 2026-08-11 (see plans/calendar_driven_attendance_templates.md, point 3), but the
        # shared mechanism itself is still used internally by the schedule-sync pipeline and the
        # import wizard's room-reassignment resolution, so it deserves its own test independent of
        # any specific caller.
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self._create_schedule(template, self.space_a)
        schedule_id = schedule.id

        result = schedule._write_or_new_version({'space_id': self.space_b.id})

        self.assertEqual(result.id, schedule_id)
        self.assertTrue(result.active)
        self.assertEqual(result.space_id, self.space_b)

    def test_write_or_new_version_archives_and_clones_with_sessions(self):
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self._create_schedule(template, self.space_a)
        schedule_id = schedule.id
        session = self._create_session(schedule, self.teacher_a)

        result = schedule._write_or_new_version({'space_id': self.space_b.id})

        self.assertNotEqual(result.id, schedule_id)
        self.assertFalse(schedule.active)
        self.assertEqual(result.space_id, self.space_b)
        self.assertEqual(session.attendance_schedule_id.id, schedule_id)

    def test_action_archive_does_not_cascade_to_sessions(self):
        # Developer feedback 2026-08-06, reversing an earlier same-day decision: archiving a
        # schedule line (directly, via '_write_or_new_version''s archive-before-clone step above,
        # or via the template's own cascade below) must NOT archive its sessions, in either
        # direction. A schedule line can be archived for reasons that have nothing to do with a
        # session's own relevance (e.g. a mid-course room correction) - sessions are an
        # independent historical record, never touched as a side effect of
        # whatever happens to the schedule/template that originally scheduled them. See
        # plans/course_transition_teacher_schedule_archival.md.
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self._create_schedule(template, self.space_a)
        session = self._create_session(schedule, self.teacher_a)

        schedule.action_archive()

        self.assertFalse(schedule.active)
        self.assertTrue(session.active)

    def test_action_archive_on_template_does_not_cascade_to_sessions(self):
        # Same rule, one level up: template.action_archive() already archives
        # attendance_schedule_ids (pre-existing behavior, unaffected) - but that must not reach
        # sessions either.
        template = self._create_template(self.teacher_a, self.space_a)
        schedule = self._create_schedule(template, self.space_a)
        session = self._create_session(schedule, self.teacher_a)

        # ems_bypass_template_lock: this test is about the archive-cascade behavior, not point 3's
        # own archival lock - bypass it as test setup, same as the calendar-sync pipeline does.
        template.with_context(ems_bypass_template_lock=True).action_archive()

        self.assertFalse(template.active)
        self.assertFalse(schedule.active)
        self.assertTrue(session.active)

    def test_read_only_user_false_for_either_co_teacher(self):
        template = self._create_template(self.teacher_a, self.space_a)
        template.teacher_ids = [(4, self.teacher_b.id)]
        self.teacher_b.user_id = self.env['res.users'].create({
            'name': 'Test User B (Attendance Template)',
            'login': 'test_user_b_attendance_template@example.com',
            'groups_id': [(4, self.env.ref('base.group_user').id), (4, self.env.ref('ems.group_teacher').id)],
        })
        template = template.with_user(self.teacher_b.user_id)
        self.assertFalse(template._get_read_only_user())


class TestAttendanceTemplateSyncFromSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TATS', level={'name': 'Test Level (Attendance Template Sync)'}, study={
            'code': 'TATS001', 'name': 'Test Study (Attendance Template Sync)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TATS001',
            'acronym': 'TATS',
            'name': 'Test Subject (Attendance Template Sync)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TATS-A',
            'name': 'Test Space (Attendance Template Sync)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'TATS',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.space.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Attendance Template Sync)',
            'employee_type': 'teacher',
        })
        cls.other_space = cls.env['ems.space'].create({
            'code': 'TATS-B',
            'name': 'Test Space B (Attendance Template Sync)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.other_subject = cls.env['ems.subject'].create({
            'code': 'TATS002',
            'acronym': 'TATS2',
            'name': 'Test Subject 2 (Attendance Template Sync)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.other_group = cls.env['ems.group'].create({
            'course': 2,
            'acronym': 'TATS2',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.other_space.id,
        })
        cls.other_teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher B (Attendance Template Sync)',
            'employee_type': 'teacher',
        })

    def _entry(self, hour_from=9, hour_to=10, dayofweek='0', subject=None, group=None, group_ids=None, space=None):
        entry = {
            'subject_id': (subject or self.subject).id,
            'group_ids': group_ids if group_ids is not None else [(group or self.group).id],
            'hour_from': hour_from,
            'hour_to': hour_to,
            'dayofweek': dayofweek,
        }
        if space is not None:
            entry['space_id'] = space.id
        return entry

    def test_creates_template_with_schedule_and_space_from_group(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()], start_date=date(2026, 2, 1))

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id),
            ('subject_id', '=', self.subject.id),
        ])
        self.assertTrue(template)
        self.assertEqual(template.space_id, self.space)
        self.assertEqual(template.start_date, date(2026, 2, 1))
        self.assertEqual(len(template.attendance_schedule_ids), 1)
        self.assertRegex(template.color, r'^#[0-9A-Fa-f]{6}$')

    def test_sync_covers_both_groups_when_two_main_groups_share_one_session(self):
        # Real scenario: a level split into two official groups (e.g. a "desdoblament") that share
        # the same classroom but are taught as two distinct ems.group records - not a reinforcement
        # group. group_ids is a plain Many2many precisely to support this: one template, one set of
        # attendance_schedule_ids, covering both groups at once.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.teacher, [self._entry(group_ids=[self.group.id, self.other_group.id])])

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(template.group_ids, self.group | self.other_group)
        # Documented simplification (see docs/en/developers/attendance/attendance_template.md):
        # space_id/level_id/study_id are all derived from the FIRST group only. Safe as long as
        # every combined group shares the same classroom - not validated/warned otherwise.
        self.assertEqual(template.space_id, self.space)

    def test_fill_students_pulls_students_from_every_shared_group(self):
        student_a = self.env['res.partner'].create({
            'name': 'Student Group A (Attendance Template Sync)', 'contact_type': 'student'})
        student_b = self.env['res.partner'].create({
            'name': 'Student Group B (Attendance Template Sync)', 'contact_type': 'student'})
        self.env['ems.enrollment'].create({
            'student_id': student_a.id, 'group_id': self.group.id, 'subject_id': self.subject.id})
        self.env['ems.enrollment'].create({
            'student_id': student_b.id, 'group_id': self.other_group.id, 'subject_id': self.subject.id})

        self.env['ems.attendance_template'].sync_from_schedule(
            self.teacher, [self._entry(group_ids=[self.group.id, self.other_group.id])])

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.student_ids, student_a | student_b)

    def test_consecutive_syncs_get_different_colors(self):
        # Regression guard: color used to be based on position within the current sync batch,
        # which is almost always 0 (most syncs create a single template) - every template ended
        # up the same color. It must now be based on the running total of templates ever created,
        # so two unrelated, separately-synced templates land on different colors.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()])
        first = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])

        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(subject=self.other_subject, group=self.other_group)])
        second = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.other_teacher.id)])

        self.assertNotEqual(first.color, second.color)

    def test_default_start_date_is_september_first(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()])

        template = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])
        self.assertEqual(template.start_date.month, 9)
        self.assertEqual(template.start_date.day, 1)

    def test_archives_template_no_longer_in_entries(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()])
        template = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [])

        self.assertFalse(template.active)

    def test_second_entry_same_key_reuses_template(self):
        # Two schedule slots for the same subject+group must land on the SAME template, not create two.
        entries = [self._entry(9, 10, '0'), self._entry(9, 10, '2')]

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, entries)

        templates = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id),
            ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(len(templates), 1)
        self.assertEqual(len(templates.attendance_schedule_ids), 2)

    def test_resync_same_key_replaces_stale_schedule_lines(self):
        # Real-world bug: a subject+group combo that persists across re-imports kept its FIRST
        # import's schedule lines forever, even after the actual bell schedule changed.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        template = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(17, 18, '0')])

        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertEqual(template.attendance_schedule_ids.mapped('end_time'), [18])

    def test_resync_same_key_updates_space_from_group(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        template = self.env['ems.attendance_template'].search([('teacher_ids', 'in', self.teacher.id)])
        self.assertEqual(template.space_id, self.space)

        # Same subject+group, but its default classroom changed since the last import.
        self.group.space_id = self.other_space
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])

        self.assertEqual(template.space_id, self.other_space)

    def test_resync_updates_schedule_line_in_place_when_no_sessions(self):
        # A matched line (same weekday/time) whose room changed, with no real attendance history
        # yet, must be updated in place - same DB id - not archived and recreated. See
        # 'ems.attendance_template._match_schedule_lines'/'_write_schedule_sync'.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        line = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
        ])
        line_id = line.id

        self.group.space_id = self.other_space
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])

        self.assertEqual(line.id, line_id)
        self.assertTrue(line.active)
        self.assertEqual(line.space_id, self.other_space)

    def test_resync_archives_and_recreates_schedule_line_when_sessions_exist(self):
        # Same scenario as above, but the matched line already has a real attendance session -
        # updating its room in place would retroactively misrepresent that session. Must archive
        # the original (history stays intact) and create a fresh replacement with the new room.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        line = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
        ])
        line_id = line.id
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': line.id, 'date': date(2026, 2, 2),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })

        self.group.space_id = self.other_space
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])

        self.assertFalse(line.active)
        self.assertEqual(session.attendance_schedule_id.id, line_id)  # history stays linked to the archived original
        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        new_line = template.attendance_schedule_ids
        self.assertNotEqual(new_line.id, line_id)
        self.assertEqual(new_line.space_id, self.other_space)

    def test_resync_leaves_unchanged_schedule_line_untouched(self):
        # A matched line whose weekday/time/room are all identical to the incoming entry must not
        # be touched at all - not even a no-op archive+recreate.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        line = self.env['ems.attendance_schedule'].search([
            ('attendance_template_id.teacher_ids', 'in', self.teacher.id),
        ])
        line_id = line.id
        write_date = line.write_date

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])

        self.assertEqual(line.id, line_id)
        self.assertTrue(line.active)
        self.assertEqual(line.write_date, write_date)

    def test_sync_respects_entry_level_space_override(self):
        # An entry carrying its own 'space_id' (e.g. a one-off room reassignment resolved by the
        # import wizard) must win over the group's own default room.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.teacher, [self._entry(space=self.other_space)])

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.space_id, self.other_space)
        # The template's own 'space_id' stays the group-derived default - only the schedule
        # line's own room is overridden.
        self.assertEqual(template.space_id, self.space)

    def test_resync_swapped_times_across_two_persisting_keys_does_not_raise(self):
        # Real-world bug: refreshing a persisting template's schedule lines one key at a time (archive
        # then immediately rewrite, before moving to the next key) let an EARLIER-processed template's
        # fresh line collide with a LATER-processed template's still-active stale line. Swapping two
        # persisting subjects' time slots on re-import reproduces this regardless of which key happens
        # to be processed first — it must never raise ValidationError (ems.attendance_schedule.check_overlap).
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [
            self._entry(9, 10, '0'),
            self._entry(17, 18, '0', subject=self.other_subject, group=self.other_group),
        ])

        entries = [
            self._entry(17, 18, '0'),  # takes over what used to be other_subject's slot
            self._entry(9, 10, '0', subject=self.other_subject, group=self.other_group),  # and vice versa
        ]
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, entries)

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertEqual(other_template.attendance_schedule_ids.mapped('start_time'), [9])

    def test_batch_swapped_times_across_two_teachers_sharing_a_room_does_not_raise(self):
        # Real-world bug: syncing one teacher fully (archive + write) before moving on to the next let
        # an early teacher's fresh line collide with a later teacher's still-stale line when they share
        # a classroom (same group's default space) — the later teacher's stale data hadn't been
        # archived yet at that point. sync_from_schedule_batch() must archive every teacher's stale
        # lines first, across the whole batch, before writing any of them.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        # Swap: teacher takes over what used to be other_teacher's slot in the SAME room, and vice versa.
        teacher_entries = [
            (self.teacher, [self._entry(17, 18, '0')]),
            (self.other_teacher, [self._entry(9, 10, '0', subject=self.other_subject, group=self.group)]),
        ]
        self.env['ems.attendance_template'].sync_from_schedule_batch(teacher_entries)

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.other_teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertEqual(other_template.attendance_schedule_ids.mapped('start_time'), [9])

    def test_resync_consolidates_duplicate_templates_for_same_key(self):
        # Real-world bug: a teacher can end up with MORE THAN ONE active template for the same
        # subject+group combo — a pre-existing data-quality leftover from repeated past imports that
        # each created a new template instead of matching the existing one. Keying the sync's old-items
        # map by a single template silently drops every duplicate but the last one seen, so its stale
        # schedule line is never refreshed and can falsely collide with a later import.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        primary = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])

        # A pre-existing duplicate for the SAME subject+group, with its own stale line at 17-18 — the
        # slot the next import will want to reuse for this same subject.
        duplicate = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [self.teacher.id])],
            'study_ids': [(6, 0, [self.study.id])],
            'subject_id': self.subject.id,
            'group_ids': [(6, 0, [self.group.id])],
            'space_id': self.space.id,
            'start_date': date(2026, 9, 1),
            'end_date': date(2027, 7, 1),
            'attendance_schedule_ids': [(0, 0, {
                'weekday': '0', 'start_time': 17, 'end_time': 18, 'space_id': self.space.id,
            })],
        })

        # Re-import moves the subject into what was the duplicate's stale slot — must not raise.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(17, 18, '0')])

        active_templates = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(len(active_templates), 1)
        self.assertEqual(active_templates.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertIn(active_templates, primary | duplicate)

    def test_classify_external_conflicts_detects_overlapping_room_from_teacher_outside_batch(self):
        # 'other_teacher' is NOT part of the batch being imported — a real-world case where a teacher
        # simply isn't included in the file being (re)imported, but their stale schedule still occupies
        # a room the new import now also wants at an overlapping time. Different subject/group: a
        # genuine space conflict, not co-teaching.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts([
            (self.teacher, [self._entry(17, 18, '0')]),  # same room (self.group's space), overlapping time
        ])

        self.assertFalse(co_teaching)
        self.assertEqual(len(space_conflicts), 1)
        self.assertEqual(space_conflicts.attendance_template_id.teacher_ids, self.other_teacher)

    def test_classify_external_conflicts_ignores_non_overlapping_time(self):
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts([
            (self.teacher, [self._entry(9, 10, '0')]),  # same room, but no time overlap
        ])

        self.assertFalse(co_teaching)
        self.assertFalse(space_conflicts)

    def test_classify_external_conflicts_ignores_teacher_already_in_batch(self):
        # A teacher sharing a room with themselves (or with someone else already in the same batch) is
        # NOT an "external" conflict — sync_from_schedule_batch's own archive-then-write pass already
        # handles that case.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts([
            (self.teacher, [self._entry(17, 18, '0')]),
            (self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]),
        ])

        self.assertFalse(co_teaching)
        self.assertFalse(space_conflicts)

    def test_classify_external_conflicts_reports_co_teaching_separately(self):
        # 'other_teacher' co-teaches the SAME subject+group as 'self.teacher' — a legitimate setup, not
        # a conflict to archive, even though 'other_teacher' isn't part of this batch. Reported as
        # co-teaching, not as a space conflict.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.subject, group=self.group)]
        )

        co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts([
            (self.teacher, [self._entry(17, 18, '0')]),
        ])

        self.assertEqual(len(co_teaching), 1)
        self.assertEqual(co_teaching.attendance_template_id.teacher_ids, self.other_teacher)
        self.assertFalse(space_conflicts)

    def test_resync_frees_up_stale_slot_for_new_subject(self):
        # Reproduces the reported bug: a persisting subject+group's stale time slot must not collide
        # with a genuinely new subject taking over that same slot on re-import.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(17, 18, '0')])

        entries = [
            self._entry(9, 10, '0'),  # 'self.subject'/'self.group' moved to a new time this course
            self._entry(17, 18, '0', subject=self.other_subject, group=self.other_group),  # takes the freed slot
        ]

        # Must not raise ValidationError (ems.attendance_schedule.check_overlap).
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, entries)

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [9])
        self.assertEqual(other_template.attendance_schedule_ids.mapped('start_time'), [17])

    def test_batch_merges_exact_shared_slot_into_one_template(self):
        # Two teachers in the same import batch, same subject+group, one slot in common (Wednesday)
        # and one held only by teacher A (Monday): must produce a shared A+B template for Wednesday and
        # a solo A template for Monday — not two fully separate per-teacher templates.
        teacher_entries = [
            (self.teacher, [self._entry(9, 10, '0'), self._entry(9, 10, '2')]),  # Monday + Wednesday
            (self.other_teacher, [self._entry(9, 10, '2')]),  # Wednesday only, exact same slot
        ]
        self.env['ems.attendance_template'].sync_from_schedule_batch(teacher_entries)

        templates = self.env['ems.attendance_template'].search([('subject_id', '=', self.subject.id)])
        self.assertEqual(len(templates), 2)

        shared = templates.filtered(lambda t: len(t.teacher_ids) == 2)
        solo = templates.filtered(lambda t: len(t.teacher_ids) == 1)
        self.assertEqual(len(shared), 1)
        self.assertEqual(len(solo), 1)
        self.assertEqual(set(shared.teacher_ids.ids), {self.teacher.id, self.other_teacher.id})
        self.assertEqual(shared.attendance_schedule_ids.mapped('weekday'), ['2'])
        self.assertEqual(solo.teacher_ids, self.teacher)
        self.assertEqual(solo.attendance_schedule_ids.mapped('weekday'), ['0'])

    def test_live_edit_by_second_teacher_splits_first_teachers_template(self):
        # Teacher A already has a template with Monday+Wednesday. Teacher B then edits their OWN
        # schedule alone (simulating the 'Schedule' tab's live editor) and lands on the exact same
        # Wednesday slot: A's template must shrink to Monday-only, and a new shared A+B template must
        # appear for Wednesday — even though A never resubmitted anything in this call.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.teacher, [self._entry(9, 10, '0'), self._entry(9, 10, '2')]
        )

        self.env['ems.attendance_template'].sync_from_schedule(self.other_teacher, [self._entry(9, 10, '2')])

        templates = self.env['ems.attendance_template'].search([('subject_id', '=', self.subject.id)])
        self.assertEqual(len(templates), 2)

        shared = templates.filtered(lambda t: len(t.teacher_ids) == 2)
        solo = templates.filtered(lambda t: len(t.teacher_ids) == 1)
        self.assertEqual(len(shared), 1)
        self.assertEqual(len(solo), 1)
        self.assertEqual(set(shared.teacher_ids.ids), {self.teacher.id, self.other_teacher.id})
        self.assertEqual(shared.attendance_schedule_ids.mapped('weekday'), ['2'])
        self.assertEqual(solo.teacher_ids, self.teacher)
        self.assertEqual(solo.attendance_schedule_ids.mapped('weekday'), ['0'])

    def test_live_edit_removing_shared_slot_leaves_co_teachers_solo_template_intact(self):
        # Symmetric case: A and B share a Wednesday slot; A then edits their own schedule to drop it.
        # B's Wednesday must survive solo, untouched.
        teacher_entries = [
            (self.teacher, [self._entry(9, 10, '2')]),
            (self.other_teacher, [self._entry(9, 10, '2')]),
        ]
        self.env['ems.attendance_template'].sync_from_schedule_batch(teacher_entries)

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [])

        templates = self.env['ems.attendance_template'].search([('subject_id', '=', self.subject.id)])
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates.teacher_ids, self.other_teacher)
        self.assertEqual(templates.attendance_schedule_ids.mapped('weekday'), ['2'])

    def test_live_edit_dropping_solo_combo_archives_template(self):
        # A drops a subject+group combo nobody else teaches: the template must be archived outright.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [])

        self.assertFalse(template.active)
