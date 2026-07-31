from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestEmGradingWizardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'EGWT',
            level={'name': 'Test Level (EM Grading Wizard Tour)'},
            study={'code': 'EGWT001', 'name': 'Test Study (EM Grading Wizard Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'EGWT001', 'acronym': 'EGWT', 'name': 'EM Grading Wizard Tour Subject',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'EGWT001_01RA', 'acronym': 'RA1', 'name': 'EM Grading Wizard Tour Outcome',
            'subject_id': cls.subject.id,
        })
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome.id, 'ponderation': 100.0})],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'EmgwtStudent Test', 'firstname': 'EmgwtStudent', 'lastname': 'Test',
            'contact_type': 'student', 'main_group_id': cls.group.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
        })
        session = cls.env['ems.grade_session'].create({
            'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '1',
        })
        session.fill_students()
        cls.subject_line = session.grade_subject_line_ids.filtered(
            lambda line: line.student_id == cls.student)

    def test_em_grading_wizard_apply_tour(self):
        self.assertFalse(self.subject_line.external_is_scored)

        self.start_tour("/odoo", "ems_em_grading_wizard_apply", login="admin")

        self.assertTrue(self.subject_line.external_is_scored)
        self.assertEqual(self.subject_line.external_score, 7)
