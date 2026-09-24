from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_level_study_group, create_role_user


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

        # A Head of Studies teaches nothing at all here - any visibility they get over
        # planning_other must come from their role, not from ems.teaching (issue #503).
        cls.hos_user = create_role_user(cls, 'head_of_studies', 'test_hos_for_planning')

        # A second HOS who DOES teach subject_taught - needed to exercise is_own_subject's
        # True/False split: rule_planning_teacher_own_subjects already hides planning_other
        # from a plain teacher entirely, so only a role that can read BOTH plannings (HOS, via
        # rule_planning_hos_all) can tell "mine" apart from "not mine, but still visible".
        cls.hos_teaching_user = create_role_user(cls, 'head_of_studies', 'test_hos_teaching_for_planning')
        hos_teaching_employee = cls.env['hr.employee'].create({
            'name': 'Test HOS Teaching (Planning) Employee', 'user_id': cls.hos_teaching_user.id, 'employee_type': 'teacher',
        })
        cls.env['ems.teaching'].create({
            'teacher_id': hos_teaching_employee.id, 'group_id': cls.group.id, 'subject_id': cls.subject_taught.id,
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

    def test_hos_sees_every_planning_not_just_taught(self):
        # Issue #503: Head of Studies/Deputy must see ALL plannings, not only the ones tied
        # to subjects they personally teach via ems.teaching (this HOS teaches nothing here).
        visible = self.env['ems.planning'].with_user(self.hos_user).search([
            ('id', 'in', [self.planning_taught.id, self.planning_other.id]),
        ])
        self.assertIn(self.planning_taught, visible)
        self.assertIn(self.planning_other, visible)

    def test_hos_can_write_any_planning(self):
        self.planning_other.with_user(self.hos_user).write({
            'internal_ponderation': 70.0, 'external_ponderation': 30.0,
        })
        self.assertEqual(self.planning_other.internal_ponderation, 70.0)

    def test_hos_cannot_unlink_planning(self):
        with self.assertRaises(AccessError):
            self.planning_other.with_user(self.hos_user).unlink()

    def test_is_own_subject_computed_per_teaching(self):
        # hos_teaching_user can read BOTH plannings (rule_planning_hos_all) but only teaches
        # subject_taught, so is_own_subject must tell them apart even though access alone does not.
        plannings = (self.planning_taught | self.planning_other).with_user(self.hos_teaching_user)
        self.assertTrue(plannings.browse(self.planning_taught.id).is_own_subject)
        self.assertFalse(plannings.browse(self.planning_other.id).is_own_subject)

    def test_only_mine_filter_searches_own_subject(self):
        found = self.env['ems.planning'].with_user(self.teacher_user).search([
            ('id', 'in', [self.planning_taught.id, self.planning_other.id]),
            ('is_own_subject', '=', True),
        ])
        self.assertEqual(found, self.planning_taught)


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
        cls.other_course = cls.env['ems.course'].create({'start': 2030, 'end': 2031})

    def test_compute_name(self):
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        expected_course = self.env.company.current_course_id
        self.assertEqual(planning.name, "%s  %s (%s)" % (
            self.study.acronym, self.subject.display_name, expected_course.name))

    def test_compute_name_without_course(self):
        # Transient state right after a fresh install's data-file create, before post_init_hook
        # backfills course_id - _compute_name must not crash on an empty course_id.
        planning = self.env['ems.planning'].with_context(install_mode=True).create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': False,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        self.assertFalse(planning.course_id)
        self.assertEqual(planning.name, "%s  %s" % (self.study.acronym, self.subject.display_name))

    def test_course_id_defaults_to_current_course(self):
        planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        self.assertEqual(planning.course_id, self.env.company.current_course_id)

    def test_course_id_required_outside_install_mode(self):
        with self.assertRaises(ValidationError):
            self.env['ems.planning'].create({
                'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': False,
                'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
            })

    def test_course_id_not_required_under_install_mode(self):
        # The escape hatch a fresh install's data-file load relies on (see check_course_id_required).
        planning = self.env['ems.planning'].with_context(install_mode=True).create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': False,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        self.assertFalse(planning.course_id)

    def test_same_study_subject_different_course_allowed(self):
        self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        other_course_planning = self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.other_course.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        self.assertEqual(other_course_planning.course_id, self.other_course)

    def test_same_study_subject_same_course_blocked(self):
        self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.other_course.id,
            'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
        })
        with self.assertRaises(Exception):
            self.env['ems.planning'].create({
                'study_id': self.study.id, 'subject_id': self.subject.id, 'course_id': self.other_course.id,
                'planning_outcome_ids': [(0, 0, {'outcome_id': self.outcome1.id, 'ponderation': 100.0})],
            })

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

    def test_custom_data_records_are_frozen_against_future_upgrades(self):
        # data/custom/ccff/ems.planning*.csv seeds the centre's grading-ponderation template
        # only once: a centre rebalancing its own weights through the app (e.g. after a new
        # learning outcome is added to the shared curriculum catalog) is 'living' data, not
        # config this repo's CSV should keep re-pushing on every upgrade (issue #503 follow-up,
        # found the hard way - see plans/ems_planning_outcome_ponderation_over_100.md). Mirrors
        # test_group.py's own test for the same mechanism.
        for model in ('ems.planning', 'ems.planning_outcome'):
            custom_data = self.env['ir.model.data'].sudo().search([
                ('module', '=', '__import__'), ('model', '=', model),
            ])
            self.assertTrue(custom_data, "no __import__-owned %s found - fixture assumption broken" % model)
            self.assertTrue(all(custom_data.mapped('noupdate')), "%s rows not frozen" % model)
