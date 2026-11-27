from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_user


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
        # The Head of Studies changes the states (issue #878), the least-privileged role allowed.
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'tour_hos_state_wizard')

    def test_grade_session_state_wizard_apply_tour(self):
        self.assertEqual(self.grade_session.state, 'open')

        self.start_tour("/odoo", "ems_grade_session_state_wizard_apply", login="tour_hos_state_wizard")

        self.assertEqual(self.grade_session.state, 'board')

    def test_grade_session_state_from_list_tour(self):
        # Issue #878: from the list's selection; the overlay used to stay forever once the wizard's
        # dialog closed, which the tour sees as a step that never finds its trigger.
        self.start_tour("/odoo/action-ems.action_grade_session_tree",
                        "ems_grade_session_state_from_list", login="tour_hos_state_wizard")
        self.assertEqual(self.grade_session.state, 'board')
