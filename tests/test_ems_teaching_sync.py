from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestTeachingSyncFromSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TTSF', level={'name': 'Test Level (Teaching Sync)'}, study={
            'code': 'TTSF001', 'name': 'Test Study (Teaching Sync)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TTSF001',
            'acronym': 'TTSF',
            'name': 'Test Subject (Teaching Sync)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.group_b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Teaching Sync)',
            'employee_type': 'teacher',
        })

    def test_creates_new_teaching_from_entries(self):
        entries = [{'subject_id': self.subject.id, 'group_ids': [self.group_a.id]}]

        self.env['ems.teaching'].sync_from_schedule(self.teacher, entries)

        teaching = self.env['ems.teaching'].search([
            ('teacher_id', '=', self.teacher.id),
            ('subject_id', '=', self.subject.id),
            ('group_id', '=', self.group_a.id),
        ])
        self.assertTrue(teaching)

    def test_removes_teaching_no_longer_in_entries(self):
        self.env['ems.teaching'].sync_from_schedule(self.teacher, [
            {'subject_id': self.subject.id, 'group_ids': [self.group_a.id]},
        ])

        self.env['ems.teaching'].sync_from_schedule(self.teacher, [
            {'subject_id': self.subject.id, 'group_ids': [self.group_b.id]},
        ])

        remaining = self.env['ems.teaching'].search([('teacher_id', '=', self.teacher.id)])
        self.assertEqual(remaining.group_id, self.group_b)

    def test_keeps_unchanged_teaching_record(self):
        self.env['ems.teaching'].sync_from_schedule(self.teacher, [
            {'subject_id': self.subject.id, 'group_ids': [self.group_a.id]},
        ])
        teaching_before = self.env['ems.teaching'].search([('teacher_id', '=', self.teacher.id)])

        self.env['ems.teaching'].sync_from_schedule(self.teacher, [
            {'subject_id': self.subject.id, 'group_ids': [self.group_a.id]},
        ])
        teaching_after = self.env['ems.teaching'].search([('teacher_id', '=', self.teacher.id)])

        self.assertEqual(teaching_before, teaching_after)

    def test_empty_entries_removes_all_teaching(self):
        self.env['ems.teaching'].sync_from_schedule(self.teacher, [
            {'subject_id': self.subject.id, 'group_ids': [self.group_a.id]},
        ])

        self.env['ems.teaching'].sync_from_schedule(self.teacher, [])

        remaining = self.env['ems.teaching'].search([('teacher_id', '=', self.teacher.id)])
        self.assertFalse(remaining)
