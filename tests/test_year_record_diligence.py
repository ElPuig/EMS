# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import Form, TransactionCase

from .common import create_level_study, create_role_user, next_student_id


class TestYearRecordDiligence(TransactionCase):
    """The diligence wizard: the only write path into a closed academic file (issue #493)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].create({'start': 2088, 'end': 2089})
        cls.level, cls.study = create_level_study(cls, 'DLG', level={'name': 'Diligence Level'},
                                                  study={'code': 'DLGSTD', 'acronym': 'DLG',
                                                         'name': 'Diligence Study'})
        # Subject 1 is internal only (the English module of the real case); subject 3 carries a
        # work placement weight, so a correction on it leaves the final pending.
        cls.subject1 = cls.env['ems.subject'].create({
            'code': 'DLGSUB1', 'acronym': 'DLG1', 'name': 'Diligence Subject 1',
            'study_ids': [(4, cls.study.id)]})
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'DLGSUB2', 'acronym': 'DLG2', 'name': 'Diligence Subject 2',
            'study_ids': [(4, cls.study.id)]})
        cls.subject3 = cls.env['ems.subject'].create({
            'code': 'DLGSUB3', 'acronym': 'DLG3', 'name': 'Diligence Subject 3',
            'study_ids': [(4, cls.study.id)]})
        cls.outcome3a = cls.env['ems.outcome'].create({
            'code': 'DLGSUB3_01RA', 'acronym': 'RA1', 'name': 'Outcome 3A',
            'subject_id': cls.subject3.id})
        cls.outcome3b = cls.env['ems.outcome'].create({
            'code': 'DLGSUB3_02RA', 'acronym': 'RA2', 'name': 'Outcome 3B',
            'subject_id': cls.subject3.id})
        # The teaching plan of subject 3 is what an "add a missing subject" diligence reads.
        cls.planning3 = cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject3.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [
                (0, 0, {'outcome_id': cls.outcome3a.id, 'ponderation': 50.0}),
                (0, 0, {'outcome_id': cls.outcome3b.id, 'ponderation': 50.0}),
            ]})

        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_diligence')
        cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_hos_diligence')
        cls.teacher = create_role_user(cls, 'teacher', 'test_teacher_diligence')

    # --- fixtures ------------------------------------------------------------

    def _record(self, academic_result='partial'):
        """A closed course of a student: subject 1 failed on two of its three outcomes (6/4/4,
        so the internal grade is capped at 4) and subject 2 passed - the shape of the real case
        this wizard was built for."""
        student = self.env['res.partner'].create({
            'name': 'Diligence Student', 'contact_type': 'student',
            'student_id': next_student_id()})
        return self.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': self.course.id,
            'study_id': self.study.id, 'study_name': self.study.display_name,
            'academic_result': academic_result,
            'subject_record_ids': [
                (0, 0, {
                    'subject_id': self.subject1.id, 'subject_name': self.subject1.display_name,
                    'internal_weight': 100.0, 'external_weight': 0.0,
                    'internal_grade': 4, 'final_grade': 4, 'has_final': True, 'state': 'failed',
                    'outcome_record_ids': [
                        (0, 0, {'outcome_name': 'RA1', 'weight': 40.0,
                                'final_score': 6, 'final_is_scored': True}),
                        (0, 0, {'outcome_name': 'RA2', 'weight': 30.0,
                                'final_score': 4, 'final_is_scored': True}),
                        (0, 0, {'outcome_name': 'RA3', 'weight': 30.0,
                                'final_score': 4, 'final_is_scored': True}),
                    ]}),
                (0, 0, {
                    'subject_id': self.subject2.id, 'subject_name': self.subject2.display_name,
                    'internal_weight': 100.0, 'external_weight': 0.0,
                    'internal_grade': 7, 'final_grade': 7, 'has_final': True, 'state': 'passed',
                    'outcome_record_ids': [
                        (0, 0, {'outcome_name': 'RA1', 'weight': 100.0,
                                'final_score': 7, 'final_is_scored': True}),
                    ]}),
            ]})

    def _failed_subject(self, record):
        return record.subject_record_ids.filtered(
            lambda subject_record: subject_record.subject_id == self.subject1)

    def _form(self, record, user=None, operation='correct'):
        """The wizard exactly as the web client drives it (view spec and onchains included)."""
        Wizard = self.env['ems.year_record_diligence_wizard']
        if user:
            Wizard = Wizard.with_user(user)
        form = Form(Wizard.with_context(default_record_id=record.id),
                    view='ems.view_year_record_diligence_wizard_form')
        form.operation = operation
        form.resolution = 'Reviewed and resolved as passed.'
        return form

    def _pass_failing_outcomes(self, form):
        """What the secretariat types in: a 5 on every outcome the diligence resolves."""
        for index in range(len(form.line_ids)):
            with form.line_ids.edit(index) as line:
                if line.previous_score < 5:
                    line.score = 5

    # --- correcting a subject ------------------------------------------------

    def test_correct_turns_a_failed_subject_into_a_passed_one(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        form = self._form(record)
        form.subject_record_id = subject_record
        self.assertEqual(len(form.line_ids), 3)
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        # (6*40 + 5*30 + 5*30) / 100 = 5.4, rounded half up and no longer capped at 4.
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.internal_grade, 5)
        self.assertEqual(subject_record.final_grade, 5)
        self.assertTrue(subject_record.has_final)
        self.assertEqual(subject_record.outcome_record_ids.mapped('final_score'), [6, 5, 5])

    def test_correct_preview_matches_what_gets_written(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        form = self._form(record)
        form.subject_record_id = subject_record
        self._pass_failing_outcomes(form)
        wizard = form.save()
        preview = (wizard.preview_internal_grade, wizard.preview_state,
                   wizard.preview_final_grade, wizard.preview_has_final, wizard.proposed_result)
        wizard.action_apply()
        self.assertEqual(preview, (subject_record.internal_grade, subject_record.state,
                                   subject_record.final_grade, subject_record.has_final,
                                   record.academic_result))

    def test_correct_updates_the_course_result(self):
        record = self._record()
        form = self._form(record)
        form.subject_record_id = self._failed_subject(record)
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        self.assertEqual(record.academic_result, 'full')

    def test_correct_leaves_the_course_result_alone_when_not_asked(self):
        record = self._record()
        form = self._form(record)
        form.subject_record_id = self._failed_subject(record)
        self._pass_failing_outcomes(form)
        form.update_result = False
        form.save().action_apply()
        self.assertEqual(record.academic_result, 'partial')

    def test_correct_keeps_a_result_the_grades_do_not_decide(self):
        # 'repeating' and 'withdrawn' come from the exit and the destination enrollment, not
        # from the grades: a diligence on a subject cannot resolve them.
        for result in ('repeating', 'withdrawn'):
            record = self._record(academic_result=result)
            form = self._form(record)
            form.subject_record_id = self._failed_subject(record)
            self._pass_failing_outcomes(form)
            form.save().action_apply()
            self.assertEqual(record.academic_result, result)

    def test_correct_stamps_the_diligence_on_the_subject(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        form = self._form(record, user=self.secretary)
        form.subject_record_id = subject_record
        self._pass_failing_outcomes(form)
        form.diligence_date = date(2088, 6, 30)
        form.save().action_apply()
        self.assertEqual(subject_record.diligence_date, date(2088, 6, 30))
        self.assertEqual(subject_record.diligence_user_id, self.secretary)
        self.assertEqual(subject_record.diligence_note, 'Reviewed and resolved as passed.')

    def test_correct_logs_the_detail_in_the_student_chatter(self):
        record = self._record()
        before = len(record.student_id.message_ids)
        form = self._form(record)
        form.subject_record_id = self._failed_subject(record)
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        messages = record.student_id.message_ids
        self.assertEqual(len(messages) - before, 1)
        body = messages[0].body
        self.assertIn('Reviewed and resolved as passed.', body)
        self.assertIn('RA2: 4 → 5', body)
        self.assertIn('RA3: 4 → 5', body)
        self.assertIn(self.subject1.display_name, body)

    def test_correct_without_any_change_is_rejected(self):
        record = self._record()
        form = self._form(record)
        form.subject_record_id = self._failed_subject(record)
        with self.assertRaises(UserError):
            form.save().action_apply()

    def test_correct_leaves_the_final_pending_while_the_placement_is_not_graded(self):
        record = self._record()
        subject_record = self.env['ems.student.year_record.subject'].create({
            'record_id': record.id, 'subject_id': self.subject3.id,
            'subject_name': self.subject3.display_name,
            'internal_weight': 90.0, 'external_weight': 10.0, 'state': 'failed',
            'outcome_record_ids': [
                (0, 0, {'outcome_name': 'RA1', 'weight': 50.0,
                        'final_score': 4, 'final_is_scored': True}),
                (0, 0, {'outcome_name': 'RA2', 'weight': 50.0,
                        'final_score': 6, 'final_is_scored': True}),
            ]})
        form = self._form(record)
        form.subject_record_id = subject_record
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        # Passed on its outcomes, but the final still waits for the work placement grade.
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.internal_grade, 6)
        self.assertFalse(subject_record.has_final)
        self.assertTrue(subject_record.final_pending)

    def test_correct_clears_a_frozen_override(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        subject_record.is_overridden = True
        form = self._form(record)
        form.subject_record_id = subject_record
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        self.assertFalse(subject_record.is_overridden)

    def test_an_outcome_left_ungraded_keeps_the_subject_failed(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        subject_record.outcome_record_ids[2].final_is_scored = False
        form = self._form(record)
        form.subject_record_id = subject_record
        with form.line_ids.edit(1) as line:
            line.score = 5
        form.save().action_apply()
        self.assertEqual(subject_record.state, 'failed')

    # --- adding a missing subject --------------------------------------------

    def test_add_a_missing_subject_from_its_teaching_plan(self):
        record = self._record()
        form = self._form(record, operation='add')
        form.subject_id = self.subject3
        # Weights and outcomes come from the teaching plan of the record's study.
        self.assertEqual(form.internal_weight, 90.0)
        self.assertEqual(form.external_weight, 10.0)
        self.assertEqual(len(form.line_ids), 2)
        for index in range(2):
            with form.line_ids.edit(index) as line:
                line.score = 7
        form.save().action_apply()
        added = record.subject_record_ids.filtered(
            lambda subject_record: subject_record.subject_id == self.subject3)
        self.assertEqual(added.state, 'passed')
        self.assertEqual(added.internal_grade, 7)
        self.assertEqual(added.outcome_record_ids.mapped('weight'), [50.0, 50.0])
        self.assertEqual(added.diligence_note, 'Reviewed and resolved as passed.')

    def test_add_only_offers_subjects_the_record_does_not_have(self):
        record = self._record()
        wizard = self.env['ems.year_record_diligence_wizard'].create({
            'record_id': record.id, 'resolution': 'x'})
        self.assertIn(self.subject3, wizard.available_subject_ids)
        self.assertNotIn(self.subject1, wizard.available_subject_ids)
        self.assertNotIn(self.subject2, wizard.available_subject_ids)

    def test_add_without_a_subject_is_rejected(self):
        record = self._record()
        wizard = self.env['ems.year_record_diligence_wizard'].create({
            'record_id': record.id, 'operation': 'add', 'resolution': 'x'})
        with self.assertRaises(UserError):
            wizard.action_apply()

    # --- removing a subject --------------------------------------------------

    def test_remove_a_subject_and_recompute_the_course_result(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        form = self._form(record, operation='remove')
        form.subject_record_id = subject_record
        form.save().action_apply()
        self.assertFalse(subject_record.exists())
        self.assertEqual(record.subject_record_ids.subject_id, self.subject2)
        # Only the passed subject is left.
        self.assertEqual(record.academic_result, 'full')

    def test_remove_logs_the_subject_in_the_student_chatter(self):
        record = self._record()
        form = self._form(record, operation='remove')
        form.subject_record_id = self._failed_subject(record)
        form.save().action_apply()
        self.assertIn(self.subject1.display_name, record.student_id.message_ids[0].body)

    # --- who may sign a diligence --------------------------------------------

    def test_the_secretariat_may_apply_a_diligence(self):
        record = self._record()
        form = self._form(record, user=self.secretary)
        form.subject_record_id = self._failed_subject(record)
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        self.assertEqual(self._failed_subject(record).state, 'passed')

    def test_the_head_of_studies_may_apply_a_diligence(self):
        record = self._record()
        form = self._form(record, user=self.head_of_studies)
        form.subject_record_id = self._failed_subject(record)
        self._pass_failing_outcomes(form)
        form.save().action_apply()
        self.assertEqual(self._failed_subject(record).state, 'passed')

    def test_a_teacher_may_not_apply_a_diligence(self):
        record = self._record()
        # The ACL stops a teacher at the wizard itself, before the defensive role check even
        # gets a chance to run.
        with self.assertRaises(AccessError):
            self.env['ems.year_record_diligence_wizard'].with_user(self.teacher).create({
                'record_id': record.id, 'subject_record_id': self._failed_subject(record).id,
                'resolution': 'x'}).action_apply()
        self.assertEqual(self._failed_subject(record).state, 'failed')

    # --- the recomputation itself --------------------------------------------

    def test_recompute_uses_the_same_formula_as_the_live_grades(self):
        record = self._record()
        subject_record = self._failed_subject(record)
        subject_record.outcome_record_ids[1].final_score = 5
        subject_record.outcome_record_ids[2].final_score = 5
        subject_record._recompute_from_outcomes()
        self.assertEqual(
            subject_record.internal_grade,
            self.env['ems.grade_subject_line']._internal_from_outcomes([(6, 40.0), (5, 30.0), (5, 30.0)]))

    def test_grade_based_result_of_an_empty_record(self):
        record = self.env['ems.student.year_record'].create({
            'student_id': self._record().student_id.id,
            'course_id': self.env['ems.course'].create({'start': 2090, 'end': 2091}).id,
            'academic_result': 'partial'})
        self.assertEqual(record.grade_based_result(), 'partial')
