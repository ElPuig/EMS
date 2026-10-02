# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestGroupReferenceSpace(TransactionCase):
    """Issue #458: ems.group.space_id (the group's reference classroom) follows the group's own
    teaching schedule automatically - the room of its tutorship, or, for a group with no tutorship
    in its schedule (e.g. a reinforcement group), the room it spends the most teaching hours in.
    Still editable by hand (the working-schedules import wizard falls back on it for any block
    imported without a room), and an automatic update never moves the group's other classes the
    way a manual edit does (issue #405's _propagate_classroom_change)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TGRS', level={'name': 'Test Level (Group Reference Space)'}, study={
            'code': 'TGRS001', 'name': 'Test Study (Group Reference Space)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGRS001', 'acronym': 'TGRS', 'name': 'Test Subject (Group Reference Space)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.tutorship = cls.env['ems.subject'].create({
            'code': 'TGRS002', 'acronym': 'TGRST', 'name': 'Test Tutorship (Group Reference Space)',
            'study_ids': [(6, 0, [cls.study.id])], 'is_tutorship': True,
        })
        cls.space_a, cls.space_b, cls.space_c, cls.space_old = cls.env['ems.space'].create([{
            'code': code, 'name': name,
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        } for code, name in (
            ('TGRS-A', 'Test Space A (Group Reference Space)'),
            ('TGRS-B', 'Test Space B (Group Reference Space)'),
            ('TGRS-C', 'Test Space C (Group Reference Space)'),
            ('TGRS-OLD', 'Test Old Space (Group Reference Space)'),
        )])

    def _group(self, space=None):
        return self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': space.id if space else False,
        })

    def _block(self, group, space, weekday='0', hour_from=9.0, hour_to=10.0, subject=None, teaching=True):
        """A teaching block ('resource.calendar.attendance') with its matching, already-synced
        'ems.attendance_schedule' line - same fixture shape as TestGroupClassroomChange's own.
        A FRESH teacher per call, so several blocks for the same group never collide against
        ems.attendance_template's (teacher, subject, group) uniqueness. 'teaching=False' creates a
        bare non-teaching block instead (no subject, no template/schedule)."""
        self._teacher_count = getattr(self, '_teacher_count', 0) + 1
        teacher = self.env['hr.employee'].create({
            'name': f'Test Teacher {self._teacher_count} (Group Reference Space)',
            'employee_type': 'teacher',
        })
        if not teaching:
            return self.env['resource.calendar.attendance'].create({
                'calendar_id': teacher.resource_calendar_id.id, 'name': 'Test Guard Duty (Group Reference Space)',
                'dayofweek': weekday, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
                'group_ids': [group.id], 'space_id': space.id,
            })
        subject = subject or self.subject
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher.id])], 'study_ids': [(6, 0, [self.study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': weekday,
            'start_time': hour_from, 'end_time': hour_to, 'space_id': space.id,
        })
        return self.env['resource.calendar.attendance'].create({
            'calendar_id': teacher.resource_calendar_id.id, 'name': f"{teacher.name}: {subject.name}",
            'dayofweek': weekday, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            'group_ids': [group.id], 'subject_id': subject.id, 'space_id': space.id,
            'attendance_schedule_id': schedule.id,
        })

    def test_tutorship_room_wins_over_most_hours(self):
        group = self._group(self.space_old)
        self._block(group, self.space_a, weekday='0', hour_from=9.0, hour_to=14.0)  # 5h
        self._block(group, self.space_b, weekday='1', hour_from=9.0, hour_to=10.0, subject=self.tutorship)  # 1h
        self.assertEqual(group.space_id, self.space_b)

    def test_without_tutorship_most_hours_wins(self):
        group = self._group(self.space_old)
        self._block(group, self.space_a, weekday='0', hour_from=9.0, hour_to=11.0)  # 2h
        self._block(group, self.space_b, weekday='1', hour_from=9.0, hour_to=14.0)  # 5h
        self._block(group, self.space_c, weekday='2', hour_from=9.0, hour_to=10.0)  # 1h
        self.assertEqual(group.space_id, self.space_b)

    def test_tie_break_by_name_then_id(self):
        group = self._group(self.space_old)
        self._block(group, self.space_b, weekday='0', hour_from=9.0, hour_to=12.0)
        self._block(group, self.space_a, weekday='1', hour_from=9.0, hour_to=12.0)  # tied, but "A" < "B"
        self.assertEqual(group.space_id, self.space_a)

    def test_group_without_schedule_keeps_manual_room(self):
        group = self._group(self.space_old)
        group._sync_reference_space()
        self.assertEqual(group.space_id, self.space_old)

    def test_ignores_non_teaching_blocks(self):
        group = self._group(self.space_old)
        self._block(group, self.space_a, hour_from=9.0, hour_to=13.0, teaching=False)
        self.assertEqual(group.space_id, self.space_old)

    def test_automatic_update_does_not_move_other_classes(self):
        group = self._group(self.space_a)
        lesson = self._block(group, self.space_a, weekday='0', hour_from=9.0, hour_to=14.0)
        self._block(group, self.space_b, weekday='1', hour_from=9.0, hour_to=10.0, subject=self.tutorship)
        self.assertEqual(group.space_id, self.space_b)
        self.assertEqual(lesson.space_id, self.space_a)
        self.assertFalse(lesson.space_pending_group_sync)

    def test_moving_tutorship_updates_reference_room(self):
        group = self._group(self.space_old)
        tutorship = self._block(group, self.space_a, weekday='1', subject=self.tutorship)
        self.assertEqual(group.space_id, self.space_a)
        tutorship.space_id = self.space_c
        self.assertEqual(group.space_id, self.space_c)

    def test_removing_tutorship_falls_back_to_most_hours(self):
        group = self._group(self.space_old)
        self._block(group, self.space_a, weekday='0', hour_from=9.0, hour_to=14.0)
        tutorship = self._block(group, self.space_b, weekday='1', subject=self.tutorship)
        self.assertEqual(group.space_id, self.space_b)
        tutorship.unlink()
        self.assertEqual(group.space_id, self.space_a)

    def test_archiving_calendar_recomputes(self):
        group = self._group(self.space_old)
        self._block(group, self.space_a, weekday='0', hour_from=9.0, hour_to=14.0)
        tutorship = self._block(group, self.space_b, weekday='1', subject=self.tutorship)
        self.assertEqual(group.space_id, self.space_b)
        tutorship.calendar_id.active = False
        self.assertEqual(group.space_id, self.space_a)

    def test_manual_edit_still_propagates_and_sticks(self):
        group = self._group(self.space_old)
        lesson = self._block(group, self.space_a, weekday='0', hour_from=9.0, hour_to=14.0)
        tutorship = self._block(group, self.space_a, weekday='1', subject=self.tutorship)
        self.assertEqual(group.space_id, self.space_a)

        group.space_id = self.space_c

        self.assertEqual(group.space_id, self.space_c)
        self.assertEqual(lesson.space_id, self.space_c)
        self.assertEqual(tutorship.space_id, self.space_c)
