from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAttendanceTemplate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level = cls.env['ems.level'].create({'acronym': 'TSAT', 'name': 'Test Level (Attendance Template)'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TSAT001',
            'acronym': 'TSAT',
            'name': 'Test Study (Attendance Template)',
            'date': date.today(),
            'deprecated': False,
            'level_id': cls.level.id,
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
            'teacher_id': teacher.id,
            'level_id': self.level.id,
            'study_id': self.study.id,
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

    def test_same_teacher_overlapping_time_raises(self):
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_a, self.space_b)
        with self.assertRaises(ValidationError):
            self._create_schedule(template2, self.space_b, weekday='0', start_time=9.5, end_time=10.5)

    def test_overlap_error_identifies_both_sessions(self):
        # The error must be actionable: both colliding sessions (subject/groups, teacher, space,
        # time) need to be identifiable from the message alone, not just the other one's template.
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_a, self.space_b)
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

        template2 = self._create_template(self.teacher_a, self.space_b)
        schedule2 = self._create_schedule(template2, self.space_b, weekday='0', start_time=10.0, end_time=11.0)
        self.assertTrue(schedule2.id)

    def test_same_teacher_different_weekday_allowed(self):
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_a, self.space_b)
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

        template2 = self._create_template(self.teacher_a, self.space_b, start_date=date(2026, 3, 1), end_date=date(2026, 6, 30))
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
            template2.write({'teacher_id': self.teacher_a.id})


class TestAttendanceTemplateSyncFromSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level = cls.env['ems.level'].create({'acronym': 'TATS', 'name': 'Test Level (Attendance Template Sync)'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TATS001',
            'acronym': 'TATS',
            'name': 'Test Study (Attendance Template Sync)',
            'date': date.today(),
            'deprecated': False,
            'level_id': cls.level.id,
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

    def _entry(self, hour_from=9, hour_to=10, dayofweek='0', subject=None, group=None):
        return {
            'subject_id': (subject or self.subject).id,
            'group_ids': [(group or self.group).id],
            'hour_from': hour_from,
            'hour_to': hour_to,
            'dayofweek': dayofweek,
        }

    def test_creates_template_with_schedule_and_space_from_group(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()], start_date=date(2026, 2, 1))

        template = self.env['ems.attendance_template'].search([
            ('teacher_id', '=', self.teacher.id),
            ('subject_id', '=', self.subject.id),
        ])
        self.assertTrue(template)
        self.assertEqual(template.space_id, self.space)
        self.assertEqual(template.start_date, date(2026, 2, 1))
        self.assertEqual(len(template.attendance_schedule_ids), 1)

    def test_default_start_date_is_september_first(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()])

        template = self.env['ems.attendance_template'].search([('teacher_id', '=', self.teacher.id)])
        self.assertEqual(template.start_date.month, 9)
        self.assertEqual(template.start_date.day, 1)

    def test_archives_template_no_longer_in_entries(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry()])
        template = self.env['ems.attendance_template'].search([('teacher_id', '=', self.teacher.id)])

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [])

        self.assertFalse(template.active)

    def test_second_entry_same_key_reuses_template(self):
        # Two schedule slots for the same subject+group must land on the SAME template, not create two.
        entries = [self._entry(9, 10, '0'), self._entry(9, 10, '2')]

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, entries)

        templates = self.env['ems.attendance_template'].search([
            ('teacher_id', '=', self.teacher.id),
            ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(len(templates), 1)
        self.assertEqual(len(templates.attendance_schedule_ids), 2)

    def test_resync_same_key_replaces_stale_schedule_lines(self):
        # Real-world bug: a subject+group combo that persists across re-imports kept its FIRST
        # import's schedule lines forever, even after the actual bell schedule changed.
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        template = self.env['ems.attendance_template'].search([('teacher_id', '=', self.teacher.id)])

        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(17, 18, '0')])

        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertEqual(template.attendance_schedule_ids.mapped('end_time'), [18])

    def test_resync_same_key_updates_space_from_group(self):
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])
        template = self.env['ems.attendance_template'].search([('teacher_id', '=', self.teacher.id)])
        self.assertEqual(template.space_id, self.space)

        # Same subject+group, but its default classroom changed since the last import.
        self.group.space_id = self.other_space
        self.env['ems.attendance_template'].sync_from_schedule(self.teacher, [self._entry(9, 10, '0')])

        self.assertEqual(template.space_id, self.other_space)

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
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.other_subject.id),
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
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_id', '=', self.other_teacher.id), ('subject_id', '=', self.other_subject.id),
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
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])

        # A pre-existing duplicate for the SAME subject+group, with its own stale line at 17-18 — the
        # slot the next import will want to reuse for this same subject.
        duplicate = self.env['ems.attendance_template'].create({
            'teacher_id': self.teacher.id,
            'level_id': self.level.id,
            'study_id': self.study.id,
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
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(len(active_templates), 1)
        self.assertEqual(active_templates.attendance_schedule_ids.mapped('start_time'), [17])
        self.assertIn(active_templates, primary | duplicate)

    def test_find_external_conflicts_detects_overlapping_room_from_teacher_outside_batch(self):
        # 'other_teacher' is NOT part of the batch being imported — a real-world case where a teacher
        # simply isn't included in the file being (re)imported, but their stale schedule still occupies
        # a room the new import now also wants at an overlapping time.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        conflicts = self.env['ems.attendance_template'].find_external_conflicts([
            (self.teacher, [self._entry(17, 18, '0')]),  # same room (self.group's space), overlapping time
        ])

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts.attendance_template_id.teacher_id, self.other_teacher)

    def test_find_external_conflicts_ignores_non_overlapping_time(self):
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        conflicts = self.env['ems.attendance_template'].find_external_conflicts([
            (self.teacher, [self._entry(9, 10, '0')]),  # same room, but no time overlap
        ])

        self.assertFalse(conflicts)

    def test_find_external_conflicts_ignores_teacher_already_in_batch(self):
        # A teacher sharing a room with themselves (or with someone else already in the same batch) is
        # NOT an "external" conflict — sync_from_schedule_batch's own archive-then-write pass already
        # handles that case.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]
        )

        conflicts = self.env['ems.attendance_template'].find_external_conflicts([
            (self.teacher, [self._entry(17, 18, '0')]),
            (self.other_teacher, [self._entry(17, 18, '0', subject=self.other_subject, group=self.group)]),
        ])

        self.assertFalse(conflicts)

    def test_find_external_conflicts_ignores_co_teaching(self):
        # 'other_teacher' co-teaches the SAME subject+group as 'self.teacher' — a legitimate setup, not
        # a conflict to archive, even though 'other_teacher' isn't part of this batch.
        self.env['ems.attendance_template'].sync_from_schedule(
            self.other_teacher, [self._entry(17, 18, '0', subject=self.subject, group=self.group)]
        )

        conflicts = self.env['ems.attendance_template'].find_external_conflicts([
            (self.teacher, [self._entry(17, 18, '0')]),
        ])

        self.assertFalse(conflicts)

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
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.subject.id),
        ])
        other_template = self.env['ems.attendance_template'].search([
            ('teacher_id', '=', self.teacher.id), ('subject_id', '=', self.other_subject.id),
        ])
        self.assertEqual(template.attendance_schedule_ids.mapped('start_time'), [9])
        self.assertEqual(other_template.attendance_schedule_ids.mapped('start_time'), [17])
