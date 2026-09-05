from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestPlanningTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'PLNT',
            level={'name': 'Test Level (Planning Tour)'},
            study={'code': 'PLNT001', 'name': 'Test Study (Planning Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'PLNT001', 'acronym': 'PLNT', 'name': 'Planning Tour Subject',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'PLNT001_01RA', 'acronym': 'RA1', 'name': 'Planning Tour Outcome',
            'subject_id': cls.subject.id,
        })

    def test_planning_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_planning_crud", login="admin")

        planning = self.env['ems.planning'].search([
            ('study_id', '=', self.study.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(len(planning), 1)
        self.assertEqual(len(planning.planning_outcome_ids), 1)
        self.assertEqual(planning.planning_outcome_ids.outcome_id, self.outcome)
        self.assertEqual(planning.planning_outcome_ids.ponderation, 100.0)
