from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import Form, TransactionCase

from .common import create_level_study


class TestEmGradingWizard(TransactionCase):
    """The work placement (EM) grade is entered per group as a matrix: one row per student
    with a single EM grade (applied to every module of theirs with an external weight) and a
    "grade per module" switch that turns on one cell per module instead. Destinations: live
    grade lines of the current course and archived year records of previous courses whose
    final is still pending. All the wizard interactions go through odoo.tests.Form so the
    tests exercise the same onchange/save protocol as the web client (view field spec
    included) — the matrix widget edits exactly these lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].create({'start': 2096, 'end': 2097})
        cls.env.company.current_course_id = cls.course

        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor (EM)',
            'login': 'test_tutor_for_em_wizard',
            'groups_id': [(4, cls.env.ref('base.group_user').id),
                          (4, cls.env.ref('ems.group_tutor').id)],
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (EM) Employee',
            'user_id': cls.tutor_user.id,
            'employee_type': 'teacher',
        })

        # Curriculum: subject1 has a work placement (90/10), subject2 is internal-only.
        cls.level, cls.study = create_level_study(cls, 'EML', level={'name': 'EM Level'}, study={
            'code': 'EMSTD1', 'acronym': 'EMS', 'name': 'EM Study',
        })
        cls.subject1 = cls.env['ems.subject'].create({
            'code': 'EMSUB1', 'acronym': 'EM1', 'name': 'EM Subject 1',
            'study_ids': [(4, cls.study.id)],
        })
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'EMSUB2', 'acronym': 'EM2', 'name': 'EM Subject 2',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome1 = cls.env['ems.outcome'].create({
            'code': 'EMSUB1_01RA', 'acronym': 'RA1', 'name': 'EM Outcome 1',
            'subject_id': cls.subject1.id,
        })
        cls.outcome2 = cls.env['ems.outcome'].create({
            'code': 'EMSUB2_01RA', 'acronym': 'RA1', 'name': 'EM Outcome 2',
            'subject_id': cls.subject2.id,
        })
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject1.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome1.id, 'ponderation': 100.0})],
        })
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject2.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome2.id, 'ponderation': 100.0})],
        })

        cls.group = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id, 'shift': 'morning',
        })
        cls.other_group = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })

    # --- helpers -------------------------------------------------------------

    def _student(self, name, group=None):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student',
            'main_group_id': (group or self.group).id})

    def _enroll(self, student, subject, group=None):
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': (group or self.group).id,
            'subject_id': subject.id})

    def _session(self, subject, round="1", group=None):
        group = group or self.group
        session = self.env['ems.grade_session'].search([
            ('group_id', '=', group.id), ('subject_id', '=', subject.id),
            ('round', '=', round)], limit=1)
        session = session or self.env['ems.grade_session'].create({
            'group_id': group.id, 'subject_id': subject.id, 'round': round})
        session.fill_students()
        return session

    def _live_student(self, name='EM Student', score=6):
        """A student with both subjects graded in the current course (all RAs passed):
        subject1 carries a placement, subject2 does not."""
        student = self._student(name)
        self._enroll(student, self.subject1)
        self._enroll(student, self.subject2)
        for subject, outcome in ((self.subject1, self.outcome1), (self.subject2, self.outcome2)):
            session = self._session(subject)
            session.grade_outcome_line_ids.filtered(
                lambda line: line.student_id == student and line.outcome_id == outcome
            ).write({'score': score, 'is_scored': True})
        return student

    def _subject_line(self, student, subject):
        return self.env['ems.grade_subject_line'].search([
            ('student_id', '=', student.id),
            ('grade_session_id.subject_id', '=', subject.id)], limit=1)

    def _archived_subject(self, student, internal_grade=6, year=2095):
        """A previous-course year record whose subject1 is passed with the final still
        pending (the placement grade has not arrived yet)."""
        course = self.env['ems.course'].search([('start', '=', year)], limit=1) \
            or self.env['ems.course'].create({'start': year, 'end': year + 1})
        record = self.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': course.id,
            'study_id': self.study.id, 'group_id': self.group.id,
            'subject_record_ids': [(0, 0, {
                'subject_id': self.subject1.id, 'subject_name': self.subject1.display_name,
                'internal_weight': 90.0, 'external_weight': 10.0,
                'internal_grade': internal_grade, 'state': 'passed',
            })],
        })
        return record.subject_record_ids

    def _form(self, group=None, user=None):
        """The wizard exactly as the web client drives it (view spec included)."""
        Wizard = self.env['ems.em_grading_wizard']
        if user:
            Wizard = Wizard.with_user(user)
        form = Form(Wizard, view='ems.view_em_grading_wizard_form')
        form.group_id = group if group is not None else self.group
        return form

    def _grade_student(self, form, index, score):
        """The single EM grade of a student: applies to every module of theirs. Mirrors what
        the matrix widget writes when the EM grade cell of the row is filled in."""
        with form.student_line_ids.edit(index) as student_line:
            student_line.score = score
            student_line.to_apply = True

    def _grade_per_module(self, form, index):
        """Switch a student to per-module grading (the row's checkbox)."""
        with form.student_line_ids.edit(index) as student_line:
            student_line.per_module = True

    def _grade_module(self, form, index, score):
        """Fill in one module cell of the matrix."""
        with form.line_ids.edit(index) as line:
            line.score = score
            line.to_apply = True

    # --- line building (through the client protocol) --------------------------

    def test_only_subjects_with_external_weight(self):
        student = self._live_student()
        form = self._form()
        self.assertEqual(len(form.line_ids), 1)
        line = form.line_ids.edit(0)
        self.assertEqual(line.student_id, student)
        # The column header splits code and name (narrow columns in the matrix).
        self.assertEqual(line.subject_acronym, self.subject1.acronym)
        self.assertEqual(line.subject_name, self.subject1.name)
        self.assertEqual(line.source, 'live')
        self.assertEqual(line.internal_grade, 6)
        self.assertEqual(line.external_weight, 10.0)
        self.assertFalse(line.to_apply)
        # One student line, holding the single grade for all of that student's modules.
        self.assertEqual(len(form.student_line_ids), 1)
        student_line = form.student_line_ids.edit(0)
        self.assertEqual(student_line.student_id, student)
        self.assertEqual(student_line.module_count, 1)
        self.assertFalse(student_line.to_apply)
        self.assertFalse(student_line.per_module)

    def test_line_uses_last_round(self):
        self._live_student()
        session2 = self._session(self.subject1, round="2")
        wizard = self._form().save()
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.subject_line_id.grade_session_id, session2)

    def test_archived_pending_final_is_offered(self):
        student = self._student('EM Archived Student')
        self._enroll(student, self.subject1)
        subject_record = self._archived_subject(student)
        self.assertTrue(subject_record.final_pending)
        wizard = self._form().save()
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.source, 'history')
        self.assertEqual(wizard.line_ids.subject_record_id, subject_record)

    def test_archived_with_final_is_not_offered(self):
        student = self._student('EM Closed Student')
        self._enroll(student, self.subject1)
        subject_record = self._archived_subject(student)
        subject_record.write({'external_grade': 7, 'external_is_scored': True,
                              'final_grade': 6, 'has_final': True})
        self.assertFalse(subject_record.final_pending)
        self.assertEqual(len(self._form().line_ids), 0)

    def test_live_line_wins_over_archived_same_subject(self):
        student = self._live_student()
        self._archived_subject(student)
        wizard = self._form().save()
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.source, 'live')

    def test_ex_student_is_not_offered(self):
        """An ex-student is never graded: a withdrawal keeps its ems.enrollment records
        (they live until the transition), so without the contact_type filter it would still
        show up in its old group — with its grades editable."""
        withdrawn = self._live_student('EM Withdrawn')
        self._archived_subject(withdrawn)
        withdrawn.write({'contact_type': 'withdrawal', 'main_group_id': False})
        wizard = self._form().save()
        self.assertFalse(wizard.student_line_ids)
        self.assertFalse(wizard.line_ids)

    # --- apply: live destination ---------------------------------------------

    def test_apply_live_passed_completes_the_final(self):
        student = self._live_student()
        form = self._form()
        self._grade_student(form, 0, 8)
        form.save().action_apply()
        line = self._subject_line(student, self.subject1)
        self.assertEqual((line.external_score, line.external_is_scored), (8, True))
        # 6 * 90% + 8 * 10% = 6.2 -> 6 (round half up), final available.
        self.assertEqual(line.final_score, 6)
        self.assertTrue(line.has_final)

    def test_apply_live_failed_repeats_the_placement(self):
        student = self._live_student()
        form = self._form()
        self._grade_student(form, 0, 3)
        form.save().action_apply()
        line = self._subject_line(student, self.subject1)
        # The grade is kept for the record but not marked: no final, the subject stays
        # passed and the placement is repeated.
        self.assertEqual(line.external_score, 3)
        self.assertFalse(line.external_is_scored)
        self.assertFalse(line.has_final)

    def test_apply_live_on_final_session(self):
        """The EM arrives after the rounds are closed: a finalised session must not
        block the tutor (the wizard lifts the state guard for the EM fields only)."""
        student = self._live_student()
        self._subject_line(student, self.subject1).grade_session_id.write({'state': 'final'})
        form = self._form(user=self.tutor_user)
        self._grade_student(form, 0, 8)
        form.save().action_apply()
        line = self._subject_line(student, self.subject1)
        self.assertEqual((line.external_score, line.external_is_scored), (8, True))
        self.assertTrue(line.has_final)

    def test_untouched_students_are_not_written(self):
        finished = self._live_student('AAA Finished')
        unfinished = self._live_student('BBB Unfinished')
        form = self._form()
        self.assertEqual(len(form.student_line_ids), 2)
        self._grade_student(form, 0, 8)  # lines are ordered by student name
        form.save().action_apply()
        self.assertTrue(self._subject_line(finished, self.subject1).external_is_scored)
        unfinished_line = self._subject_line(unfinished, self.subject1)
        self.assertFalse(unfinished_line.external_is_scored)
        self.assertEqual(unfinished_line.external_score, 0)

    def test_student_grade_applies_to_all_their_modules(self):
        """The normal case: one grade per student, applied to every module of theirs."""
        subject3 = self.env['ems.subject'].create({
            'code': 'EMSUB3', 'acronym': 'EM3', 'name': 'EM Subject 3',
            'study_ids': [(4, self.study.id)]})
        outcome3 = self.env['ems.outcome'].create({
            'code': 'EMSUB3_01RA', 'acronym': 'RA1', 'name': 'EM Outcome 3',
            'subject_id': subject3.id})
        self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': subject3.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome3.id, 'ponderation': 100.0})]})
        student = self._live_student()
        self._enroll(student, subject3)
        session = self._session(subject3)
        session.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == student).write({'score': 6, 'is_scored': True})

        form = self._form()
        self.assertEqual(len(form.line_ids), 2)  # both modules with a placement weight
        self._grade_student(form, 0, 8)
        form.save().action_apply()
        for subject in (self.subject1, subject3):
            line = self._subject_line(student, subject)
            self.assertEqual((line.external_score, line.external_is_scored), (8, True))

    def test_per_module_grading(self):
        """The exception: with "grade per module" ticked, each cell carries its own grade."""
        subject3 = self.env['ems.subject'].create({
            'code': 'EMSUB3', 'acronym': 'EM3', 'name': 'EM Subject 3',
            'study_ids': [(4, self.study.id)]})
        outcome3 = self.env['ems.outcome'].create({
            'code': 'EMSUB3_01RA', 'acronym': 'RA1', 'name': 'EM Outcome 3',
            'subject_id': subject3.id})
        self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': subject3.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome3.id, 'ponderation': 100.0})]})
        student = self._live_student()
        self._enroll(student, subject3)
        session = self._session(subject3)
        session.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == student).write({'score': 6, 'is_scored': True})

        form = self._form()
        self._grade_per_module(form, 0)
        # Module lines are ordered by subject name: index 0 is EM Subject 1, index 1 is 3.
        self._grade_module(form, 0, 10)
        self._grade_module(form, 1, 6)
        form.save().action_apply()
        self.assertEqual(self._subject_line(student, self.subject1).external_score, 10)
        self.assertEqual(self._subject_line(student, subject3).external_score, 6)

    def test_per_module_leaves_empty_cells_alone(self):
        """A student graded per module only gets the cells actually filled in."""
        student = self._live_student()
        form = self._form()
        self._grade_per_module(form, 0)
        form.save()
        with self.assertRaises(UserError):
            form.record.action_apply()
        self.assertFalse(self._subject_line(student, self.subject1).external_is_scored)

    # --- apply: archived destination -----------------------------------------

    def test_apply_archived_passed_uses_frozen_weights(self):
        student = self._student('EM Archived Passed')
        self._enroll(student, self.subject1)
        subject_record = self._archived_subject(student, internal_grade=6)
        form = self._form()
        self._grade_student(form, 0, 8)
        form.save().action_apply()
        self.assertEqual((subject_record.external_grade, subject_record.external_is_scored), (8, True))
        self.assertEqual(subject_record.final_grade, 6)
        self.assertTrue(subject_record.has_final)
        self.assertFalse(subject_record.final_pending)
        self.assertEqual(subject_record.state, 'passed')

    def test_apply_archived_failed_keeps_final_pending(self):
        student = self._student('EM Archived Failed')
        self._enroll(student, self.subject1)
        subject_record = self._archived_subject(student)
        form = self._form()
        self._grade_student(form, 0, 4)
        form.save().action_apply()
        self.assertEqual(subject_record.external_grade, 4)
        self.assertFalse(subject_record.external_is_scored)
        self.assertFalse(subject_record.has_final)
        self.assertTrue(subject_record.final_pending)
        self.assertEqual(subject_record.state, 'passed')

    # --- ownership and validation --------------------------------------------

    def test_tutor_group_domain(self):
        wizard = self.env['ems.em_grading_wizard'].with_user(self.tutor_user).create({})
        selectable = self.env['ems.group'].with_user(self.tutor_user).search(
            eval(wizard.group_domain))  # noqa: S307 - the domain is built by the wizard
        self.assertIn(self.group, selectable)
        self.assertNotIn(self.other_group, selectable)
        admin_wizard = self.env['ems.em_grading_wizard'].create({})
        self.assertEqual(eval(admin_wizard.group_domain), [])  # noqa: S307

    def test_tutor_cannot_apply_other_group(self):
        wizard = self.env['ems.em_grading_wizard'].with_user(self.tutor_user).create({
            'group_id': self.other_group.id})
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_apply_without_grades_raises(self):
        self._live_student()
        with self.assertRaises(UserError):
            self._form().save().action_apply()

    def test_score_out_of_range(self):
        self._live_student()
        form = self._form()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._grade_student(form, 0, 11)
            form.save()
