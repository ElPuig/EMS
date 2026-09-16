from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestSpaceSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Space Schedule)',
            'login': 'test_teacher_for_space_schedule',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary User (Space Schedule)',
            'login': 'test_secretary_for_space_schedule',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.level, cls.study = create_level_study(cls, 'TSPL', level={'name': 'Test Level (Space Schedule)'}, study={
            'code': 'TSPL001', 'name': 'Test Study (Space Schedule)', 'date': date.today(),
        })
        cls.subject_main = cls.env['ems.subject'].create({
            'code': 'TSPL001', 'acronym': 'TSPLM', 'name': 'Test Main Subject (Space Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.subject_other = cls.env['ems.subject'].create({
            'code': 'TSPL002', 'acronym': 'TSPLO', 'name': 'Test Other Subject (Space Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        # The space under test, and a DIFFERENT room to prove the schedule is scoped by this
        # exact space, not by whichever room a block's group happens to default to.
        cls.space = cls.env['ems.space'].create({
            'code': 'TSPL-A', 'name': 'Test Space (Space Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.other_space = cls.env['ems.space'].create({
            'code': 'TSPL-B', 'name': 'Test Other Space (Space Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        # The group's own reference classroom is deliberately 'other_space', not 'space' - a
        # block explicitly booked into 'space' must still show up, proving the search really is
        # scoped by the block's own space_id, not by its group's default classroom.
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TSPL', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'space_id': cls.other_space.id, 'shift': 'morning',
        })
        cls.teacher_a = cls.env['hr.employee'].create({'name': 'Test Teacher A (Space Schedule)', 'employee_type': 'teacher'})
        cls.teacher_b = cls.env['hr.employee'].create({'name': 'Test Teacher B (Space Schedule)', 'employee_type': 'teacher'})

    def _new_calendar(self, teacher, name):
        calendar = self.env['resource.calendar'].create({'name': name})
        teacher.resource_calendar_id = calendar
        return calendar

    def test_schedule_attendance_ids_only_includes_this_space(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (This Space)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM',
        }])
        # Same group, same teacher's own calendar, but booked into the OTHER room - must not leak in.
        calendar_a.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
                'name': 'TSPL: TSPLM',
            },
            {
                'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject_other.id, 'group_ids': [self.group.id], 'space_id': self.other_space.id,
                'name': 'TSPL: TSPLO (other room)',
            },
        ])

        teaching_entries = self.space.schedule_attendance_ids.filtered('subject_id')
        self.assertEqual(teaching_entries.mapped('subject_id'), self.subject_main)
        self.assertFalse(self.other_space.schedule_attendance_ids.filtered(
            lambda attendance: attendance.subject_id == self.subject_main))

    def test_schedule_attendance_ids_ignores_archived_calendar_even_under_active_test_false(self):
        """Same class of incident already found on ems.group's/res.partner (student)'s own version
        of this compute (2026-09-10, issue #408 follow-up): a caller context that already set
        active_test=False for an unrelated reason must not resurrect a stale/archived calendar's
        own leftover attendance rows here."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Archived)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM (stale)',
        }])
        calendar_a.action_archive()
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Current)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '1', 'hour_from': 11, 'hour_to': 12, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM (current)',
        }])

        space = self.space.with_context(active_test=False)
        teaching_entries = space.schedule_attendance_ids.filtered('subject_id')

        self.assertEqual(teaching_entries.mapped('employee_id'), self.teacher_b)

    def test_get_schedule_report_lines_shows_both_shifts(self):
        """A room has no shift of its own (unlike a group/student) - both a morning and an
        afternoon booking must survive into the report lines, never filtered down to just one
        shift's hour window."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Morning)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Afternoon)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
            'subject_id': self.subject_other.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLO',
        }])

        time_labels = {line['time_label'] for line in self.space.get_schedule_report_lines()}
        self.assertIn('09:00-10:00', time_labels)
        self.assertIn('16:00-17:00', time_labels)

    def test_get_subject_teachers_summary(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Summary)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Summary)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 11.5, 'hour_to': 12.5, 'day_period': 'morning',
            'subject_id': self.subject_other.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLO',
        }])

        summary = self.space.get_subject_teachers_summary()

        self.assertEqual(len(summary), 2)
        by_subject = {row['subject']: row['teachers'] for row in summary}
        self.assertEqual(by_subject[self.subject_main.display_name], self.teacher_a.display_name)
        self.assertEqual(by_subject[self.subject_other.display_name], self.teacher_b.display_name)

    def test_empty_space_without_bookings_returns_no_lines(self):
        unused_space = self.env['ems.space'].create({
            'code': 'TSPL-C', 'name': 'Test Unused Space (Space Schedule)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })

        self.assertFalse(unused_space.schedule_attendance_ids)
        self.assertEqual(unused_space.get_schedule_report_lines(), [])
        self.assertEqual(unused_space.get_subject_teachers_summary(), [])

    def test_teacher_can_read_space_schedule(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Teacher Access)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM',
        }])

        space = self.space.with_user(self.teacher_user)
        self.assertTrue(space.schedule_attendance_ids)
        self.assertTrue(space.get_schedule_report_lines())

    def test_secretary_can_read_space_schedule(self):
        space = self.space.with_user(self.secretary_user)
        self.assertEqual(space.get_schedule_report_lines(), space.get_schedule_report_lines())

    def test_report_space_schedule_renders(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.group.id], 'space_id': self.space.id,
            'name': 'TSPL: TSPLM',
        }])

        content, content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_space_schedule', [self.space.id])

        self.assertTrue(content)
        self.assertIn(content_type, ('pdf', 'html'))
        self.assertIn(self.teacher_a.name.encode(), content)
