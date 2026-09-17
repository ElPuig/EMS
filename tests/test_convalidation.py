from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import (create_level_study, create_role_employee, create_role_user, mock_outgoing_email,
                     next_student_id)


def create_convalidation_fixtures(cls):
    """A vocational training study (its level allows convalidations) with two graded subjects and a
    tutorship, a group, the running course, and one user per role involved (Head of Studies,
    secretary, teacher). Shared with the portal and tour tests."""
    Course = cls.env['ems.course']
    cls.course = Course.create({'start': 2094, 'end': 2095})
    cls.env.company.current_course_id = cls.course
    cls.level, cls.study = create_level_study(cls, 'TCVL', level={
        'name': 'Test Level (Convalidation)', 'allows_convalidation': True,
    }, study={'code': 'TCVL001', 'acronym': 'TCVL', 'name': 'Test Study (Convalidation)'})
    cls.subject, cls.other_subject, cls.tutorship = cls.env['ems.subject'].create([{
        'code': code, 'acronym': acronym, 'name': name, 'is_tutorship': is_tutorship,
        'study_ids': [(6, 0, cls.study.ids)],
    } for code, acronym, name, is_tutorship in (
        ('TCVL01', 'TCV1', 'Test Subject One (Convalidation)', False),
        ('TCVL02', 'TCV2', 'Test Subject Two (Convalidation)', False),
        ('TCVL03', 'TCVT', 'Test Tutorship (Convalidation)', True),
    )])
    cls.outcome, cls.other_outcome = cls.env['ems.outcome'].create([{
        'code': f'{subject.code}_01RA', 'acronym': 'RA1', 'name': f'Outcome of {subject.name}',
        'subject_id': subject.id,
    } for subject in (cls.subject, cls.other_subject)])
    for subject, outcome, external in ((cls.subject, cls.outcome, 10.0), (cls.other_subject, cls.other_outcome, 0.0)):
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': subject.id,
            'internal_ponderation': 100.0 - external, 'external_ponderation': external,
            'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id, 'ponderation': 100.0})],
        })
    cls.group = cls.env['ems.group'].create({
        'course': 2, 'acronym': 'TCV', 'level_id': cls.level.id, 'study_id': cls.study.id, 'shift': 'morning',
    })
    cls.student = cls.env['res.partner'].create({
        'name': 'Convalidation Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'main_group_id': cls.group.id, 'email': 'convalidation.student@example.com',
        'birth_date': '2000-01-01',
    })
    cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_convalidation_hos',
                                           name='Convalidation Head of Studies')
    create_role_employee(cls, cls.head_of_studies)
    cls.secretary = create_role_user(cls, 'secretary', 'test_convalidation_secretary',
                                     name='Convalidation Secretary')
    create_role_employee(cls, cls.secretary, employee_type='asp')
    cls.teacher = create_role_user(cls, 'teacher', 'test_convalidation_teacher', name='Convalidation Teacher')
    create_role_employee(cls, cls.teacher)


class TestConvalidation(TransactionCase):
    """Issue #276 - subject convalidation requests, their resolution by the Head of Studies and
    their effect on grades. See docs/en/developers/grades/convalidation.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        create_convalidation_fixtures(cls)

    # --- helpers -------------------------------------------------------------

    def _request(self, subjects=None, student=None, user=None, **vals):
        Convalidation = self.env['ems.convalidation']
        if user:
            Convalidation = Convalidation.with_user(user)
        return Convalidation.create({
            'student_id': (student or self.student).id,
            'study_id': self.study.id,
            'course_id': self.course.id,
            'line_ids': [(0, 0, {'subject_id': subject.id}) for subject in (subjects or self.subject)],
            **vals,
        })

    def _line(self, request, subject=None):
        return request.line_ids.filtered(lambda line: line.subject_id == (subject or self.subject))

    def _enroll_and_grade(self, subject=None, student=None, state='open'):
        subject = subject or self.subject
        student = student or self.student
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': self.group.id, 'subject_id': subject.id})
        session = self.env['ems.grade_session'].search([
            ('group_id', '=', self.group.id), ('subject_id', '=', subject.id)], limit=1)
        if not session:
            session = self.env['ems.grade_session'].create({
                'group_id': self.group.id, 'subject_id': subject.id})
            session.fill_students()
        if state != 'open':
            session.state = state
        return session.grade_subject_line_ids.filtered(lambda line: line.student_id == student)

    # --- requests ------------------------------------------------------------

    def test_new_request_is_submitted(self):
        request = self._request(self.subject | self.other_subject)
        self.assertEqual(request.state, 'submitted')
        self.assertEqual(request.pending_count, 2)
        self.assertEqual(set(request.line_ids.mapped('state')), {'pending'})
        self.assertEqual(request.line_ids.student_id, self.student)
        self.assertIn(self.student.name, request.display_name)

    def test_study_level_must_allow_convalidations(self):
        _level, study = create_level_study(self, 'TCVN', study={'code': 'TCVN001'})
        with self.assertRaises(ValidationError):
            self._request(study_id=study.id)

    def test_subject_must_belong_to_the_study(self):
        foreign = self.env['ems.subject'].create({'code': 'TCVX01', 'acronym': 'TCVX', 'name': 'Foreign subject'})
        with self.assertRaises(ValidationError):
            self._request(foreign)

    def test_tutorship_cannot_be_convalidated(self):
        self.assertNotIn(self.tutorship, self.study._ems_convalidable_subjects())
        with self.assertRaises(ValidationError):
            self._request(self.tutorship)

    def test_request_needs_a_subject(self):
        with self.assertRaises(ValidationError):
            self.env['ems.convalidation'].create({
                'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id})

    def test_subject_once_per_request(self):
        request = self._request()
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                request.line_ids = [(0, 0, {'subject_id': self.subject.id})]

    def test_state_follows_the_lines(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_forward()
        self.assertEqual(request.state, 'in_progress')
        # A forwarded subject keeps the request open until the Department answers.
        self._line(request, self.other_subject).with_user(self.head_of_studies).action_grant()
        self.assertEqual(request.state, 'in_progress')
        self._line(request).with_user(self.head_of_studies).action_reject()
        self.assertEqual(request.state, 'resolved')
        self.assertEqual(request.granted_count, 1)
        self.assertEqual(request.pending_count, 0)

    def test_grant_pending_resolves_every_pending_subject(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_reject()
        request.with_user(self.head_of_studies).action_grant_pending()
        self.assertEqual(self._line(request).state, 'rejected')
        self.assertEqual(self._line(request, self.other_subject).state, 'granted')
        self.assertEqual(request.state, 'resolved')

    def test_cancel_and_reopen(self):
        request = self._request()
        request.with_user(self.secretary).action_cancel()
        self.assertEqual(request.state, 'cancelled')
        request.with_user(self.secretary).action_reopen()
        self.assertEqual(request.state, 'submitted')

    def test_cannot_cancel_once_a_subject_is_resolved(self):
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_forward()
        with self.assertRaises(UserError):
            request.action_cancel()

    # --- access --------------------------------------------------------------

    def test_head_of_studies_resolves(self):
        request = self._request(user=self.head_of_studies)
        self._line(request).with_user(self.head_of_studies).write({'state': 'granted', 'resolution_notes': 'OK'})
        self.assertEqual(request.state, 'resolved')
        self.assertEqual(request.resolved_by_id, self.head_of_studies)

    def test_director_resolves(self):
        director = create_role_user(self, 'director', 'test_convalidation_director')
        request = self._request()
        self._line(request).with_user(director).action_grant()
        self.assertEqual(self._line(request).state, 'granted')

    def test_secretary_registers_but_cannot_resolve(self):
        request = self._request(user=self.secretary)
        request.with_user(self.secretary).write({'resolution_notes': 'Received on paper'})
        self._line(request).with_user(self.secretary).write({'resolution_notes': 'Certificate attached'})
        with self.assertRaises(UserError):
            self._line(request).with_user(self.secretary).action_grant()
        with self.assertRaises(UserError):
            self.env['ems.convalidation.line'].with_user(self.secretary).create({
                'convalidation_id': request.id, 'subject_id': self.other_subject.id, 'state': 'granted'})

    def test_secretary_cannot_delete_requests(self):
        request = self._request()
        with self.assertRaises(AccessError):
            request.with_user(self.secretary).unlink()

    def test_teacher_has_no_access(self):
        request = self._request()
        with self.assertRaises(AccessError):
            request.with_user(self.teacher).read(['state'])

    def test_student_form_count_is_readable_by_a_teacher(self):
        self._request()
        student = self.student.with_user(self.teacher)
        self.assertEqual(student.convalidation_count, 1)

    # --- resolution notice ---------------------------------------------------

    def _resolution_mails(self, request):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'ems.convalidation'), ('res_id', '=', request.id)])

    def test_resolution_is_emailed_once_to_an_adult_student(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertFalse(self._resolution_mails(request))
        self.assertFalse(request.resolution_date)
        self._line(request, self.other_subject).with_user(self.head_of_studies).action_reject()
        mails = self._resolution_mails(request)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_to, self.student.email)
        self.assertTrue(request.resolution_date)
        self.assertTrue(request.message_ids.filtered(lambda message: self.student.email in (message.body or '')))
        # Editing a resolved request does not notify again.
        request.with_user(self.head_of_studies).resolution_notes = 'See you in September'
        self.assertEqual(len(self._resolution_mails(request)), 1)

    def test_reopened_request_is_notified_again(self):
        request = self._request()
        line = self._line(request).with_user(self.head_of_studies)
        line.action_grant()
        line.action_reset()
        self.assertEqual(request.state, 'submitted')
        self.assertFalse(request.resolution_date)
        line.action_reject()
        self.assertEqual(len(self._resolution_mails(request)), 2)

    def test_minor_resolution_goes_to_the_family(self):
        minor = self.env['res.partner'].create({
            'name': 'Convalidation Minor', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group.id, 'email': 'convalidation.minor@example.com',
            'birth_date': '2020-01-01',
        })
        family = self.env['res.partner'].create({
            'name': 'Convalidation Family', 'contact_type': 'family', 'email': 'convalidation.family@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': minor.id})
        request = self._request(student=minor)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertEqual(self._resolution_mails(request).mapped('email_to'), [family.email])

    def test_student_communications_are_comments_nobody_follows(self):
        request = self._request(user=self.head_of_studies)
        comment = self.env.ref('mail.mt_comment')
        submitted = request.message_ids.filtered(lambda message: message.subtype_id == comment)
        self.assertEqual(submitted.mapped('subject'), ['Convalidation request submitted'])
        self.assertIn(self.subject.display_name, submitted.body)
        self.assertFalse(request.message_partner_ids)
        self._line(request).with_user(self.head_of_studies).action_grant()
        request.invalidate_recordset(['message_ids'])
        # Rendered in the recipient's language, so only its shape is checked.
        resolved = request.message_ids.filtered(lambda message: message.subtype_id == comment) - submitted
        self.assertEqual(len(resolved), 1)
        self.assertIn(self.student.name, resolved.subject)
        self.assertIn(self.subject.display_name, resolved.body)
        # Posting emails nobody: the only email is the resolution itself.
        self.assertEqual(len(self._resolution_mails(request)), 1)
        self.assertEqual(len(self.env['mail.mail'].sudo().search([
            ('model', '=', 'ems.convalidation'), ('res_id', '=', request.id)])), 1)

    def test_cancel_and_reopen_are_communicated(self):
        request = self._request()
        request.with_user(self.secretary).action_cancel()
        request.with_user(self.secretary).action_reopen()
        self.assertEqual(
            request.message_ids.filtered(lambda message: message.subtype_id == self.env.ref('mail.mt_comment'))
            .mapped('subject'),
            ['Convalidation request reopened', 'Convalidation request cancelled', 'Convalidation request submitted'])

    def test_resolution_without_any_email_is_logged(self):
        student = self.env['res.partner'].create({
            'name': 'Convalidation No Email', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': '2000-01-01'})
        request = self._request(student=student)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertFalse(self._resolution_mails(request))
        self.assertTrue(request.message_ids.filtered(lambda message: 'could not be emailed' in (message.body or '')))

    # --- grades --------------------------------------------------------------

    def test_granted_subject_is_convalidated_in_grades(self):
        grade_line = self._enroll_and_grade()
        self.assertFalse(grade_line.is_convalidated)
        self.assertFalse(grade_line.has_final)
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertTrue(grade_line.is_convalidated)
        self.assertTrue(grade_line.internal_is_complete)
        self.assertTrue(grade_line.has_final)
        self.assertEqual(grade_line.final_score, 5)

    def test_convalidation_reaches_a_finalised_session(self):
        grade_line = self._enroll_and_grade(state='final')
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertTrue(grade_line.is_convalidated)

    def test_flag_cannot_be_written_by_hand_on_a_closed_session(self):
        grade_line = self._enroll_and_grade(state='final')
        # Only the convalidation sync may touch the flag of a closed session.
        with self.assertRaises(Exception):
            grade_line.with_user(self.head_of_studies).write({'is_convalidated': True})

    def test_revoked_convalidation_restores_the_grade(self):
        grade_line = self._enroll_and_grade()
        request = self._request()
        line = self._line(request).with_user(self.head_of_studies)
        line.action_grant()
        line.action_reject()
        self.assertFalse(grade_line.is_convalidated)
        self.assertFalse(grade_line.has_final)

    def test_deleted_line_restores_the_grade(self):
        grade_line = self._enroll_and_grade()
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._line(request).unlink()
        self.assertFalse(grade_line.is_convalidated)
        request.unlink()
        self.assertFalse(request.exists())

    def test_rejected_duplicate_does_not_undo_a_grant(self):
        grade_line = self._enroll_and_grade()
        first = self._request()
        self._line(first).with_user(self.head_of_studies).action_grant()
        second = self._request()
        self._line(second).with_user(self.head_of_studies).action_reject()
        self.assertTrue(grade_line.is_convalidated)

    def test_new_grade_lines_start_convalidated(self):
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_grant()
        grade_line = self._enroll_and_grade()
        self.assertTrue(grade_line.is_convalidated)
        self.assertEqual(grade_line.final_score, 5)

    def test_em_wizard_skips_convalidated_subjects(self):
        grade_line = self._enroll_and_grade()
        wizard = self.env['ems.em_grading_wizard'].create({'group_id': self.group.id})
        self.assertIn(grade_line, wizard._live_subject_lines(self.student))
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertNotIn(grade_line, wizard._live_subject_lines(self.student))

    def test_year_record_copies_the_convalidation(self):
        self._enroll_and_grade()
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_grant()
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        self.assertTrue(subject_record.is_convalidated)
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.final_grade, 5)
        self.assertFalse(subject_record.final_pending)

    def test_frozen_year_record_follows_a_late_resolution(self):
        self._enroll_and_grade()
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        self.assertEqual(subject_record.state, 'failed')
        request = self._request()
        line = self._line(request).with_user(self.head_of_studies)
        line.action_forward()
        self.assertFalse(subject_record.is_convalidated)
        line.action_grant()
        self.assertTrue(subject_record.is_convalidated)
        self.assertEqual(subject_record.state, 'passed')
        self.assertTrue(subject_record.has_final)
        line.action_reject()
        self.assertFalse(subject_record.is_convalidated)
        self.assertEqual(subject_record.state, 'failed')
        self.assertFalse(subject_record.has_final)

    def test_other_course_year_records_are_left_alone(self):
        self._enroll_and_grade()
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        later_course = self.env['ems.course'].create({'start': 2095, 'end': 2096})
        request = self._request(course_id=later_course.id)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self.assertFalse(subject_record.is_convalidated)

    # --- portal helpers ------------------------------------------------------

    def test_portal_study_prefers_the_enrollment_being_made(self):
        Convalidation = self.env['ems.convalidation']
        self.assertEqual(Convalidation._ems_portal_study(self.student), self.study)
        _level, other_study = create_level_study(self, 'TCVO', level={'allows_convalidation': True},
                                                 study={'code': 'TCVO001'})
        self.env['sale.order'].create({
            'partner_id': self.student.id, 'ems_study_id': other_study.id,
            'ems_course_id': Convalidation._default_course_id().id,
        })
        self.assertEqual(Convalidation._ems_portal_study(self.student), other_study)

    def test_portal_study_must_allow_convalidations(self):
        self.level.allows_convalidation = False
        self.assertFalse(self.env['ems.convalidation']._ems_portal_study(self.student))

    def test_requestable_subjects_skip_the_ones_in_course(self):
        Convalidation = self.env['ems.convalidation']
        self.assertEqual(Convalidation._ems_portal_requestable_subjects(self.student, self.study),
                         self.subject | self.other_subject)
        request = self._request()
        self.assertEqual(Convalidation._ems_portal_requestable_subjects(self.student, self.study),
                         self.other_subject)
        # A rejected subject can be asked for again, with new documents.
        self._line(request).with_user(self.head_of_studies).action_reject()
        self.assertEqual(Convalidation._ems_portal_requestable_subjects(self.student, self.study),
                         self.subject | self.other_subject)
