from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


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
