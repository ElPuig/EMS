from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_level_study_group


class TestPlanningAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Planning)',
            'login': 'test_teacher_for_planning',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Planning) Employee', 'user_id': cls.teacher_user.id, 'employee_type': 'teacher',
        })

        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TPL', level={'name': 'Test Planning Level'}, study={
            'code': 'TPLSTD', 'acronym': 'TPS', 'name': 'Test Planning Study',
        })

        cls.subject_taught = cls._make_subject('TPLSB1', 'TPB1', 'Taught Subject')
        cls.subject_other = cls._make_subject('TPLSB2', 'TPB2', 'Other Subject')
        cls.planning_taught = cls._make_planning(cls.subject_taught)
        cls.planning_other = cls._make_planning(cls.subject_other)

        # The teacher only teaches subject_taught.
        cls.env['ems.teaching'].create({
            'teacher_id': cls.teacher_employee.id, 'group_id': cls.group.id, 'subject_id': cls.subject_taught.id,
        })

    @classmethod
    def _make_subject(cls, code, acronym, name):
        subject = cls.env['ems.subject'].create({
            'code': code, 'acronym': acronym, 'name': name, 'study_ids': [(4, cls.study.id)],
        })
        cls.env['ems.outcome'].create({
            'code': code + '_01RA', 'acronym': 'RA1', 'name': 'Outcome', 'subject_id': subject.id,
        })
        return subject

    @classmethod
    def _make_planning(cls, subject):
        return cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': subject.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': subject.outcome_ids[0].id, 'ponderation': 100.0})],
        })

    def test_teacher_sees_only_taught_plannings(self):
        visible = self.env['ems.planning'].with_user(self.teacher_user).search([
            ('id', 'in', [self.planning_taught.id, self.planning_other.id]),
        ])
        self.assertIn(self.planning_taught, visible)
        self.assertNotIn(self.planning_other, visible)

    def test_teacher_cannot_write_planning(self):
        with self.assertRaises(AccessError):
            self.planning_taught.with_user(self.teacher_user).write({
                'internal_ponderation': 80.0, 'external_ponderation': 20.0,
            })

    def test_teacher_cannot_read_untaught_planning(self):
        with self.assertRaises(AccessError):
            self.planning_other.with_user(self.teacher_user).read(['name'])

    def test_admin_can_write_planning(self):
        self.planning_taught.write({'internal_ponderation': 80.0, 'external_ponderation': 20.0})
        self.assertEqual(self.planning_taught.internal_ponderation, 80.0)


class TestPlanningLogic(TransactionCase):
    """The model's own business logic: check_ponderation's two sum-to-100 rules
    (outcomes, internal/external), _onchange_planning_outcome_ids' even split with
    remainder handling, and _compute_name — none of it exercised by
    TestPlanningAccess above."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TPLL', level={'name': 'Test Planning Logic Level'}, study={
            'code': 'TPLL001', 'name': 'Test Planning Logic Study',
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TPLLSUB', 'acronym': 'TPLS', 'name': 'Test Planning Logic Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.subject_no_outcomes = cls.env['ems.subject'].create({
            'code': 'TPLLSUB2', 'acronym': 'TPLS2', 'name': 'Test Planning Logic Subject No Outcomes',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.outcome1 = cls.env['ems.outcome'].create({
            'code': 'TPLLSUB_01RA', 'acronym': 'RA1', 'name': 'Outcome 1', 'subject_id': cls.subject.id,
        })
        cls.outcome2 = cls.env['ems.outcome'].create({
            'code': 'TPLLSUB_02RA', 'acronym': 'RA2', 'name': 'Outcome 2', 'subject_id': cls.subject.id,
        })
        cls.outcome3 = cls.env['ems.outcome'].create({
            'code': 'TPLLSUB_03RA', 'acronym': 'RA3', 'name': 'Outcome 3', 'subject_id': cls.subject.id,
        })

    def test_compute_name(self):
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        self.assertEqual(planning.name, "%s  %s" % (self.study.acronym, self.subject.display_name))

    def test_outcome_ponderation_must_sum_100(self):
        with self.assertRaises(ValidationError):
            self.env['ems.planning'].create({
                'study_id': self.study.id, 'subject_id': self.subject.id,
                'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 50.0})],
            })

    def test_internal_external_ponderation_must_sum_100(self):
        with self.assertRaises(ValidationError):
            self.env['ems.planning'].create({
                'study_id': self.study.id, 'subject_id': self.subject.id,
                'internal_ponderation': 90.0, 'external_ponderation': 5.0,
                'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
            })

    def test_planning_outcome_ponderation_out_of_range_raises(self):
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        with self.assertRaises(ValidationError):
            planning.planning_outcome_ids.write({'ponderation': 150.0})

    def test_onchange_splits_evenly_with_remainder_on_last(self):
        planning = self.env['ems.planning'].new({'study_id': self.study.id, 'subject_id': self.subject.id})
        planning._onchange_planning_outcome_ids()
        ponderations = planning.planning_outcome_ids.mapped('ponderation')
        self.assertEqual(len(ponderations), 3)
        self.assertEqual(ponderations[0], 33.33)
        self.assertEqual(ponderations[1], 33.33)
        self.assertEqual(ponderations[2], 33.34)
        self.assertEqual(round(sum(ponderations), 2), 100)

    def test_onchange_with_no_outcomes_does_not_crash(self):
        """Regression test: count = len(outcomes) was used as a divisor with no
        zero-guard — selecting a subject with no learning outcomes yet (a
        perfectly normal state for a newly created subject) raised
        ZeroDivisionError. Fixed in this DTON pass."""
        planning = self.env['ems.planning'].new({
            'study_id': self.study.id, 'subject_id': self.subject_no_outcomes.id,
        })
        planning._onchange_planning_outcome_ids()
        self.assertFalse(planning.planning_outcome_ids)

    def test_onchange_clears_previous_outcomes_on_subject_change(self):
        planning = self.env['ems.planning'].new({'study_id': self.study.id, 'subject_id': self.subject.id})
        planning._onchange_planning_outcome_ids()
        self.assertEqual(len(planning.planning_outcome_ids), 3)
        planning.subject_id = self.subject_no_outcomes
        planning._onchange_planning_outcome_ids()
        self.assertFalse(planning.planning_outcome_ids)
