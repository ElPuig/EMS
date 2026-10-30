from datetime import date

from odoo.tests.common import HttpCase, tagged

from odoo.addons.ems.models.employees.working_schedule import subject_block_name

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestWorkingScheduleMultiGroupTour(HttpCase):
    """Regression tour for issue "unable to setup multiple groups when editing a schedule
    manually": resource.calendar.attendance.group_ids is a real Many2many (a join_session slot -
    one teacher running an identical session for two different groups at once, e.g. an optional
    subject combining two official groups in the same room - genuinely needs more than one), but
    the Schedule tab's edit widget only ever kept the FIRST group on a card, both on load and on
    save. Exercises the real interactive flow via the widget's native multi-select group picker -
    a clean upgrade.sh and passing TransactionCase tests prove none of this on their own, since
    neither renders anything in a real browser."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TWSMG',
            level={'name': 'Test Level (Working Schedule Multi Group Tour)'},
            study={'code': 'TWSMG001', 'name': 'Test Study (Working Schedule Multi Group Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWSMG001', 'acronym': 'TWSMG', 'name': 'Multi Group Tour Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TWSMG-A', 'name': 'Test Space (Working Schedule Multi Group Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.group_a = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSMGA', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Multi Group Tour Group A', 'space_id': cls.space.id,
        })
        cls.group_b = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSMGB', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Multi Group Tour Group B', 'space_id': cls.space.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Multi Group Tour Teacher', 'employee_type': 'teacher',
        })

    def test_working_schedule_multi_group_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_working_schedule_multi_group", login="admin", watch=True)
        self.start_tour("/odoo", "ems_working_schedule_multi_group", login="admin")

        calendar = self.teacher.resource_calendar_id
        monday_rows = calendar.attendance_ids.filtered(lambda attendance: attendance.dayofweek == '0')
        self.assertEqual(len(monday_rows), 1)
        self.assertEqual(set(monday_rows.group_ids.ids), {self.group_a.id, self.group_b.id})
        # The Schedule tab names it in the import's format (issue #723).
        self.assertEqual(monday_rows.name, subject_block_name(self.subject, self.group_a | self.group_b, monday_rows.topic))

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher.id), ('active', '=', True),
        ])
        self.assertEqual(len(template), 1)
        self.assertEqual(set(template.group_ids.ids), {self.group_a.id, self.group_b.id})
