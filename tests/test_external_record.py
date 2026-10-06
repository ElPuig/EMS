# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import Form, TransactionCase

from .common import create_level_study, create_level_study_group, create_role_user, next_student_id


class TestExternalRecord(TransactionCase):
    """A course taken at another centre, added to the academic history from its academic
    certificate (issue #585): the record is opened by its own wizard and its modules are added,
    per learning outcome, through the grade review."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.past_course = Course.create({'start': 2080, 'end': 2081})
        cls.other_past_course = Course.create({'start': 2081, 'end': 2082})
        cls.current_course = Course.create({'start': 2082, 'end': 2083})
        cls.future_course = Course.create({'start': 2083, 'end': 2084})
        cls.env.company.current_course_id = cls.current_course

        cls.level, cls.study = create_level_study(cls, 'EXR', level={'name': 'External Record Level'},
                                                  study={'code': 'EXRSTD', 'acronym': 'EXR',
                                                         'name': 'External Record Study'})
        # A study with no teaching plan of learning outcomes (ESO and BTX today).
        cls.level_no_plan, cls.study_no_plan = create_level_study(cls, 'EXRN')
        # Module A carries a work placement weight, module B is internal only, and module C is
        # part of the study but has no teaching plan that course.
        cls.subject_a, cls.subject_b, cls.subject_c = [cls.env['ems.subject'].create({
            'code': f'EXRSUB{suffix}', 'acronym': f'EXR{suffix}',
            'name': f'External Record Subject {suffix}', 'study_ids': [(4, cls.study.id)],
        }) for suffix in 'ABC']
        cls.outcomes_a = [cls.env['ems.outcome'].create({
            'code': f'EXRSUBA_0{index}RA', 'acronym': f'RA{index}', 'name': f'Outcome A{index}',
            'subject_id': cls.subject_a.id}) for index in (1, 2)]
        cls.outcome_b = cls.env['ems.outcome'].create({
            'code': 'EXRSUBB_01RA', 'acronym': 'RA1', 'name': 'Outcome B1',
            'subject_id': cls.subject_b.id})
        cls.env['ems.planning'].create([{
            'study_id': cls.study.id, 'subject_id': cls.subject_a.id, 'course_id': cls.past_course.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id, 'ponderation': 50.0})
                                     for outcome in cls.outcomes_a],
        }, {
            'study_id': cls.study.id, 'subject_id': cls.subject_b.id, 'course_id': cls.past_course.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome_b.id, 'ponderation': 100.0})],
        }])

        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_external_record')
        cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_hos_external_record')
        cls.teacher = create_role_user(cls, 'teacher', 'test_teacher_external_record')

    def setUp(self):
        super().setUp()
        self.student = self.env['res.partner'].create({
            'name': 'External Record Student', 'contact_type': 'student',
            'student_id': next_student_id()})

    # --- fixtures ------------------------------------------------------------

    def _form(self, user=None):
        Wizard = self.env['ems.external_record_wizard']
        if user:
            Wizard = Wizard.with_user(user)
        return Form(Wizard.with_context(default_student_id=self.student.id),
                    view='ems.view_external_record_wizard_form')

    def _create(self, user=None):
        """What the secretariat fills in from the certificate's heading. Returns the record and
        the action the wizard answers with."""
        form = self._form(user)
        form.course_id = self.past_course
        form.study_id = self.study
        form.origin_centre_name = 'Institut Extern'
        form.origin_centre_code = '08000000'
        form.notes = 'Transfer of academic file.'
        action = form.save().action_create()
        record = self.env['ems.student.year_record'].search([('student_id', '=', self.student.id)])
        return record, action

    def _review_form(self, action, user=None):
        """The grade review the external record wizard hands over to, opened with that action's
        own context, as the web client does."""
        Wizard = self.env['ems.grade_review_wizard']
        if user:
            Wizard = Wizard.with_user(user)
        return Form(Wizard.with_context(**action['context']),
                    view='ems.view_grade_review_wizard_form')

    def _available_subjects(self, record):
        return self.env['ems.grade_review_wizard'].new(
            {'record_id': record.id, 'operation': 'add'}).available_subject_ids._origin

    def _type_grades(self, form, scores):
        for index, score in enumerate(scores):
            with form.line_ids.edit(index) as line:
                line.score = score

    # --- opening the record --------------------------------------------------

    def test_create_opens_an_external_record(self):
        record, _action = self._create(user=self.secretary)
        self.assertEqual(len(record), 1)
        self.assertTrue(record.is_external)
        self.assertEqual(record.course_id, self.past_course)
        self.assertEqual(record.study_id, self.study)
        self.assertEqual(record.study_name, self.study.display_name)
        self.assertEqual(record.level_id, self.level)
        self.assertEqual(record.origin_centre_name, 'Institut Extern')
        self.assertEqual(record.origin_centre_code, '08000000')
        self.assertFalse(record.group_id)
        self.assertFalse(record.subject_record_ids)

    def test_create_logs_it_in_the_student_chatter(self):
        self._create(user=self.secretary)
        body = self.student.message_ids[0].body
        self.assertIn('Institut Extern (08000000)', body)
        self.assertIn('Transfer of academic file.', body)

    def test_create_hands_over_to_the_grade_review_to_add_modules(self):
        record, action = self._create(user=self.secretary)
        self.assertEqual(action['res_model'], 'ems.grade_review_wizard')
        self.assertEqual(action['context']['default_record_id'], record.id)
        self.assertEqual(action['context']['default_operation'], 'add')
        self.assertIn('Institut Extern', action['context']['default_resolution'])

    def test_only_courses_already_over_and_not_in_the_history_are_offered(self):
        self.env['ems.student.year_record'].create({
            'student_id': self.student.id, 'course_id': self.other_past_course.id})
        offered = self.env['ems.external_record_wizard'].new(
            {'student_id': self.student.id}).available_course_ids._origin
        self.assertIn(self.past_course, offered)
        self.assertNotIn(self.other_past_course, offered)
        self.assertNotIn(self.current_course, offered)
        self.assertNotIn(self.future_course, offered)

    def test_only_studies_with_a_teaching_plan_that_course_are_offered(self):
        offered = self.env['ems.external_record_wizard'].new(
            {'student_id': self.student.id, 'course_id': self.past_course.id}).available_study_ids._origin
        self.assertIn(self.study, offered)
        self.assertNotIn(self.study_no_plan, offered)

    def test_a_course_already_in_the_history_is_rejected(self):
        self._create()
        wizard = self.env['ems.external_record_wizard'].create({
            'student_id': self.student.id, 'course_id': self.past_course.id,
            'study_id': self.study.id, 'origin_centre_name': 'Another one'})
        with self.assertRaises(UserError):
            wizard.action_create()

    def test_the_head_of_studies_may_add_one(self):
        # Read-only on the history otherwise: the wizard writes it with elevated rights.
        record, _action = self._create(user=self.head_of_studies)
        self.assertTrue(record.is_external)

    def test_a_teacher_may_not_add_one(self):
        with self.assertRaises(AccessError):
            self.env['ems.external_record_wizard'].with_user(self.teacher).create({
                'student_id': self.student.id, 'course_id': self.past_course.id,
                'study_id': self.study.id, 'origin_centre_name': 'Institut Extern'})
        wizard = self.env['ems.external_record_wizard'].create({
            'student_id': self.student.id, 'course_id': self.past_course.id,
            'study_id': self.study.id, 'origin_centre_name': 'Institut Extern'})
        with self.assertRaises(UserError):
            wizard.with_user(self.teacher).action_create()

    # --- adding its modules --------------------------------------------------

    def test_only_modules_with_a_teaching_plan_that_course_are_offered(self):
        record, _action = self._create()
        offered = self._available_subjects(record)
        self.assertEqual(offered, self.subject_a | self.subject_b)

    def test_add_a_module_per_learning_outcome(self):
        record, action = self._create(user=self.secretary)
        form = self._review_form(action, user=self.secretary)
        form.subject_id = self.subject_b
        self._type_grades(form, [8])
        form.save().action_apply()
        subject_record = record.subject_record_ids
        self.assertEqual(subject_record.subject_id, self.subject_b)
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.internal_grade, 8)
        self.assertEqual(subject_record.final_grade, 8)
        self.assertEqual(subject_record.outcome_record_ids.final_score, 8)
        self.assertEqual(subject_record.review_user_id, self.secretary)

    def test_a_module_without_its_placement_grade_stays_pending(self):
        record, action = self._create()
        form = self._review_form(action)
        form.subject_id = self.subject_a
        self._type_grades(form, [7, 6])
        form.save().action_apply()
        subject_record = record.subject_record_ids
        self.assertEqual(subject_record.state, 'passed')
        self.assertFalse(subject_record.has_final)
        self.assertTrue(subject_record.final_pending)
        # ...which is what makes the EM grading wizard offer it to the student's current tutor.
        self.assertIn(subject_record,
                      self.env['ems.em_grading_wizard']._pending_subject_records(self.student))

    def test_the_internal_grade_can_be_forced_to_the_certificates(self):
        record, action = self._create()
        form = self._review_form(action)
        form.subject_id = self.subject_a
        self._type_grades(form, [7, 6])
        form.preview_internal_grade = 6
        form.save().action_apply()
        self.assertEqual(record.subject_record_ids.internal_grade, 6)
        self.assertTrue(record.subject_record_ids.is_overridden)

    def test_apply_and_add_reopens_on_the_same_record_and_resolution(self):
        record, action = self._create()
        form = self._review_form(action)
        form.subject_id = self.subject_b
        form.review_date = date(2081, 7, 1)
        self._type_grades(form, [6])
        wizard = form.save()
        next_action = wizard.action_apply_and_add()
        self.assertEqual(next_action['context']['default_record_id'], record.id)
        self.assertEqual(next_action['context']['default_operation'], 'add')
        self.assertEqual(next_action['context']['default_resolution'], wizard.resolution)
        self.assertEqual(next_action['context']['default_review_date'], date(2081, 7, 1))
        # The module just added is no longer offered.
        self.assertEqual(self._available_subjects(record), self.subject_a)
        self.assertEqual(record.academic_result, 'full')

    # --- the rest of EMS leaves it alone --------------------------------------

    def test_the_generator_never_rewrites_it(self):
        record, action = self._create()
        form = self._review_form(action)
        form.subject_id = self.subject_b
        self._type_grades(form, [6])
        form.save().action_apply()
        _level, _study, group = create_level_study_group(self, 'EXRG')
        regenerated = self.env['ems.student.year_record'].generate_for_students(
            self.student, self.past_course, group=group)
        self.assertEqual(regenerated, record)
        self.assertTrue(record.is_external)
        self.assertEqual(record.subject_record_ids.subject_id, self.subject_b)
        self.assertFalse(record.group_id)

    def test_a_title_from_another_centre_is_not_a_title_of_this_centre(self):
        record, _action = self._create()
        record.title_obtained = True
        convalidation = self.env['ems.convalidation'].new({'student_id': self.student.id})
        self.assertFalse(convalidation.has_centre_title)
