from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestWorkingScheduleSplitPeriodTour(HttpCase):
    """See plans/calendar_driven_attendance_templates.md's "Mid-course subject handoff"
    refinement: the same weekday/time slot on a teacher's calendar can now hold two different
    subjects across the year, each scoped by its own date_from/date_to (resource.calendar.
    attendance). Exercises the real interactive flow via the Schedule tab's grid widget's
    per-day CARDS (2026-08-11 redesign, replacing an earlier shared-row "Split" button) - a
    clean upgrade.sh and passing TransactionCase tests prove none of this on their own, since
    neither renders anything in a real browser."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TWSSP',
            level={'name': 'Test Level (Working Schedule Split Period Tour)'},
            study={'code': 'TWSSP001', 'name': 'Test Study (Working Schedule Split Period Tour)', 'date': date.today()},
        )
        cls.subject_a = cls.env['ems.subject'].create({
            'code': 'TWSSP001', 'acronym': 'TWSSPA', 'name': 'Split Tour Subject A',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.subject_b = cls.env['ems.subject'].create({
            'code': 'TWSSP002', 'acronym': 'TWSSPB', 'name': 'Split Tour Subject B',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TWSSP-A', 'name': 'Test Space (Working Schedule Split Period Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSSPA', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Split Tour Group A', 'space_id': cls.space.id,
        })
        cls.group_b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSSPB', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Split Tour Group B', 'space_id': cls.space.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Split Period Tour Teacher', 'employee_type': 'teacher',
        })

    def test_working_schedule_split_period_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_working_schedule_split_period", login="admin", watch=True)
        self.start_tour("/odoo", "ems_working_schedule_split_period", login="admin")

        calendar = self.teacher.resource_calendar_id
        monday_rows = calendar.attendance_ids.filtered(lambda attendance: attendance.dayofweek == '0')
        self.assertEqual(len(monday_rows), 2)
        first = monday_rows.filtered(lambda attendance: attendance.subject_id == self.subject_a)
        second = monday_rows.filtered(lambda attendance: attendance.subject_id == self.subject_b)
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(first.hour_from, second.hour_from)
        self.assertEqual(first.hour_to, second.hour_to)
        self.assertEqual(first.date_from, date(2026, 9, 1))
        self.assertEqual(first.date_to, date(2027, 2, 28))
        self.assertEqual(second.date_from, date(2027, 3, 1))
        self.assertEqual(second.date_to, date(2027, 7, 1))

        templates = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('active', '=', True),
        ])
        self.assertEqual(len(templates), 2)
