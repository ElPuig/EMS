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

    def _create_template(self, teacher, space, start_date=date(2026, 1, 1), end_date=date(2026, 6, 30)):
        return self.env['ems.attendance_template'].create({
            'teacher_id': teacher.id,
            'level_id': self.level.id,
            'study_id': self.study.id,
            'subject_id': self.subject.id,
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
        template1 = self._create_template(self.teacher_a, self.space_a)
        self._create_schedule(template1, self.space_a, weekday='0', start_time=9.0, end_time=10.0)

        template2 = self._create_template(self.teacher_b, self.space_b)
        with self.assertRaises(ValidationError):
            self._create_schedule(template2, self.space_a, weekday='0', start_time=9.5, end_time=10.5)

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

    def _entry(self, hour_from=9, hour_to=10, dayofweek='0'):
        return {
            'subject_id': self.subject.id,
            'group_ids': [self.group.id],
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
