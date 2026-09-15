from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study, next_student_id


class TestStudentSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Student Schedule)',
            'login': 'test_teacher_for_student_schedule',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary User (Student Schedule)',
            'login': 'test_secretary_for_student_schedule',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.level, cls.study = create_level_study(cls, 'TSSL', level={'name': 'Test Level (Student Schedule)'}, study={
            'code': 'TSSL001', 'name': 'Test Study (Student Schedule)', 'date': date.today(),
        })
        cls.subject_main = cls.env['ems.subject'].create({
            'code': 'TSSL001', 'acronym': 'TSSLM', 'name': 'Test Main Subject (Student Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.subject_elective = cls.env['ems.subject'].create({
            'code': 'TSSL002', 'acronym': 'TSSLE', 'name': 'Test Elective Subject (Student Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.subject_not_enrolled = cls.env['ems.subject'].create({
            'code': 'TSSL003', 'acronym': 'TSSLN', 'name': 'Test Not-Enrolled Subject (Student Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TSSL-A', 'name': 'Test Space (Student Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        # A DIFFERENT physical room from 'cls.space' - the elective group's own sessions need to
        # be bookable at the exact same time as the main group's (that's the whole point of these
        # tests), which two sessions in the SAME room could never be (ems.attendance_schedule's own
        # room-booking overlap constraint rejects that regardless of which students attend either).
        cls.space2 = cls.env['ems.space'].create({
            'code': 'TSSL-B', 'name': 'Test Space 2 (Student Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.main_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TSSL', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'space_id': cls.space.id, 'shift': 'morning',
        })
        cls.elective_group = cls.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'TSSL-ELECTIVE', 'space_id': cls.space2.id, 'shift': 'morning',
        })
        cls.non_teaching_br = cls.env.ref('ems.non_teaching_br')
        cls.level_framework = cls.env['resource.calendar'].create({
            'name': 'Test Level Framework (Student Schedule)',
            'is_framework': True, 'level_id': cls.level.id, 'full_time_required_hours': 24,
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.level_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 11, 'hour_to': 11.5, 'day_period': 'morning', 'non_teaching': cls.non_teaching_br.id,
        })
        cls.teacher_a = cls.env['hr.employee'].create({'name': 'Test Teacher A (Student Schedule)', 'employee_type': 'teacher'})
        cls.teacher_b = cls.env['hr.employee'].create({'name': 'Test Teacher B (Student Schedule)', 'employee_type': 'teacher'})

        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student (Student Schedule)', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': cls.main_group.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student.id, 'group_id': cls.main_group.id, 'subject_id': cls.subject_main.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student.id, 'group_id': cls.elective_group.id, 'subject_id': cls.subject_elective.id,
        })

    def _new_calendar(self, teacher, name):
        calendar = self.env['resource.calendar'].create({'name': name})
        teacher.resource_calendar_id = calendar
        return calendar

    def test_schedule_attendance_ids_only_includes_enrolled_subjects(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Enrolled Subject)')
        # 'apply_schedule_changes' replaces a calendar's WHOLE weekly state in one call (see its
        # own docstring) - both cells must be passed together, not as two separate calls, or the
        # second call would wipe out the first.
        calendar_a.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
            },
            # Taught to the SAME group but never enrolled by this student - must not leak in.
            {
                'dayofweek': '1', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject_not_enrolled.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLN',
            },
        ])

        teaching_entries = self.student.schedule_attendance_ids.filtered('subject_id')
        self.assertEqual(teaching_entries.mapped('subject_id'), self.subject_main)

    def test_schedule_attendance_ids_ignores_archived_calendar_even_under_active_test_false(self):
        """Real incident, 2026-09-10 (issue #408 follow-up): a real student's Schedule tab showed
        a duplicated, out-of-date copy of several subjects alongside the real ones, each pair
        genuinely overlapping - traced to this tab being opened from ems.action_student_kanban,
        whose own context sets active_test=False (so archived/withdrawn students still show up
        in that list) - a context that then leaked into this compute too, resurfacing a stale/
        archived calendar's own never-deleted (only archived) attendance rows from a past course
        transition's calendar rollover. The compute must force active_test=True on its own
        searches regardless of the surrounding context."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Archived)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM (stale)',
        }])
        calendar_a.action_archive()
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Current)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '1', 'hour_from': 11, 'hour_to': 12, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM (current)',
        }])

        student = self.student.with_context(active_test=False)
        teaching_entries = student.schedule_attendance_ids.filtered('subject_id')

        self.assertEqual(teaching_entries.mapped('employee_id'), self.teacher_b)

    def test_schedule_attendance_ids_aggregates_across_groups(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Cross-group)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Cross-group)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9.5, 'hour_to': 10.25, 'day_period': 'morning',
            'subject_id': self.subject_elective.id, 'group_ids': [self.elective_group.id], 'name': 'TSSL: TSSLE',
        }])

        teaching_entries = self.student.schedule_attendance_ids.filtered('subject_id')
        self.assertEqual(len(teaching_entries), 2)
        self.assertEqual(set(teaching_entries.mapped('subject_id')), {self.subject_main, self.subject_elective})
        self.assertEqual(set(teaching_entries.mapped('employee_id')), {self.teacher_a, self.teacher_b})

    def test_get_schedule_report_lines_keeps_overlapping_entries_as_distinct_periods(self):
        """A student's own overlapping enrollments (main group 9:00-10:00, an elective through a
        different group 9:30-10:15) must both survive into the report lines as their own distinct
        periods - never merged/dropped just because their time ranges intersect (see CLAUDE.md's
        own warning that, unlike a group's or a teacher's schedule, a student's CAN overlap)."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Overlap)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Overlap)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9.5, 'hour_to': 10.25, 'day_period': 'morning',
            'subject_id': self.subject_elective.id, 'group_ids': [self.elective_group.id], 'name': 'TSSL: TSSLE',
        }])

        lines = self.student.get_schedule_report_lines()

        time_labels = {line['time_label'] for line in lines}
        self.assertIn('09:00-10:00', time_labels)
        self.assertIn('09:30-10:15', time_labels)

    def test_get_subject_teachers_summary_across_groups(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Summary)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Summary)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 11.5, 'hour_to': 12.5, 'day_period': 'morning',
            'subject_id': self.subject_elective.id, 'group_ids': [self.elective_group.id], 'name': 'TSSL: TSSLE',
        }])

        summary = self.student.get_subject_teachers_summary()

        self.assertEqual(len(summary), 2)
        by_subject = {row['subject']: row['teachers'] for row in summary}
        self.assertEqual(by_subject[self.subject_main.display_name], self.teacher_a.display_name)
        self.assertEqual(by_subject[self.subject_elective.display_name], self.teacher_b.display_name)

    def test_get_subject_teachers_summary_includes_topic_in_label(self):
        """Issue #428: same underlying (subject, topic) grouping as
        TestGroupSchedule.test_get_subject_teachers_summary_separates_by_topic - a student's own
        aggregated schedule (across all their enrolled groups) must reflect the topic-qualified
        label too, not just a group's."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Topic Summary)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
            'topic': 'Angles',
        }])

        summary = self.student.get_subject_teachers_summary()

        by_subject = {row['subject']: row['teachers'] for row in summary}
        self.assertEqual(by_subject.get('%s - Angles' % self.subject_main.display_name), self.teacher_a.display_name)

    def test_break_derived_from_main_group_level(self):
        lines = self.student.get_schedule_report_lines()

        matching = [line for line in lines if line['time_label'] == '11:00-11:30']
        self.assertEqual(len(matching), 1)
        monday_cell = matching[0]['cells'][0]
        self.assertEqual(len(monday_cell['blocks']), 1)
        self.assertFalse(monday_cell['blocks'][0]['entries'].subject_id)
        self.assertEqual(monday_cell['blocks'][0]['entries'].non_teaching, self.non_teaching_br)

    def test_break_not_shown_without_main_group(self):
        no_group_student = self.env['res.partner'].create({
            'name': 'Test Student No Group (Student Schedule)', 'contact_type': 'student', 'student_id': next_student_id(),
        })

        self.assertFalse(no_group_student._get_break_entries())
        self.assertEqual(no_group_student.get_schedule_report_lines(), [])

    def test_non_student_contact_has_no_schedule(self):
        family_contact = self.env['res.partner'].create({
            'name': 'Test Family Contact (Student Schedule)', 'contact_type': 'family',
        })

        self.assertFalse(family_contact.schedule_attendance_ids)

    def test_empty_student_without_enrollments_returns_no_lines(self):
        unenrolled_student = self.env['res.partner'].create({
            'name': 'Test Unenrolled Student (Student Schedule)', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': self.main_group.id,
        })

        # Still picks up the main group's derived break (level+shift are enough on their own),
        # but no teaching entries at all since there are no enrollments to match against.
        self.assertFalse(unenrolled_student.schedule_attendance_ids.filtered('subject_id'))
        self.assertEqual(unenrolled_student.get_subject_teachers_summary(), [])

    def test_teacher_can_read_student_schedule(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Teacher Access)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
        }])

        student = self.student.with_user(self.teacher_user)
        self.assertTrue(student.schedule_attendance_ids)
        self.assertTrue(student.get_schedule_report_lines())

    def test_secretary_can_read_student_schedule(self):
        student = self.student.with_user(self.secretary_user)
        self.assertEqual(student.get_schedule_report_lines(), student.get_schedule_report_lines())

    def test_report_student_schedule_renders(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject_main.id, 'group_ids': [self.main_group.id], 'name': 'TSSL: TSSLM',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (PDF)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9.5, 'hour_to': 10.25, 'day_period': 'morning',
            'subject_id': self.subject_elective.id, 'group_ids': [self.elective_group.id], 'name': 'TSSL: TSSLE',
        }])

        content, content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_student_schedule', [self.student.id])

        self.assertTrue(content)
        self.assertIn(content_type, ('pdf', 'html'))
        self.assertIn(self.teacher_a.name.encode(), content)
        self.assertIn(self.teacher_b.name.encode(), content)
