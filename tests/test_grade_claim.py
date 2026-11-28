from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import (create_head_of_studies_branch, create_level_study, create_role_employee, create_role_user,
                     mock_outgoing_email, next_student_id)


def build_claim_fixture(cls):
    """A teacher, a tutor hung below a Department Chief and a Head of Studies (plus another
    teacher and another Head of Studies out of that chain), one subject with two outcomes and an
    adult student whose RA1 is graded 4 in an open session whose claims period is running."""
    mock_outgoing_email(cls)
    cls.today = cls.env['ems.datetime_utils'].get_local_today()
    cls.teacher_user = create_role_user(cls, 'teacher', 'test_claim_teacher', name='Claim Teacher')
    cls.teacher = create_role_employee(cls, cls.teacher_user)
    cls.other_teacher_user = create_role_user(cls, 'teacher', 'test_claim_other_teacher', name='Claim Other Teacher')
    create_role_employee(cls, cls.other_teacher_user)
    cls.tutor_user = create_role_user(cls, 'tutor', 'test_claim_tutor', name='Claim Tutor')
    cls.tutor = create_role_employee(cls, cls.tutor_user)
    create_head_of_studies_branch(cls, 'TGC', cls.tutor)

    cls.level, cls.study = create_level_study(cls, 'TGC', level={'name': 'Test Claim Level'}, study={
        'code': 'TGCSTD', 'acronym': 'TGC', 'name': 'Test Claim Study'})
    cls.subject = cls.env['ems.subject'].create({
        'code': 'TGCSUB', 'acronym': 'TGCS', 'name': 'Test Claim Subject', 'study_ids': [(4, cls.study.id)]})
    cls.outcome1, cls.outcome2 = cls.env['ems.outcome'].create([
        {'code': 'TGCSUB_01RA', 'acronym': 'RA1', 'name': 'Outcome 1', 'subject_id': cls.subject.id},
        {'code': 'TGCSUB_02RA', 'acronym': 'RA2', 'name': 'Outcome 2', 'subject_id': cls.subject.id},
    ])
    cls.env['ems.planning'].create({
        'study_id': cls.study.id, 'subject_id': cls.subject.id,
        'internal_ponderation': 100.0, 'external_ponderation': 0.0,
        'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome1.id, 'ponderation': 50.0}),
                                 (0, 0, {'outcome_id': cls.outcome2.id, 'ponderation': 50.0})],
    })
    cls.group = cls.env['ems.group'].create({
        'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id, 'tutor_id': cls.tutor.id})
    cls.student = cls.env['res.partner'].create({
        'name': 'Claim Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'birth_date': '2000-01-01', 'main_group_id': cls.group.id, 'email': 'claim.student@example.com'})
    cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})
    cls.grade_session = cls.env['ems.grade_session'].create({
        'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '1', 'teacher_id': cls.teacher.id,
        'claim_date_from': cls.today - timedelta(days=1), 'claim_date_to': cls.today + timedelta(days=3)})
    cls.grade_session.fill_students()
    cls.line1 = cls.grade_session.grade_outcome_line_ids.filtered(lambda line: line.outcome_id == cls.outcome1)
    cls.line2 = cls.grade_session.grade_outcome_line_ids.filtered(lambda line: line.outcome_id == cls.outcome2)
    cls.line1.write({'score': 4, 'is_scored': True})


class TestGradeClaim(TransactionCase):
    """Issue #879: grade claims from the portal, answered by the teacher, then the tutor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        build_claim_fixture(cls)
        cls.Claim = cls.env['ems.grade_claim']

    def _publish(self):
        self.grade_session.state = 'published'

    def _file(self, item=None, reason='RA1 left out my second project'):
        return self.Claim.ems_file_from_portal(self.student, self.student, item or f'outcome-{self.line1.id}', reason)

    def test_claimable_only_published_inside_the_period(self):
        self.assertEqual(self.Claim._ems_claimable_items(self.student, self.student), [])
        self._publish()
        items = self.Claim._ems_claimable_items(self.student, self.student)
        # RA1 graded; RA2 not graded, and no final grade until every outcome is evaluated.
        self.assertEqual([(kind, line) for __, kind, line, __ in items], [('outcome', self.line1)])
        self.grade_session.claim_date_to = self.today - timedelta(days=1)
        self.assertEqual(self.Claim._ems_claimable_items(self.student, self.student), [])

    def test_final_grade_claimable_once_every_outcome_is_evaluated(self):
        self.line2.write({'score': 6, 'is_scored': True})
        self._publish()
        kinds = [kind for __, kind, __, __ in self.Claim._ems_claimable_items(self.student, self.student)]
        self.assertEqual(kinds, ['outcome', 'outcome', 'final'])

    def test_a_minor_without_family_cannot_claim(self):
        # The convalidations' rule: a minor never files it himself, only his family.
        self.student.birth_date = self.today - timedelta(days=365 * 15)
        self._publish()
        self.assertEqual(self.Claim._ems_claimable_items(self.student, self.student), [])
        with self.assertRaises(UserError):
            self._file()

    def test_filing_gives_the_teacher_a_quiet_task_and_once_per_grade(self):
        self._publish()
        claim = self._file()
        self.assertEqual(claim.state, 'teacher')
        self.assertEqual(claim.claimed_score, 4)
        self.assertEqual(claim.activity_ids.user_id, self.teacher_user)
        with self.assertRaises(UserError):
            self._file()

    def test_teacher_accepts_and_the_grade_changes(self):
        self._publish()
        claim = self._file()
        mails_before = self.env['mail.mail'].search_count([('email_to', '=', 'claim.student@example.com')])
        claim.with_user(self.teacher_user).ems_accept(6)
        self.assertEqual((claim.state, claim.new_score, self.line1.score), ('accepted', 6, 6))
        self.assertFalse(claim.activity_ids)
        self.assertEqual(self.env['mail.mail'].search_count([('email_to', '=', 'claim.student@example.com')]),
                         mails_before + 1)

    def test_deny_then_tutor_second_instance(self):
        self._publish()
        claim = self._file()
        reason = self.env.ref('ems.grade_claim_denial_matches')
        claim.with_user(self.teacher_user).ems_deny(reason, '')
        self.assertEqual(claim.state, 'teacher_denied')
        claim.ems_escalate_from_portal(self.student, 'The shared sheet says 6')
        self.assertEqual(claim.state, 'tutor')
        self.assertEqual(claim.activity_ids.user_id, self.tutor_user)
        with self.assertRaises(AccessError):
            claim.with_user(self.teacher_user).ems_deny(reason, '')
        claim.with_user(self.tutor_user).ems_deny(reason, '')
        self.assertEqual(claim.state, 'denied')
        self.assertEqual(self.line1.score, 4)

    def test_escalation_deadline_two_school_days_after_a_late_denial(self):
        self._publish()
        claim = self._file()
        self.assertEqual(claim.escalation_deadline, self.grade_session.claim_date_to)
        claim.with_user(self.teacher_user).ems_deny(self.env.ref('ems.grade_claim_denial_matches'), '')
        self.grade_session.claim_date_to = self.today
        claim.invalidate_recordset(['escalation_deadline'])
        expected = self.env['resource.calendar.leaves']._ems_nth_school_day(self.today, 2)
        self.assertEqual(claim.escalation_deadline, expected)

    def test_other_denial_reason_needs_details(self):
        self._publish()
        claim = self._file()
        with self.assertRaises(UserError):
            claim.with_user(self.teacher_user).ems_deny(self.env.ref('ems.grade_claim_denial_other'), ' ')

    def test_who_answers(self):
        # Another teacher cannot; the Head of Studies of the tutor's chain can (either instance);
        # one from another branch cannot.
        self._publish()
        claim = self._file()
        with self.assertRaises(AccessError):
            claim.with_user(self.other_teacher_user).ems_accept(6)
        with self.assertRaises(AccessError):
            claim.with_user(self.other_head_of_studies).ems_accept(6)
        claim.with_user(self.head_of_studies).ems_accept(7)
        self.assertEqual(self.line1.score, 7)

    def test_final_grade_claim_overrides_the_internal_grade(self):
        self.line2.write({'score': 6, 'is_scored': True})
        self._publish()
        subject_line = self.grade_session.grade_subject_line_ids
        claim = self._file(item=f'final-{subject_line.id}')
        claim.with_user(self.teacher_user).ems_accept(7)
        self.assertTrue(subject_line.is_overridden)
        self.assertEqual(subject_line.final_score, 7)

    def test_session_cannot_be_finalised_with_pending_claims(self):
        self._publish()
        claim = self._file()
        head = self.head_of_studies
        with self.assertRaises(UserError):
            self.grade_session.with_user(head).write({'state': 'final'})
        claim.with_user(self.teacher_user).ems_accept(5)
        self.grade_session.with_user(head).write({'state': 'final'})
        self.assertEqual(self.grade_session.state, 'final')

    def test_the_apply_flag_alone_does_not_open_a_published_grade(self):
        # Only the accepted claim (in sudo, after checking who answers) writes a published grade.
        self._publish()
        with self.assertRaises(UserError):
            self.line1.with_user(self.teacher_user).with_context(ems_grade_claim_apply=True).write({'score': 9})

    def test_teacher_reads_only_claims_of_their_sessions_or_chain(self):
        self._publish()
        claim = self._file()
        self.assertEqual(self.Claim.with_user(self.teacher_user).search([('id', '=', claim.id)]), claim)
        self.assertEqual(self.Claim.with_user(self.head_of_studies).search([('id', '=', claim.id)]), claim)
        self.assertFalse(self.Claim.with_user(self.other_teacher_user).search([('id', '=', claim.id)]))
        self.assertFalse(self.Claim.with_user(self.other_head_of_studies).search([('id', '=', claim.id)]))

    def test_answer_wizard(self):
        self._publish()
        claim = self._file()
        action = claim.with_user(self.teacher_user).action_deny()
        wizard = self.env['ems.grade_claim.answer_wizard'].with_user(self.teacher_user).with_context(action['context']).create({
            'reason_id': self.env.ref('ems.grade_claim_denial_evidence').id})
        self.assertEqual(wizard.decision, 'deny')
        wizard.action_confirm()
        self.assertEqual(claim.teacher_reason_id, self.env.ref('ems.grade_claim_denial_evidence'))
        self.assertEqual(claim.teacher_answered_by_id, self.teacher_user)
