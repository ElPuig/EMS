from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestGradeSession(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Users / employees
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Grade)',
            'login': 'test_teacher_for_grade',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Grade) Employee',
            'user_id': cls.teacher_user.id,
            'employee_type': 'teacher',
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Grade)',
            'login': 'test_secretary_for_grade',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })

        # Curriculum
        cls.level, cls.study = create_level_study(cls, 'TGL', level={'name': 'Test Grade Level'}, study={
            'code': 'TGSTD1', 'acronym': 'TGS', 'name': 'Test Grade Study',
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGSUB1',
            'acronym': 'TGSU',
            'name': 'Test Grade Subject',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome1 = cls.env['ems.outcome'].create({
            'code': 'TGSUB1_01RA', 'acronym': 'RA1', 'name': 'Outcome 1', 'subject_id': cls.subject.id,
        })
        cls.outcome2 = cls.env['ems.outcome'].create({
            'code': 'TGSUB1_02RA', 'acronym': 'RA2', 'name': 'Outcome 2', 'subject_id': cls.subject.id,
        })

        # Planning: 60 / 40, internal 90 / external 10
        cls.planning = cls.env['ems.planning'].create({
            'study_id': cls.study.id,
            'subject_id': cls.subject.id,
            'internal_ponderation': 90.0,
            'external_ponderation': 10.0,
            'planning_outcome_ids': [
                (0, 0, {'outcome_id': cls.outcome1.id, 'ponderation': 60.0}),
                (0, 0, {'outcome_id': cls.outcome2.id, 'ponderation': 40.0}),
            ],
        })

        # Group + students + enrollment
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.student1 = cls.env['res.partner'].create({'name': 'Student One', 'contact_type': 'student'})
        cls.student2 = cls.env['res.partner'].create({'name': 'Student Two', 'contact_type': 'student'})
        for student in (cls.student1, cls.student2):
            cls.env['ems.enrollment'].create({
                'student_id': student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
            })

    def _make_teacher(self, login, name):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name,
            'login': login,
            'groups_id': [(4, self.env.ref('base.group_user').id), (4, self.env.ref('ems.group_teacher').id)],
        })
        employee = self.env['hr.employee'].create({
            'name': name + ' Employee', 'user_id': user.id, 'employee_type': 'teacher',
        })
        return user, employee

    def _new_session(self, round="1", user=None, teacher=None):
        model = self.env['ems.grade_session']
        if user:
            model = model.with_user(user)
        return model.create({
            'group_id': self.group.id,
            'subject_id': self.subject.id,
            'round': round,
            'teacher_id': (teacher or self.teacher_employee).id,
        })

    def test_create_valid(self):
        session = self._new_session()
        self.assertTrue(session.id)
        self.assertEqual(session.planning_id, self.planning)
        self.assertTrue(session.has_planning)

    def test_required_fields(self):
        with self.assertRaises(Exception):
            self.env['ems.grade_session'].create({'subject_id': self.subject.id, 'teacher_id': self.teacher_employee.id})

    def test_display_name(self):
        session = self._new_session()
        self.assertEqual(session.display_name, "%s %s (1a)" % (self.group.name, self.subject.display_name))

    def test_unique_group_subject_round(self):
        self._new_session(round="1")
        with self.assertRaises(Exception):
            self._new_session(round="1")

    def test_fill_students_generates_lines(self):
        session = self._new_session()
        session.fill_students()
        # 2 students x 2 outcomes = 4 outcome lines; 2 subject lines
        self.assertEqual(len(session.grade_outcome_line_ids), 4)
        self.assertEqual(len(session.grade_subject_line_ids), 2)
        self.assertEqual(session.grade_outcome_line_ids.mapped('ponderation'), [60.0, 40.0, 60.0, 40.0])

    def test_passed_outcome_is_locked_in_later_round(self):
        # Student1 passes outcome1 (>= 5) in round 1; fails outcome2.
        session1 = self._new_session(round="1")
        session1.fill_students()
        lines1 = session1.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines1.filtered(lambda line: line.outcome_id == self.outcome1).write({'score': 7, 'is_scored': True})
        lines1.filtered(lambda line: line.outcome_id == self.outcome2).write({'score': 3, 'is_scored': True})

        # Round 2: the passed outcome is locked and carried over; the failed one is carried over too (with
        # its previous score) but stays open and editable.
        session2 = self._new_session(round="2")
        session2.fill_students()
        lines2 = session2.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        locked = lines2.filtered(lambda line: line.outcome_id == self.outcome1)
        reopen = lines2.filtered(lambda line: line.outcome_id == self.outcome2)
        self.assertTrue(locked.is_locked)
        self.assertEqual(locked.score, 7)
        self.assertTrue(locked.is_scored)
        self.assertFalse(reopen.is_locked)
        self.assertTrue(reopen.is_scored)
        self.assertEqual(reopen.score, 3)

    def test_locked_outcome_cannot_be_rewritten(self):
        session1 = self._new_session(round="1")
        session1.fill_students()
        session1.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == self.student1 and line.outcome_id == self.outcome1
        ).write({'score': 8, 'is_scored': True})

        session2 = self._new_session(round="2")
        session2.fill_students()
        locked = session2.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == self.student1 and line.outcome_id == self.outcome1
        )
        with self.assertRaises(UserError):
            locked.write({'score': 4, 'is_scored': True})

    def test_apply_grade_changes_batches_writes(self):
        # The tutor view's batch entry point writes several outcome and subject lines in one call and
        # recomputes the subject grades.
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        line1 = lines.filtered(lambda line: line.outcome_id == self.outcome1)
        line2 = lines.filtered(lambda line: line.outcome_id == self.outcome2)
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.env['ems.grade_session'].apply_grade_changes(
            {str(line1.id): {'score': 8, 'is_scored': True}, str(line2.id): {'score': 6, 'is_scored': True}},
            {str(subject_line.id): {'external_score': 7, 'external_is_scored': True}},
        )
        self.assertEqual(line1.score, 8)
        self.assertEqual(line2.score, 6)
        self.assertEqual(subject_line.external_score, 7)
        # (8*60 + 6*40) / 100 = 7.2 -> 7 internal, complete evaluation.
        self.assertEqual(subject_line.internal_score, 7)
        self.assertTrue(subject_line.internal_is_complete)

    def test_apply_grade_changes_enforces_lock(self):
        session1 = self._new_session(round="1")
        session1.fill_students()
        session1.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == self.student1 and line.outcome_id == self.outcome1
        ).write({'score': 8, 'is_scored': True})
        session2 = self._new_session(round="2")
        session2.fill_students()
        locked = session2.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == self.student1 and line.outcome_id == self.outcome1
        )
        # The batch method still goes through the line write(), so a locked outcome is rejected.
        with self.assertRaises(UserError):
            self.env['ems.grade_session'].apply_grade_changes(
                {str(locked.id): {'score': 3, 'is_scored': True}}, {},
            )

    def test_failed_outcome_carried_over_but_editable(self):
        # A failed outcome (< 5) does not lock the next round: its previous score is carried over as a
        # starting point, but it can still be re-evaluated.
        session1 = self._new_session(round="1")
        session1.fill_students()
        session1.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == self.student1 and line.outcome_id == self.outcome1
        ).write({'score': 4, 'is_scored': True})

        session2 = self._new_session(round="2")
        session2.fill_students()
        reopen = session2.grade_outcome_line_ids.filtered(
            lambda line: line.student_id == self.student1 and line.outcome_id == self.outcome1
        )
        self.assertFalse(reopen.is_locked)
        self.assertTrue(reopen.is_scored)
        self.assertEqual(reopen.score, 4)  # carried over from round 1
        reopen.write({'score': 6, 'is_scored': True})  # must not raise
        self.assertEqual(reopen.score, 6)

    def test_internal_score_weighted_average(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines.filtered(lambda line: line.outcome_id == self.outcome1).write({'score': 8, 'is_scored': True})
        lines.filtered(lambda line: line.outcome_id == self.outcome2).write({'score': 6, 'is_scored': True})
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        # (8*60 + 6*40) / 100 = 7.2, rounded to a whole number -> 7.
        self.assertEqual(subject_line.internal_score, 7)
        self.assertTrue(subject_line.internal_is_scored)
        # The planning has a 10% external weight not yet informed -> no computed grade.
        self.assertFalse(subject_line.computed_is_scored)

    def test_missing_score_is_renormalized(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        # Only outcome1 informed: the internal grade is the renormalized average over the evaluated
        # outcomes (8*60 / 60 = 8), a provisional grade; the pending outcome is left out, not counted as 0.
        lines.filtered(lambda line: line.outcome_id == self.outcome1).write({'score': 8, 'is_scored': True})
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.assertEqual(subject_line.internal_score, 8)
        self.assertTrue(subject_line.internal_is_scored)
        # But the evaluation is incomplete (outcome2 still pending).
        self.assertFalse(subject_line.internal_is_complete)

    def test_internal_complete_when_all_scored(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines.write({'score': 8, 'is_scored': True})  # both outcomes evaluated
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.assertTrue(subject_line.internal_is_complete)

    def test_missing_score_provisional_computed(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        # outcome1 passed (10), outcome2 pending, external passed (10): the provisional internal is the
        # renormalized 10, so the provisional computed grade is 10 - but the evaluation is not complete.
        lines.filtered(lambda line: line.outcome_id == self.outcome1).write({'score': 10, 'is_scored': True})
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        subject_line.write({'external_score': 10, 'external_is_scored': True})
        self.assertTrue(subject_line.computed_is_scored)
        self.assertEqual(subject_line.computed_score, 10)
        self.assertFalse(subject_line.internal_is_complete)

    def test_no_final_while_incomplete(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        # Only outcome1 scored; outcome2 pending -> internal incomplete.
        lines.filtered(lambda line: line.outcome_id == self.outcome1).write({'score': 8, 'is_scored': True})
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        subject_line.write({'external_score': 8, 'external_is_scored': True})
        # A provisional computed grade exists, but the evaluation is incomplete -> no final (stays pending).
        self.assertTrue(subject_line.computed_is_scored)
        self.assertFalse(subject_line.internal_is_complete)
        self.assertFalse(subject_line.has_final)
        # Completing the remaining outcome brings the final in.
        lines.filtered(lambda line: line.outcome_id == self.outcome2).write({'score': 6, 'is_scored': True})
        self.assertTrue(subject_line.internal_is_complete)
        self.assertTrue(subject_line.has_final)

    def test_failed_outcome_caps_internal(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        # (8*60 + 3*40) / 100 = 6.0, but outcome2 is failed (< 5) -> internal capped at 4.
        lines.filtered(lambda line: line.outcome_id == self.outcome1).write({'score': 8, 'is_scored': True})
        lines.filtered(lambda line: line.outcome_id == self.outcome2).write({'score': 3, 'is_scored': True})
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.assertEqual(subject_line.internal_score, 4.0)

    def test_external_score_in_computed(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines.write({'score': 8, 'is_scored': True})  # both outcomes -> internal 8
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        # Until the external grade is informed there is no computed (nor final) grade.
        self.assertFalse(subject_line.computed_is_scored)
        self.assertFalse(subject_line.has_final)
        # An informed external 0 is different from empty; but a failed external part caps computed at 4.
        subject_line.write({'external_score': 0, 'external_is_scored': True})
        self.assertTrue(subject_line.computed_is_scored)
        self.assertEqual(subject_line.computed_score, 4)
        # A passing external grade lifts the cap: 8*0.9 + 10*0.1 = 8.2 -> 8.
        subject_line.write({'external_score': 10, 'external_is_scored': True})
        self.assertEqual(subject_line.computed_score, 8)

    def test_failed_part_caps_computed(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines.write({'score': 8, 'is_scored': True})  # internal passed (8)
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        # External failed (< 5): even though 8*0.9 + 3*0.1 = 7.5, the subject cannot be passed -> cap 4.
        subject_line.write({'external_score': 3, 'external_is_scored': True})
        self.assertEqual(subject_line.computed_score, 4)
        # Passing both parts lifts the cap: 8*0.9 + 6*0.1 = 8.4 -> 8.
        subject_line.write({'external_score': 6, 'external_is_scored': True})
        self.assertEqual(subject_line.computed_score, 8)

    def test_no_final_without_both_components(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines.write({'score': 8, 'is_scored': True})  # internal informed, external not
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.assertTrue(subject_line.internal_is_scored)
        self.assertFalse(subject_line.external_is_scored)
        # No external grade (10% weight) -> no final grade.
        self.assertFalse(subject_line.has_final)
        # Overriding the internal grade does not bypass the missing external -> still no final.
        subject_line.write({'is_overridden': True, 'internal_score': 9})
        self.assertFalse(subject_line.has_final)
        # Informing the external grade brings the final in.
        subject_line.write({'external_score': 6, 'external_is_scored': True})
        self.assertTrue(subject_line.has_final)

    def test_internal_default_and_override(self):
        session = self._new_session()
        session.fill_students()
        lines = session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student1)
        lines.write({'score': 7, 'is_scored': True})
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.assertFalse(subject_line.is_overridden)
        # Internal computed from the outcomes: (7*60 + 7*40) / 100 = 7.
        self.assertEqual(subject_line.internal_score, 7)
        # Overriding is an explicit flag on the internal grade: mark it and set a manual value; it persists.
        subject_line.write({'is_overridden': True, 'internal_score': 9})
        self.assertEqual(subject_line.internal_score, 9)
        # Clearing the override reverts the internal grade to the computed one.
        subject_line.is_overridden = False
        self.assertEqual(subject_line.internal_score, 7)

    def test_score_out_of_range(self):
        session = self._new_session()
        session.fill_students()
        with self.assertRaises(ValidationError):
            session.grade_outcome_line_ids[0].write({'score': 11})

    def test_no_planning_does_not_break(self):
        other_subject = self.env['ems.subject'].create({
            'code': 'TGSUB2', 'acronym': 'TGS2', 'name': 'No Planning Subject', 'study_ids': [(4, self.study.id)],
        })
        self.env['ems.enrollment'].create({
            'student_id': self.student1.id, 'group_id': self.group.id, 'subject_id': other_subject.id,
        })
        session = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': other_subject.id, 'round': '1', 'teacher_id': self.teacher_employee.id,
        })
        self.assertFalse(session.has_planning)
        session.fill_students()  # must not raise

    def test_ondelete_cascade(self):
        session = self._new_session()
        session.fill_students()
        line_ids = session.grade_outcome_line_ids.ids
        session.unlink()
        self.assertFalse(self.env['ems.grade_outcome_line'].search([('id', 'in', line_ids)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self._new_session(user=self.teacher_user)

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self._new_session(user=self.secretary_user)

    def test_teacher_can_write_scores(self):
        session = self._new_session()
        session.fill_students()
        line = session.grade_outcome_line_ids[0]
        line.with_user(self.teacher_user).write({'score': 7, 'is_scored': True})
        self.assertEqual(line.score, 7)

    def test_tutor_can_edit_tutored_group_lines(self):
        tutor_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Tutor (Grade)',
            'login': 'test_tutor_for_grade',
            'groups_id': [(4, self.env.ref('base.group_user').id), (4, self.env.ref('ems.group_teacher').id)],
        })
        tutor_employee = self.env['hr.employee'].create({
            'name': 'Test Tutor (Grade) Employee', 'user_id': tutor_user.id, 'employee_type': 'teacher',
        })
        self.group.tutor_id = tutor_employee
        # Session taught by another teacher (not the tutor).
        session = self._new_session()
        session.fill_students()
        line = session.grade_outcome_line_ids[0]
        line.with_user(tutor_user).write({'score': 5, 'is_scored': True})
        self.assertEqual(line.score, 5)

    def test_unrelated_teacher_cannot_edit(self):
        stranger_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Stranger (Grade)',
            'login': 'test_stranger_for_grade',
            'groups_id': [(4, self.env.ref('base.group_user').id), (4, self.env.ref('ems.group_teacher').id)],
        })
        self.env['hr.employee'].create({
            'name': 'Test Stranger (Grade) Employee', 'user_id': stranger_user.id, 'employee_type': 'teacher',
        })
        session = self._new_session()
        session.fill_students()
        line = session.grade_outcome_line_ids[0]
        with self.assertRaises(AccessError):
            line.with_user(stranger_user).write({'score': 5, 'is_scored': True})

    def test_line_related_fields_for_tutor_view(self):
        # The tutor view (client action) reads these related fields to group and label the grid.
        session = self._new_session()
        session.fill_students()
        outcome_line = session.grade_outcome_line_ids[0]
        self.assertEqual(outcome_line.subject_id, self.subject)
        subject_line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == self.student1)
        self.assertEqual(subject_line.subject_id, self.subject)
        self.assertEqual(subject_line.subject_name, self.subject.display_name)
        self.assertEqual(subject_line.student_firstname, self.student1.firstname)
        self.assertEqual(subject_line.student_lastname, self.student1.lastname)

    # --- state lifecycle -------------------------------------------------

    def test_teacher_cannot_edit_in_board(self):
        session = self._new_session()
        session.fill_students()
        session.state = 'board'
        line = session.grade_outcome_line_ids[0]
        with self.assertRaises(UserError):
            line.with_user(self.teacher_user).write({'score': 5, 'is_scored': True})

    def test_tutor_can_edit_in_board(self):
        tutor_user, tutor_employee = self._make_teacher('test_tutor_board', 'Tutor Board')
        self.group.tutor_id = tutor_employee
        session = self._new_session()
        session.fill_students()
        session.state = 'board'
        line = session.grade_outcome_line_ids[0]
        line.with_user(tutor_user).write({'score': 6, 'is_scored': True})
        self.assertEqual(line.score, 6)

    def test_only_admin_edits_in_final(self):
        tutor_user, tutor_employee = self._make_teacher('test_tutor_final', 'Tutor Final')
        self.group.tutor_id = tutor_employee
        session = self._new_session()
        session.fill_students()
        session.state = 'final'
        line = session.grade_outcome_line_ids[0]
        with self.assertRaises(UserError):
            line.with_user(self.teacher_user).write({'score': 5, 'is_scored': True})
        with self.assertRaises(UserError):
            line.with_user(tutor_user).write({'score': 5, 'is_scored': True})
        # Admin can still edit.
        line.write({'score': 9, 'is_scored': True})
        self.assertEqual(line.score, 9)

    def test_state_change_only_admin(self):
        session = self._new_session()
        with self.assertRaises(UserError):
            session.with_user(self.teacher_user).write({'state': 'board'})

    def test_archive_only_admin(self):
        session = self._new_session()
        session.state = 'final'
        # A teacher cannot archive a session (not even a finalised one).
        with self.assertRaises(UserError):
            session.with_user(self.teacher_user).write({'active': False})
        with self.assertRaises(UserError):
            session.with_user(self.teacher_user).action_archive()
        # An administrator can.
        session.action_archive()
        self.assertFalse(session.active)

    def test_state_wizard_bulk_transition(self):
        session = self._new_session(round='1')
        wizard = self.env['ems.grade_session_state_wizard'].create({
            'mode': 'study', 'study_ids': [(6, 0, [self.study.id])], 'round': '1', 'target_state': 'board',
        })
        wizard.action_apply_state()
        self.assertEqual(session.state, 'board')

    def test_wizard_creates_sessions_by_study(self):
        wizard = self.env['ems.grade_session_wizard'].create({
            'mode': 'study', 'study_ids': [(6, 0, [self.study.id])], 'round': '1',
        })
        wizard.action_create_sessions()
        session = self.env['ems.grade_session'].search([
            ('group_id', '=', self.group.id), ('subject_id', '=', self.subject.id), ('round', '=', '1'),
        ])
        self.assertEqual(len(session), 1)
        # 2 students x 2 outcomes
        self.assertEqual(len(session.grade_outcome_line_ids), 4)

    def test_wizard_excludes_tutorship(self):
        tutorship = self.env['ems.subject'].create({
            'code': 'TGTUT1', 'acronym': 'TGTU', 'name': 'Tutorship test',
            'is_tutorship': True, 'study_ids': [(4, self.study.id)],
        })
        self.env['ems.enrollment'].create({
            'student_id': self.student1.id, 'group_id': self.group.id, 'subject_id': tutorship.id,
        })
        wizard = self.env['ems.grade_session_wizard'].create({
            'mode': 'study', 'study_ids': [(6, 0, [self.study.id])], 'round': '1',
        })
        wizard.action_create_sessions()
        self.assertFalse(self.env['ems.grade_session'].search([
            ('group_id', '=', self.group.id), ('subject_id', '=', tutorship.id),
        ]))

    def test_wizard_derives_teacher_from_teaching(self):
        self.env['ems.teaching'].create({
            'teacher_id': self.teacher_employee.id, 'group_id': self.group.id, 'subject_id': self.subject.id,
        })
        wizard = self.env['ems.grade_session_wizard'].create({
            'mode': 'study', 'study_ids': [(6, 0, [self.study.id])], 'round': '2',
        })
        wizard.action_create_sessions()
        session = self.env['ems.grade_session'].search([
            ('group_id', '=', self.group.id), ('subject_id', '=', self.subject.id), ('round', '=', '2'),
        ])
        self.assertEqual(session.teacher_id, self.teacher_employee)

    def test_wizard_suggests_next_round(self):
        wizard = self.env['ems.grade_session_wizard'].new({'mode': 'study', 'study_ids': [(6, 0, [self.study.id])]})
        wizard._onchange_suggest_round()
        self.assertEqual(wizard.round, '1')
        self._new_session(round='1')
        wizard2 = self.env['ems.grade_session_wizard'].new({'mode': 'study', 'study_ids': [(6, 0, [self.study.id])]})
        wizard2._onchange_suggest_round()
        self.assertEqual(wizard2.round, '2')

    def test_wizard_skips_existing(self):
        self._new_session(round='1')
        wizard = self.env['ems.grade_session_wizard'].create({
            'mode': 'study', 'study_ids': [(6, 0, [self.study.id])], 'round': '1',
        })
        with self.assertRaises(UserError):
            wizard.action_create_sessions()
