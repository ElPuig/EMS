from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_level_study_group, create_role_employee, create_role_user, force_user_language_to_english


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

    def test_only_mine_filter_tour(self):
        # Issue #503: the list defaults to "Show only mine" (subjects the logged-in user
        # personally teaches), removable to see every planning - see planning_tour.js.
        level, study, group = create_level_study_group(
            self, 'PLNTM',
            level={'name': 'Test Level (Planning Only Mine Tour)'},
            study={'code': 'PLNTM001', 'name': 'Test Study (Planning Only Mine Tour)', 'date': date.today()},
        )
        subject_taught = self.env['ems.subject'].create({
            'code': 'PLNTM01', 'acronym': 'PLTA', 'name': 'Only Mine Taught Subject',
            'study_ids': [(4, study.id)],
        })
        subject_other = self.env['ems.subject'].create({
            'code': 'PLNTM02', 'acronym': 'PLTO', 'name': 'Only Mine Other Subject',
            'study_ids': [(4, study.id)],
        })
        outcome_taught = self.env['ems.outcome'].create({
            'code': 'PLNTM01_01RA', 'acronym': 'RA1', 'name': 'Outcome', 'subject_id': subject_taught.id,
        })
        outcome_other = self.env['ems.outcome'].create({
            'code': 'PLNTM02_01RA', 'acronym': 'RA1', 'name': 'Outcome', 'subject_id': subject_other.id,
        })
        self.env['ems.planning'].create({
            'study_id': study.id, 'subject_id': subject_taught.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome_taught.id, 'ponderation': 100.0})],
        })
        self.env['ems.planning'].create({
            'study_id': study.id, 'subject_id': subject_other.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome_other.id, 'ponderation': 100.0})],
        })

        # Head of Studies, not a plain teacher: a teacher's OWN read access
        # (rule_planning_teacher_own_subjects) is already limited to taught subjects, so
        # removing the UI filter would change nothing for them. The point of this filter is
        # rule_planning_hos_all's wider access (issue #503) - HOS/DHOS can see every planning,
        # defaulted down to their own taught ones, with an easy way back to everything.
        hos_user = create_role_user(self, 'head_of_studies', 'test_hos_planning_only_mine')
        hos_employee = create_role_employee(self, hos_user)
        self.env['ems.teaching'].create({
            'teacher_id': hos_employee.id, 'group_id': group.id, 'subject_id': subject_taught.id,
        })

        self.start_tour("/odoo", "ems_planning_only_mine_filter", login="test_hos_planning_only_mine")
