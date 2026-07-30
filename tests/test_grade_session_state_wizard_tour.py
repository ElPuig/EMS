from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestGradeSessionStateWizardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TGSSW',
            level={'name': 'Test Level (Grade Session State Wizard Tour)'},
            study={'code': 'TGSSW001', 'name': 'Test Study (Grade Session State Wizard Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGSSW001', 'acronym': 'TGSSW', 'name': 'Test Subject (Grade Session State Wizard Tour)',
            'study_ids': [(4, cls.study.id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Grade Session State Wizard Tour)', 'employee_type': 'teacher',
        })
        cls.grade_session = cls.env['ems.grade_session'].create({
            'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '1',
            'teacher_id': cls.teacher_employee.id,
        })

    def test_grade_session_state_wizard_apply_tour(self):
        self.assertEqual(self.grade_session.state, 'open')

        self.start_tour("/odoo", "ems_grade_session_state_wizard_apply", login="admin")

        self.assertEqual(self.grade_session.state, 'board')
