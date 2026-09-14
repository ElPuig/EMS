from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_user


class TestGroupSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Group Schedule)',
            'login': 'test_teacher_for_group_schedule',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary User (Group Schedule)',
            'login': 'test_secretary_for_group_schedule',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.level, cls.study = create_level_study(cls, 'TGSL', level={'name': 'Test Level (Group Schedule)'}, study={
            'code': 'TGSL001', 'name': 'Test Study (Group Schedule)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGSL001',
            'acronym': 'TGSL',
            'name': 'Test Subject (Group Schedule)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TGSL-A',
            'name': 'Test Space (Group Schedule)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1,
            'acronym': 'TGSL',
            'level_id': cls.level.id,
            'study_id': cls.study.id,
            'space_id': cls.space.id,
            'shift': 'morning',
        })
        cls.non_teaching_br = cls.env.ref('ems.non_teaching_br')
        cls.level_framework = cls.env['resource.calendar'].create({
            'name': 'Test Level Framework (Group Schedule)',
            'is_framework': True,
            'level_id': cls.level.id,
            'full_time_required_hours': 24,
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.level_framework.id,
            'name': 'BR: Break',
            'dayofweek': '0',
            'hour_from': 11,
            'hour_to': 11.5,
            'day_period': 'morning',
            'non_teaching': cls.non_teaching_br.id,
        })
        cls.teacher_a = cls.env['hr.employee'].create({
            'name': 'Test Teacher A (Group Schedule)',
            'employee_type': 'teacher',
        })
        cls.teacher_b = cls.env['hr.employee'].create({
            'name': 'Test Teacher B (Group Schedule)',
            'employee_type': 'teacher',
        })

    def _new_calendar(self, teacher, name):
        calendar = self.env['resource.calendar'].create({'name': name})
        teacher.resource_calendar_id = calendar
        return calendar

    def test_schedule_attendance_ids_aggregates_across_teachers(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Aggregation)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Aggregation)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])

        teaching_entries = self.group.schedule_attendance_ids.filtered('subject_id')
        self.assertEqual(len(teaching_entries), 2)
        self.assertEqual(set(teaching_entries.mapped('employee_id')), {self.teacher_a, self.teacher_b})

    def test_schedule_attendance_ids_ignores_archived_calendar_even_under_active_test_false(self):
        """Same real incident as res.partner (student)'s own version of this test (issue #408
        follow-up, 2026-09-10): this compute must force active_test=True on its own searches
        regardless of the surrounding context - a caller opening the group from a context that
        disabled active_test for an unrelated reason (e.g. wanting archived records visible in a
        list) must not resurface a stale/archived calendar's own never-deleted attendance rows as
        if they were still part of the group's CURRENT schedule."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Archived)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL (stale)',
        }])
        calendar_a.action_archive()
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Current)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '1', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL (current)',
        }])

        group = self.group.with_context(active_test=False)
        teaching_entries = group.schedule_attendance_ids.filtered('subject_id')

        self.assertEqual(teaching_entries.mapped('employee_id'), self.teacher_b)

    def test_get_schedule_report_lines_co_teaching_is_a_single_block(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Co-teaching)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Co-teaching)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])

        lines = self.group.get_schedule_report_lines()

        matching = [line for line in lines if line['time_label'] == '09:00-10:00']
        self.assertEqual(len(matching), 1)
        monday_cell = matching[0]['cells'][0]
        self.assertEqual(len(monday_cell['blocks']), 1)
        self.assertEqual(monday_cell['blocks'][0]['entries'].mapped('employee_id'), self.teacher_a | self.teacher_b)

    def test_get_schedule_report_lines_same_slot_different_topics_are_separate_blocks(self):
        """Issue #428, real regression found live (2026-09-11): unlike plain co-teaching (same
        subject, no topic - see the test above, correctly ONE merged block), two teachers can
        genuinely share the exact same subject/group/slot while teaching different topics (e.g.
        FP Basica's MP 3161, split by language) - found on a real teacher's calendar where a
        second, unrelated teacher happened to share the exact same subject+group+hour. Before the
        fix, '_report_color_key' grouped by subject alone, so the two entries silently merged into
        ONE block, showing only one of the two teachers/topics (chosen arbitrarily by entry
        order) - the other's topic was visible in get_subject_teachers_summary() but not in the
        grid itself."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Same Slot Topics)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
            'topic': 'Castella',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Same Slot Topics)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
            'topic': 'Catala',
        }])

        lines = self.group.get_schedule_report_lines()

        matching = [line for line in lines if line['time_label'] == '08:00-09:00']
        self.assertEqual(len(matching), 1)
        monday_cell = matching[0]['cells'][0]
        self.assertEqual(len(monday_cell['blocks']), 2)
        teachers_by_block = {block['entries'].employee_id for block in monday_cell['blocks']}
        self.assertEqual(teachers_by_block, {self.teacher_a, self.teacher_b})

    def test_get_subject_teachers_summary_lists_co_teachers(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Summary)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Summary)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])

        summary = self.group.get_subject_teachers_summary()

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['subject'], self.subject.display_name)
        self.assertIn(self.teacher_a.display_name, summary[0]['teachers'])
        self.assertIn(self.teacher_b.display_name, summary[0]['teachers'])

    def test_get_subject_teachers_summary_separates_by_topic(self):
        """Issue #428: the same subject split into several topics (e.g. FP Basica's MP 3161:
        Castella/Catala/Angles), each taught by a different teacher, must show up as distinct
        rows - not merged under one 'subject' row the way plain co-teaching (same subject, no
        topic) correctly is (see the co-teachers test above)."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Topic Summary)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
            'topic': 'Castella',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Topic Summary)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 11, 'hour_to': 12, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
            'topic': 'Catala',
        }])

        summary = self.group.get_subject_teachers_summary()

        self.assertEqual(len(summary), 2)
        rows_by_subject = {row['subject']: row['teachers'] for row in summary}
        self.assertEqual(rows_by_subject.get('%s - Castella' % self.subject.display_name), self.teacher_a.display_name)
        self.assertEqual(rows_by_subject.get('%s - Catala' % self.subject.display_name), self.teacher_b.display_name)

    def test_break_derived_from_level_framework(self):
        lines = self.group.get_schedule_report_lines()

        matching = [line for line in lines if line['time_label'] == '11:00-11:30']
        self.assertEqual(len(matching), 1)
        monday_cell = matching[0]['cells'][0]
        self.assertEqual(len(monday_cell['blocks']), 1)
        self.assertFalse(monday_cell['blocks'][0]['entries'].subject_id)
        self.assertEqual(monday_cell['blocks'][0]['entries'].non_teaching, self.non_teaching_br)
        self.assertTrue(monday_cell['blocks'][0]['entries'].non_teaching_is_break)

    def test_get_schedule_report_lines_excludes_entries_outside_shift_window(self):
        afternoon_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGSL4', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.space.id, 'shift': 'afternoon',
        })
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Shift Window)')
        calendar_a.apply_schedule_changes([
            {
                'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                'subject_id': self.subject.id, 'group_ids': [afternoon_group.id], 'name': 'TGSL: TGSL4 (morning, out of window)',
            },
            {
                'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
                'subject_id': self.subject.id, 'group_ids': [afternoon_group.id], 'name': 'TGSL: TGSL4 (afternoon, in window)',
            },
        ])

        lines = afternoon_group.get_schedule_report_lines()

        time_labels = {line['time_label'] for line in lines}
        self.assertNotIn('09:00-10:00', time_labels)
        self.assertIn('16:00-17:00', time_labels)

    def test_break_not_shown_without_level(self):
        reinforcement_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-TGSL', 'space_id': self.space.id, 'shift': 'morning',
        })

        self.assertFalse(reinforcement_group._get_break_entries())
        self.assertEqual(reinforcement_group.get_schedule_report_lines(), [])

    def test_break_not_shown_without_shift(self):
        no_shift_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGSL2', 'level_id': self.level.id, 'study_id': self.study.id, 'space_id': self.space.id,
        })

        self.assertFalse(no_shift_group._get_break_entries())

    def test_empty_group_schedule_returns_no_lines(self):
        empty_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGSL3',
            'level_id': self.env['ems.level'].create({'acronym': 'TGSL3', 'name': 'Test Level 3 (Group Schedule)'}).id,
            'study_id': self.env['ems.study'].create({
                'code': 'TGSL003', 'acronym': 'TGSL3', 'name': 'Test Study 3 (Group Schedule)',
                'date': date.today(), 'deprecated': False,
                'level_id': self.env['ems.level'].search([('acronym', '=', 'TGSL3')], limit=1).id,
            }).id,
            'space_id': self.space.id,
        })

        self.assertFalse(empty_group.schedule_attendance_ids)
        self.assertEqual(empty_group.get_schedule_report_lines(), [])
        self.assertEqual(empty_group.get_subject_teachers_summary(), [])

    def test_teacher_can_read_group_schedule(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Teacher Access)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])

        group = self.group.with_user(self.teacher_user)
        self.assertTrue(group.schedule_attendance_ids)
        self.assertTrue(group.get_schedule_report_lines())
        self.assertTrue(group.get_subject_teachers_summary())

    def test_secretary_can_read_group_schedule(self):
        group = self.group.with_user(self.secretary_user)
        self.assertEqual(group.get_schedule_report_lines(), group.get_schedule_report_lines())

    def test_report_group_schedule_renders(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (PDF)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])

        content, content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_group_schedule', [self.group.id])

        self.assertTrue(content)
        self.assertIn(content_type, ('pdf', 'html'))
        self.assertIn(self.teacher_a.name.encode(), content)
        self.assertIn(self.teacher_b.name.encode(), content)
        self.assertNotIn(b'Tutor:', content)

    def test_report_group_schedule_shows_tutor(self):
        tutor = self.env['hr.employee'].create({'name': 'Test Tutor (Group Schedule)', 'employee_type': 'teacher'})
        tutored_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGSL5', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': self.space.id, 'tutor_id': tutor.id,
        })

        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_group_schedule', [tutored_group.id])

        self.assertIn(b'Tutor:', content)
        self.assertIn(tutor.name.encode(), content)

    def test_report_group_schedule_shows_reference_classroom(self):
        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_group_schedule', [self.group.id])

        self.assertIn(b'Reference classroom:', content)
        self.assertIn(self.space.name.encode(), content)

    def test_report_group_schedule_hides_reference_classroom_when_unset(self):
        no_space_group = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'REF-TGSL-NOSPACE', 'shift': 'morning',
        })

        content, _content_type = self.env['ir.actions.report']._render_qweb_pdf('ems.report_group_schedule', [no_space_group.id])

        self.assertNotIn(b'Reference classroom:', content)

    def test_can_edit_schedule_true_for_department_chief(self):
        """Issue #446 - same gate as 'hr.employee.can_edit_schedule' (Edit/Import/New on the
        teacher's own tab), mirrored here to drive the group form's own inline edit affordance."""
        chief_user = create_role_user(self, 'department_chief', 'test_dept_chief_group_schedule')
        self.assertTrue(self.group.with_user(chief_user).can_edit_schedule)

    def test_can_edit_schedule_false_for_plain_teacher(self):
        self.assertFalse(self.group.with_user(self.teacher_user).can_edit_schedule)

    def _other_space(self, code, name):
        return self.env['ems.space'].create({
            'code': code, 'name': name,
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })

    def test_update_topic_and_relocate_writes_topic_only(self):
        """Issue #446 - 'topic' is free text with no collision semantics: a plain write, even
        with no 'space_id' passed at all (falsy - "leave the room untouched")."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Update Topic Only)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        block = self.group.schedule_attendance_ids.filtered('subject_id')

        block.update_topic_and_relocate('New Topic', False)

        self.assertEqual(block.topic, 'New Topic')
        self.assertEqual(block.space_id, self.space)

    def test_update_topic_and_relocate_moves_room_without_conflict(self):
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Move Room)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        block = self.group.schedule_attendance_ids.filtered('subject_id')
        new_space = self._other_space('TGSL-MOVE', 'Test Space (Move Room)')

        block.update_topic_and_relocate(False, new_space.id)

        self.assertEqual(block.space_id, new_space)
        self.assertFalse(block.space_pending_group_sync)

    def test_update_topic_and_relocate_flags_pending_on_conflict(self):
        """Issue #446 - a collision NEVER blocks the edit: 'topic' still lands, the room stays
        put and gets flagged 'space_pending_group_sync' instead of raising, exactly like editing
        the same room from the colliding teacher's own calendar already does (issue #444)."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Conflict)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        block = self.group.schedule_attendance_ids.filtered('subject_id')
        new_space = self._other_space('TGSL-COLL', 'Test Space (Conflict)')
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGSL-OTH', 'level_id': self.level.id, 'study_id': self.study.id,
            'space_id': new_space.id, 'shift': 'morning',
        })
        calendar_c = self._new_calendar(self.teacher_b, 'Test Calendar C (Conflict, other side)')
        calendar_c.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [other_group.id], 'name': 'TGSL: TGSL-OTH',
            'space_id': new_space.id,
        }])

        block.update_topic_and_relocate('Conflicting Topic', new_space.id)

        self.assertEqual(block.topic, 'Conflicting Topic')
        self.assertEqual(block.space_id, self.space)
        self.assertTrue(block.space_pending_group_sync)
        self.assertEqual(block.pending_new_space_id, new_space)
        self.assertEqual(self.group.pending_classroom_conflict_count, 1)

    def test_update_topic_and_relocate_moves_every_co_teaching_block(self):
        """Issue #446 - a co-taught block (same subject/topic/slot) must move together: calling
        this on the whole visual block (both underlying resource.calendar.attendance rows, one
        per co-teacher) relocates both, never leaving one teacher's own calendar stale (exactly
        the desync bug 'relocate_or_flag_pending' was written to prevent, issue #444)."""
        calendar_a = self._new_calendar(self.teacher_a, 'Test Calendar A (Co-teaching Move)')
        calendar_a.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        calendar_b = self._new_calendar(self.teacher_b, 'Test Calendar B (Co-teaching Move)')
        calendar_b.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [self.group.id], 'name': 'TGSL: TGSL',
        }])
        blocks = self.group.schedule_attendance_ids.filtered('subject_id')
        self.assertEqual(len(blocks), 2)
        new_space = self._other_space('TGSL-COTEACH', 'Test Space (Co-teaching Move)')

        blocks.update_topic_and_relocate('Shared Topic', new_space.id)

        self.assertTrue(all(block.space_id == new_space for block in blocks))
        self.assertTrue(all(block.topic == 'Shared Topic' for block in blocks))
