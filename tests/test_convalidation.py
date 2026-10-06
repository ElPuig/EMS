import base64

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import (create_level_study, create_role_employee, create_role_user, mock_outgoing_email,
                     next_student_id)


def set_convalidation_period(env, start, end):
    """The portal request period, as (day, month, time) tuples for its opening and its closing."""
    (start_day, start_month, start_time), (end_day, end_month, end_time) = start, end
    env.company.write({
        'convalidation_start_day': start_day, 'convalidation_start_month': str(start_month),
        'convalidation_start_time': start_time,
        'convalidation_end_day': end_day, 'convalidation_end_month': str(end_month),
        'convalidation_end_time': end_time,
    })


def open_convalidation_period(env):
    """A period covering the whole year, so the portal accepts requests whenever the suite runs."""
    set_convalidation_period(env, (1, 1, 0.0), (31, 12, 23 + 59 / 60))


def close_convalidation_period(env):
    """A two-day period six months away from today, so the portal refuses requests whenever the
    suite runs."""
    month = (fields.Date.today().month + 5) % 12 + 1
    set_convalidation_period(env, (1, month, 0.0), (2, month, 0.0))


def create_convalidation_fixtures(cls):
    """A vocational training study (its level allows convalidations) with two graded subjects and a
    tutorship, a group, the running course, and one user per role involved (Head of Studies,
    secretary, teacher). Shared with the portal and tour tests. The portal request period is open
    all year long."""
    open_convalidation_period(cls.env)
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
    cls.director = create_role_user(cls, 'director', 'test_convalidation_director', name='Convalidation Director')
    create_role_employee(cls, cls.director)


def hold_position(env, role_xmlid, user):
    """Give `user`'s employee the position `role_xmlid` (ems.role_dhos, ems.role_director). The
    roles are hierarchy-managed (set from the top-level department's form); tests write them
    through the sync's own context, as tests/test_absence.py does."""
    env.ref(role_xmlid).sudo().with_context(ems_syncing_roles=True).write(
        {'employee_ids': [(6, 0, user.employee_ids.ids)]})


class TestConvalidation(TransactionCase):
    """Issues #276 and #529 - subject convalidation requests and the circuit that resolves them:
    the Head of Studies reviews (and grades) them; the Director issues the centre's resolution, or
    the Ministry resolves them; the secretariat registers every resolution in Esfera and closes the
    request. See docs/en/developers/grades/convalidation.md."""

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

    def _refuse(self, lines, reason="Not equivalent"):
        lines = lines.with_user(self.head_of_studies)
        lines.write({'rejection_reason': reason})
        lines.action_reject()

    def _proposed(self, subjects=None, grade=None, **kwargs):
        """A request whose subjects are all granted by the Head of Studies and proposed to the
        Director."""
        request = self._request(subjects, **kwargs)
        lines = request.line_ids.with_user(self.head_of_studies)
        lines.action_grant()
        if grade is not None:
            lines.write({'grade': grade})
        request.with_user(self.head_of_studies).action_propose()
        return request

    def _resolved(self, subjects=None, grade=None, **kwargs):
        """A request the Director has resolved: the state the secretariat picks it up in."""
        request = self._proposed(subjects, grade, **kwargs)
        request.with_user(self.director).action_resolve()
        return request

    def _completed(self, subjects=None, grade=None, **kwargs):
        request = self._resolved(subjects, grade, **kwargs)
        request.with_user(self.secretary).action_complete()
        return request

    def _close(self, request):
        """Take a request whose subjects are all decided through the Director and the
        secretariat."""
        request.with_user(self.head_of_studies).action_propose()
        request.with_user(self.director).action_resolve()
        request.with_user(self.secretary).action_complete()
        return request

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

    def test_new_request_is_pending(self):
        request = self._request(self.subject | self.other_subject)
        self.assertEqual(request.state, 'pending')
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

    # --- the circuit ---------------------------------------------------------

    def test_full_circuit_through_the_director(self):
        request = self._request(self.subject | self.other_subject)
        lines = request.line_ids.with_user(self.head_of_studies)
        lines.action_grant()
        # Deciding the subjects is not yet the proposal: the request stays with the Head.
        self.assertEqual(request.state, 'pending')
        request.with_user(self.head_of_studies).action_propose()
        self.assertEqual(request.state, 'direction')
        self.assertEqual(request.validated_by_id, self.head_of_studies)
        self.assertTrue(request.validation_date)
        self.assertFalse(request.resolution_pdf_id)
        request.with_user(self.director).action_resolve()
        self.assertEqual(request.state, 'in_progress')
        self.assertEqual(request.signed_by_id, self.director)
        self.assertTrue(request.signature_date)
        self.assertFalse(request.resolution_date)
        self.assertEqual(request.resolution_pdf_id.mimetype, 'application/pdf')
        self.assertEqual(request.resolution_pdf_id.res_id, request.id)
        request.with_user(self.secretary).action_complete()
        self.assertEqual(request.state, 'completed')
        self.assertEqual(request.resolved_by_id, self.secretary)
        self.assertTrue(request.resolution_date)
        self.assertEqual(request.granted_count, 2)

    def test_proposal_needs_every_subject_decided(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_propose()

    def test_refusal_needs_its_reason(self):
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_reject()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_propose()
        self._line(request).with_user(self.head_of_studies).write({'rejection_reason': "Different hours"})
        request.with_user(self.head_of_studies).action_propose()
        self.assertEqual(request.state, 'direction')

    def test_full_refusal_goes_through_the_director_and_the_secretariat(self):
        """A refusal is a resolution too: the Director issues it, the secretariat registers it."""
        request = self._request(self.subject | self.other_subject)
        self._refuse(request.line_ids)
        request.with_user(self.head_of_studies).action_propose()
        self.assertEqual(request.state, 'direction')
        request.with_user(self.director).action_resolve()
        self.assertEqual(request.state, 'in_progress')
        self.assertFalse(self._resolution_mails(request))
        request.with_user(self.secretary).action_complete()
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.resolved_by_id, self.secretary)
        self.assertEqual(len(self._resolution_mails(request)), 1)

    def test_partially_granted_request_is_completed(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._refuse(self._line(request, self.other_subject))
        self._close(request)
        self.assertEqual(request.state, 'completed')
        self.assertEqual(request.granted_count, 1)

    def test_director_returns_the_proposal(self):
        hold_position(self.env, 'ems.role_dhos', self.head_of_studies)
        request = self._proposed()
        wizard = self.env['ems.convalidation.return_wizard'].with_user(self.director).create({
            'convalidation_id': request.id, 'reason': "Check the hours of the previous module"})
        wizard.action_return()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.return_reason, "Check the hours of the previous module")
        self.assertEqual(self._tasks(request, 'ems.mail_activity_convalidation_review').user_id, self.head_of_studies)
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_resolution'))
        # An internal matter: an internal note, nothing for the student's Communications page.
        note = request.message_ids.filtered(lambda message: 'Check the hours' in (message.body or ''))
        self.assertEqual(note.subtype_id, self.env.ref('mail.mt_note'))
        # The Head can change the decision again and propose anew, which clears the reason.
        self._line(request).with_user(self.head_of_studies).write({'grade': 7})
        request.with_user(self.head_of_studies).action_propose()
        self.assertEqual(request.state, 'direction')
        self.assertFalse(request.return_reason)

    def test_only_the_director_resolves(self):
        request = self._proposed()
        for user in (self.head_of_studies, self.secretary):
            with self.assertRaises(UserError):
                request.with_user(user).action_resolve()
            with self.assertRaises(UserError):
                request.with_user(user).action_return()
        self.assertEqual(request.state, 'direction')

    def test_nobody_changes_the_decision_once_proposed(self):
        request = self._proposed()
        line = self._line(request)
        for user in (self.head_of_studies, self.director):
            with self.assertRaises(UserError):
                line.with_user(user).action_reject()
            with self.assertRaises(UserError):
                line.with_user(user).write({'grade': 9})
        request.with_user(self.director).action_resolve()
        with self.assertRaises(UserError):
            line.with_user(self.secretary).write({'grade': 9})

    # --- resolved by the Ministry ----------------------------------------------

    def test_ministry_circuit_skips_the_director(self):
        hold_position(self.env, 'ems.role_dhos', self.head_of_studies)
        request = self._request()
        request.with_user(self.head_of_studies).action_send_to_ministry()
        self.assertEqual(request.state, 'ministry')
        self.assertTrue(request.resolved_by_ministry)
        self.assertTrue(request.ministry_date)
        # Still the Head's: the review task stays open while the Ministry answers.
        self.assertEqual(self._tasks(request, 'ems.mail_activity_convalidation_review').user_id, self.head_of_studies)
        # The applicant can no longer cancel it, but can still be asked for documents.
        with self.assertRaises(UserError):
            request.action_cancel()
        self.env['ems.convalidation.info_wizard'].with_user(self.head_of_studies).create({
            'convalidation_id': request.id, 'message': "Send the Ministry's form"}).action_send()
        # Waiting for it, still cancellable by nobody; once it arrives it is back with the Ministry.
        self.assertEqual(request.state, 'documentation')
        with self.assertRaises(UserError):
            request.action_cancel()
        request.with_user(self.head_of_studies).action_documentation_received()
        self.assertEqual(request.state, 'ministry')
        self._line(request).with_user(self.head_of_studies).write({'state': 'granted', 'grade': 8})
        request.with_user(self.head_of_studies).write({
            'ministry_resolution': base64.b64encode(b'%PDF-1.4 ministry'),
            'ministry_resolution_filename': 'ministry.pdf'})
        request.with_user(self.head_of_studies).action_ministry_resolved()
        self.assertEqual(request.state, 'in_progress')
        self.assertFalse(request.signed_by_id)
        self.assertEqual(request.resolution_pdf_id.name, 'ministry.pdf')
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_review'))
        self.assertIn(self.secretary, self._tasks(request, 'ems.mail_activity_convalidation_registration').user_id)
        request.with_user(self.secretary).action_complete()
        self.assertEqual(request.state, 'completed')
        mail = self._resolution_mails(request).filtered(lambda mail: mail.attachment_ids)
        self.assertEqual(mail.attachment_ids.name, 'ministry.pdf')

    def test_ministry_resolution_document_is_optional(self):
        request = self._request()
        request.with_user(self.head_of_studies).action_send_to_ministry()
        self._refuse(request.line_ids, "Refused by the Ministry")
        request.with_user(self.head_of_studies).action_ministry_resolved()
        self.assertFalse(request.resolution_pdf_id)
        request.with_user(self.secretary).action_complete()
        self.assertEqual(request.state, 'rejected')

    def test_only_a_pending_request_goes_to_the_ministry(self):
        request = self._proposed()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_send_to_ministry()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_ministry_resolved()

    # --- the resolution document ---------------------------------------------

    def _resolution_html(self, request):
        return self.env['ir.actions.report'].with_context(lang=request._ems_resolution_lang())._render_qweb_html(
            'ems.action_report_convalidation_resolution', request.ids)[0].decode()

    def test_resolution_shows_each_subject_and_its_outcome(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._refuse(self._line(request, self.other_subject), "Different competences")
        html = self._resolution_html(request)
        self.assertIn(request.name, html)
        self.assertIn(self.subject.code, html)
        self.assertIn(self.other_subject.name, html)
        self.assertIn("Different competences", html)
        self.assertIn("1085/2020", html)

    def test_default_grade_reads_convalidated(self):
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._line(request, self.other_subject).with_user(self.head_of_studies).write({'state': 'granted', 'grade': 8})
        self.assertTrue(self._line(request)._ems_is_default_grade())
        self.assertFalse(self._line(request, self.other_subject)._ems_is_default_grade())

    def test_legal_grounds_and_appeal_are_configurable(self):
        request = self._request(basis='certificate')
        standard = request._ems_resolution_legal_grounds()
        self.assertTrue(standard)
        self.env.company.write({
            'convalidation_legal_certificate': "Custom grounds for certificates",
            'convalidation_appeal_text': "Custom appeal text",
        })
        self.assertEqual(request._ems_resolution_legal_grounds(), "Custom grounds for certificates")
        self.assertNotEqual(self._request(self.other_subject)._ems_resolution_legal_grounds(),
                            "Custom grounds for certificates")
        html = self._resolution_html(request)
        self.assertIn("Custom grounds for certificates", html)
        self.assertIn("Custom appeal text", html)

    def test_signatory_is_the_director_unless_signed_by_delegation(self):
        hold_position(self.env, 'ems.role_director', self.director)
        request = self._proposed()
        request.sudo().signed_by_id = self.head_of_studies
        self.assertEqual(request._ems_resolution_signatory(), self.director.employee_ids[:1].name)
        self.env.company.convalidation_sign_by_delegation = True
        self.assertEqual(request._ems_resolution_signatory(), self.head_of_studies.name)

    def test_minor_resolution_names_the_representative(self):
        minor, family = self._minor_with_family()
        request = self._request(student=minor, requester_id=family.id)
        self.assertEqual(request._ems_resolution_representative(), family)
        self.assertFalse(self._request(self.other_subject)._ems_resolution_representative())

    def test_cancel_and_reopen(self):
        request = self._request()
        request.with_user(self.secretary).action_cancel()
        self.assertEqual(request.state, 'cancelled')
        request.with_user(self.secretary).action_reopen()
        self.assertEqual(request.state, 'pending')

    def test_cannot_cancel_once_proposed(self):
        request = self._proposed()
        with self.assertRaises(UserError):
            request.action_cancel()

    def test_completed_request_is_closed(self):
        request = self._completed()
        with self.assertRaises(UserError):
            request.with_user(self.secretary).action_complete()
        with self.assertRaises(UserError):
            self._line(request).with_user(self.head_of_studies).action_reject()

    # --- access --------------------------------------------------------------

    def test_secretary_cannot_propose(self):
        request = self._request()
        self._line(request).with_user(self.head_of_studies).action_grant()
        with self.assertRaises(UserError):
            request.with_user(self.secretary).action_propose()
        with self.assertRaises(UserError):
            request.with_user(self.secretary).action_send_to_ministry()

    def test_what_was_filed_cannot_be_changed(self):
        request = self._request(user=self.secretary, student_notes="Passed in SMX")
        later_course = self.env['ems.course'].create({'start': 2095, 'end': 2096})
        other_student = self.env['res.partner'].create({
            'name': 'Convalidation Other Student', 'contact_type': 'student', 'student_id': next_student_id()})
        _level, other_study = create_level_study(self, 'TCVO', level={'allows_convalidation': True},
                                                 study={'code': 'TCVO001'})
        for vals in ({'student_notes': "Rewritten"}, {'basis': 'other'}, {'course_id': later_course.id},
                     {'student_id': other_student.id}, {'study_id': other_study.id}, {'state': 'completed'}):
            for user in (self.secretary, self.head_of_studies, self.director):
                with self.assertRaises(UserError):
                    request.with_user(user).write(vals)
        self.assertEqual(request.student_notes, "Passed in SMX")
        self.assertEqual(request.basis, 'prior_studies')

    def test_secretary_cannot_decide_a_subject(self):
        request = self._request(user=self.secretary)
        request.with_user(self.secretary).write({'resolution_notes': 'Received on paper'})
        self._line(request).with_user(self.secretary).write({'resolution_notes': 'Certificate attached'})
        with self.assertRaises(UserError):
            self._line(request).with_user(self.secretary).action_grant()
        with self.assertRaises(UserError):
            self.env['ems.convalidation.line'].with_user(self.secretary).create({
                'convalidation_id': request.id, 'subject_id': self.other_subject.id, 'state': 'granted'})

    def test_head_of_studies_cannot_complete(self):
        request = self._resolved()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_complete()

    def test_director_can_review(self):
        request = self._request()
        self._line(request).with_user(self.director).action_grant()
        request.with_user(self.director).action_propose()
        self.assertEqual(request.state, 'direction')

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

    # --- the grade -----------------------------------------------------------

    def test_grade_defaults_to_five_and_is_set_by_the_head_of_studies(self):
        request = self._request()
        line = self._line(request).with_user(self.head_of_studies)
        self.assertEqual(line.grade, 5)
        line.write({'grade': 8})
        self.assertEqual(line.grade, 8)

    def test_secretary_cannot_touch_the_grade_of_a_pending_request(self):
        request = self._request()
        with self.assertRaises(UserError):
            self._line(request).with_user(self.secretary).write({'grade': 9})

    def test_grade_must_be_a_passing_one(self):
        request = self._request()
        line = self._line(request).with_user(self.head_of_studies)
        with self.assertRaises(ValidationError):
            line.write({'grade': 4})
        with self.assertRaises(ValidationError):
            line.write({'grade': 11})

    def test_remarks_record_where_the_resolution_comes_from(self):
        request = self._request()
        line = self._line(request).with_user(self.head_of_studies)
        line.write({'resolution_notes': "Granted by the Department, file no. 1234"})
        self.assertEqual(line.resolution_notes, "Granted by the Department, file no. 1234")

    # --- the student's notice ------------------------------------------------

    def _resolution_mails(self, request):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'ems.convalidation'), ('res_id', '=', request.id)])

    def test_only_the_final_outcome_is_emailed(self):
        request = self._resolved(self.subject | self.other_subject)
        # Proposing and resolving are internal steps: the student sees them on the portal, without
        # an email.
        self.assertFalse(self._resolution_mails(request))
        request.with_user(self.secretary).action_complete()
        mails = self._resolution_mails(request)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_to, self.student.email)
        # With the official resolution attached.
        self.assertEqual(mails.attachment_ids, request.resolution_pdf_id)
        self.assertTrue(request.message_ids.filtered(lambda message: self.student.email in (message.body or '')))
        # Editing a completed request does not notify again.
        request.with_user(self.secretary).resolution_notes = 'See you in September'
        self.assertEqual(len(self._resolution_mails(request)), 1)

    def _minor_with_family(self):
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
        return minor, family

    def test_minor_resolution_goes_to_the_student_and_the_family(self):
        minor, family = self._minor_with_family()
        request = self._completed(student=minor)
        self.assertEqual(set(self._resolution_mails(request).mapped('email_to')), {minor.email, family.email})

    def test_adult_resolution_reaches_the_family_only_when_shared(self):
        adult, family = self._minor_with_family()
        adult.birth_date = '2000-01-01'
        self.assertEqual(adult._ems_convalidation_recipients(), adult)
        # auth_share is a stored compute read from an accepted 'share' authorization.
        self.env.flush_all()
        self.env.cr.execute("UPDATE res_partner SET auth_share = TRUE WHERE id = %s", (adult.id,))
        adult.invalidate_recordset(['auth_share'])
        self.assertEqual(adult._ems_convalidation_recipients(), adult | family)

    def test_resolution_without_any_email_is_logged(self):
        student = self.env['res.partner'].create({
            'name': 'Convalidation No Email', 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': '2000-01-01'})
        request = self._completed(student=student)
        self.assertFalse(self._resolution_mails(request))
        self.assertTrue(request.message_ids.filtered(lambda message: 'could not be emailed' in (message.body or '')))

    def test_student_communications_are_comments_nobody_follows(self):
        request = self._request(user=self.head_of_studies)
        comment = self.env.ref('mail.mt_comment')
        submitted = request.message_ids.filtered(lambda message: message.subtype_id == comment)
        self.assertEqual(submitted.mapped('subject'), ['Convalidation request submitted'])
        self.assertIn(self.subject.display_name, submitted.body)
        request.invalidate_recordset(['message_follower_ids', 'message_partner_ids'])
        self.assertFalse(request.message_partner_ids)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._close(request)
        request.invalidate_recordset(['message_ids'])
        resolved = request.message_ids.filtered(lambda message: message.subtype_id == comment) - submitted
        # One comment for the proposal, one for the Director's resolution, one for the
        # registered resolution itself.
        self.assertEqual(len(resolved), 3)
        self.assertIn(self.student.name, resolved[0].subject)
        self.assertEqual(len(self._resolution_mails(request)), 1)

    def test_nobody_ends_up_following_a_request(self):
        """Posting a comment subscribes its author unless told not to: the Head of Studies
        asking for documents and validating, and the secretary completing, all post. Followers
        would be emailed every later message - the resolution included."""
        request = self._request()
        self.env['ems.convalidation.info_wizard'].with_user(self.head_of_studies).create({
            'convalidation_id': request.id, 'message': "Attach the certificate"}).action_send()
        request._ems_portal_add_documents(self.env['ir.attachment'], "Here it is")
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._close(request)
        request.invalidate_recordset(['message_follower_ids', 'message_partner_ids'])
        self.assertFalse(request.message_follower_ids)
        # So the request emails nobody but the student: the information request and the
        # resolution, no follower copy of either.
        mails = self._resolution_mails(request)
        self.assertEqual(len(mails), 2)
        self.assertEqual(set(mails.mapped('email_to')), {self.student.email})

    def test_cancel_and_reopen_are_communicated(self):
        request = self._request()
        request.with_user(self.secretary).action_cancel()
        request.with_user(self.secretary).action_reopen()
        self.assertEqual(
            request.message_ids.filtered(lambda message: message.subtype_id == self.env.ref('mail.mt_comment'))
            .mapped('subject'),
            ['Convalidation request reopened', 'Convalidation request cancelled', 'Convalidation request submitted'])

    # --- asking the student for more documentation ---------------------------

    def _ask_for_documentation(self, request, message=None, reason=None):
        vals = {'convalidation_id': request.id, 'message': message}
        if reason:
            vals['reason_id'] = reason.id
        self.env['ems.convalidation.info_wizard'].with_user(self.head_of_studies).create(vals).action_send()

    def test_head_of_studies_asks_for_documentation(self):
        request = self._request()
        self._ask_for_documentation(request, "Please attach the academic certificate of your previous studies.")
        # The request now waits for the applicant (issue #577).
        self.assertEqual(request.state, 'documentation')
        # Kept on the request, for the portal to show it next to the answer form.
        self.assertEqual(request.info_request_reason_id,
                         self.env.ref('ems.convalidation_info_reason_previous_centre'))
        self.assertEqual(request.info_request, "Please attach the academic certificate of your previous studies.")
        self.assertTrue(request.info_request_date)
        mails = self.env['mail.mail'].sudo().search([
            ('model', '=', 'ems.convalidation'), ('res_id', '=', request.id)])
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_to, self.student.email)
        self.assertTrue(request.message_ids.filtered(
            lambda message: 'academic certificate' in (message.body or '')))

    def test_the_most_usual_reason_is_preselected(self):
        """Like the strike reasons: the first by its own order, the missing data of the previous
        centre - almost always the reason."""
        reason = self.env.ref('ems.convalidation_info_reason_previous_centre')
        wizard = self.env['ems.convalidation.info_wizard'].with_user(self.head_of_studies).create({
            'convalidation_id': self._request().id})
        self.assertEqual(wizard.reason_id, reason)
        reason.sequence = 100
        wizard = self.env['ems.convalidation.info_wizard'].with_user(self.head_of_studies).create({
            'convalidation_id': self._request(self.other_subject).id})
        self.assertNotEqual(wizard.reason_id, reason)

    def test_the_reason_alone_is_enough_and_travels_in_the_email(self):
        request = self._request()
        reason = self.env.ref('ems.convalidation_info_reason_syllabus')
        self._ask_for_documentation(request, reason=reason)
        self.assertEqual(request.info_request_reason_id, reason)
        self.assertFalse(request.info_request)
        mail = self.env['mail.mail'].sudo().search([
            ('model', '=', 'ems.convalidation'), ('res_id', '=', request.id)])
        reason_text = reason.with_context(lang=self.student.lang or 'en_US').name
        self.assertIn(reason_text, mail.body_html)

    def test_the_answer_puts_the_request_back_under_review(self):
        hold_position(self.env, 'ems.role_dhos', self.head_of_studies)
        request = self._request()
        self._ask_for_documentation(request, "Attach the certificate")
        # Nothing for the Head of Studies to do while the applicant has it.
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_review'))
        request._ems_portal_add_documents(self.env['ir.attachment'], "Here it is")
        self.assertEqual(request.state, 'pending')
        self.assertEqual(self._tasks(request, 'ems.mail_activity_convalidation_review').user_id,
                         self.head_of_studies)

    def test_documentation_received_by_other_means(self):
        request = self._request()
        self._ask_for_documentation(request, "Attach the certificate")
        with self.assertRaises(UserError):
            request.with_user(self.secretary).action_documentation_received()
        request.with_user(self.head_of_studies).action_documentation_received()
        self.assertEqual(request.state, 'pending')
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_documentation_received()

    def test_subjects_can_be_decided_but_not_proposed_while_waiting(self):
        request = self._request()
        self._ask_for_documentation(request, "Attach the certificate")
        self._line(request).with_user(self.head_of_studies).action_grant()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_propose()
        with self.assertRaises(UserError):
            request.with_user(self.head_of_studies).action_send_to_ministry()

    def test_the_applicant_can_cancel_while_waiting(self):
        request = self._request()
        self._ask_for_documentation(request, "Attach the certificate")
        request.action_cancel()
        self.assertEqual(request.state, 'cancelled')

    def test_information_cannot_be_asked_for_once_completed(self):
        request = self._completed()
        with self.assertRaises(UserError):
            self.env['ems.convalidation.info_wizard'].with_user(self.head_of_studies).create({
                'convalidation_id': request.id, 'message': "Too late"}).action_send()

    # --- tasks ---------------------------------------------------------------

    def _tasks(self, request, xmlid):
        return self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'ems.convalidation'), ('res_id', '=', request.id),
            ('activity_type_id', '=', self.env.ref(xmlid).id)])

    def test_tasks_follow_the_circuit(self):
        """The review is the Deputy Head of Studies', the resolution the Director's and the
        registration the secretariat's, straight from who holds each position: nothing to
        configure."""
        hold_position(self.env, 'ems.role_dhos', self.head_of_studies)
        hold_position(self.env, 'ems.role_director', self.director)
        request = self._request()
        self.assertEqual(self._tasks(request, 'ems.mail_activity_convalidation_review').user_id,
                         self.head_of_studies)
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_registration'))
        self._line(request).with_user(self.head_of_studies).action_grant()
        request.with_user(self.head_of_studies).action_propose()
        # The Head's task is done; the Director gets their own.
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_review'))
        self.assertEqual(self._tasks(request, 'ems.mail_activity_convalidation_resolution').user_id, self.director)
        request.with_user(self.director).action_resolve()
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_resolution'))
        registered = self._tasks(request, 'ems.mail_activity_convalidation_registration')
        self.assertIn(self.secretary, registered.user_id)
        # The EMS administrator holds every group, so it never collects the secretariat's tasks.
        self.assertNotIn(self.env.ref('base.user_admin'), registered.user_id)
        request.with_user(self.secretary).action_complete()
        self.assertFalse(self._tasks(request, 'ems.mail_activity_convalidation_registration'))
        # Scheduling a task never subscribes its assignee to the student's own messages.
        request.invalidate_recordset(['message_follower_ids', 'message_partner_ids'])
        self.assertFalse(request.message_partner_ids)

    def test_cancelling_closes_the_pending_task(self):
        hold_position(self.env, 'ems.role_dhos', self.head_of_studies)
        request = self._request()
        request.action_cancel()
        self.assertFalse(request.activity_ids)

    def test_tasks_are_not_in_task_assignment(self):
        """Owned by positions, not by a configurable list: they stay out of that screen, like
        attendance corrections (docs/en/developers/shared/task_assignment.md)."""
        for xmlid in ('ems.mail_activity_convalidation_review', 'ems.mail_activity_convalidation_resolution',
                      'ems.mail_activity_convalidation_registration'):
            self.assertFalse(self.env.ref(xmlid).ems_task_assignment)

    # --- the student's own background ----------------------------------------

    def test_title_obtained_at_the_centre_is_flagged(self):
        request = self._request()
        self.assertFalse(request.has_centre_title)
        self.env['ems.student.year_record'].sudo().create({
            'student_id': self.student.id, 'course_id': self.course.id, 'title_obtained': True})
        request.invalidate_recordset(['has_centre_title'])
        self.assertTrue(request.has_centre_title)

    # --- grades --------------------------------------------------------------

    def test_grades_only_change_once_the_secretariat_completes(self):
        """A round already closed keeps the student's line, now reading the convalidation."""
        grade_line = self._enroll_and_grade(state='final')
        request = self._resolved(grade=7)
        self.assertFalse(grade_line.is_convalidated)
        self.assertFalse(grade_line.has_final)
        request.with_user(self.secretary).action_complete()
        self.assertTrue(grade_line.is_convalidated)
        self.assertTrue(grade_line.internal_is_complete)
        self.assertTrue(grade_line.has_final)
        self.assertEqual(grade_line.final_score, 7)

    def test_default_grade_reaches_the_grades(self):
        grade_line = self._enroll_and_grade(state='final')
        self._completed()
        self.assertEqual(grade_line.final_score, 5)

    # --- the student stops taking the subject --------------------------------

    def test_completion_withdraws_the_student_from_the_subject(self):
        """Even with grades already written: the convalidation replaces them."""
        grade_line = self._enroll_and_grade()
        session = grade_line.grade_session_id
        session.grade_outcome_line_ids.filtered(lambda line: line.student_id == self.student).write(
            {'score': 6, 'is_scored': True})
        self._completed()
        self.assertFalse(self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.subject.id)]))
        self.assertFalse(grade_line.exists())
        self.assertNotIn(self.student, session.grade_outcome_line_ids.student_id)

    def test_only_granted_subjects_are_withdrawn(self):
        self._enroll_and_grade()
        self._enroll_and_grade(self.other_subject)
        request = self._request(self.subject | self.other_subject)
        self._line(request).with_user(self.head_of_studies).action_grant()
        self._refuse(self._line(request, self.other_subject))
        self._close(request)
        enrolled = self.env['ems.enrollment'].search([('student_id', '=', self.student.id)]).subject_id
        self.assertEqual(enrolled, self.other_subject)

    def test_resolution_alone_does_not_withdraw(self):
        self._enroll_and_grade()
        self._resolved()
        self.assertTrue(self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.subject.id)]))

    def test_placement_does_not_enrol_a_convalidated_subject(self):
        self._completed()
        order = self.env['sale.order'].create({
            'partner_id': self.student.id, 'ems_study_id': self.study.id,
            'ems_course_id': self.course.id, 'ems_group_id': self.group.id, 'shift': 'morning',
        })
        order.order_line = [(0, 0, {'product_id': subject.product_id.id})
                            for subject in (self.subject | self.other_subject)]
        order._ems_apply_destination_placement()
        enrolled = self.env['ems.enrollment'].search([('student_id', '=', self.student.id)]).subject_id
        self.assertEqual(enrolled, self.other_subject)

    def test_teaching_staff_get_a_notice_on_the_student(self):
        teacher_employee = self.teacher.employee_ids[:1]
        tutor = create_role_user(self, 'teacher', 'test_convalidation_tutor', name='Convalidation Tutor')
        self.group.tutor_id = create_role_employee(self, tutor)
        self.env['ems.teaching'].create({
            'teacher_id': teacher_employee.id, 'group_id': self.group.id, 'subject_id': self.subject.id})
        self._enroll_and_grade()
        request = self._completed(grade=8)
        notices = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', self.student.id),
            ('activity_type_id', '=', self.env.ref('ems.mail_activity_convalidation_notice').id)])
        self.assertEqual(notices.user_id, self.teacher | tutor)
        self.assertIn(request.name, notices[0].note)
        self.assertIn(self.subject.display_name, notices[0].summary)
        # The notice is their to-do, not a subscription to the student's messages.
        self.student.invalidate_recordset(['message_follower_ids', 'message_partner_ids'])
        self.assertFalse((self.teacher | tutor).partner_id & self.student.message_partner_ids)

    # --- registration number -------------------------------------------------

    def test_requests_are_numbered_per_course(self):
        first, second = self._request(), self._request(self.other_subject)
        self.assertEqual(first.name, 'CONV-2094-95-0001')
        self.assertEqual(second.name, 'CONV-2094-95-0002')
        self.assertTrue(first.display_name.startswith('CONV-2094-95-0001'))
        later_course = self.env['ems.course'].create({'start': 2095, 'end': 2096})
        self.assertEqual(self._request(course_id=later_course.id).name, 'CONV-2095-96-0001')

    def test_convalidation_reaches_a_finalised_session(self):
        grade_line = self._enroll_and_grade(state='final')
        self._completed(grade=6)
        self.assertTrue(grade_line.is_convalidated)
        self.assertEqual(grade_line.final_score, 6)

    def test_flag_cannot_be_written_by_hand_on_a_closed_session(self):
        grade_line = self._enroll_and_grade(state='final')
        with self.assertRaises(Exception):
            grade_line.with_user(self.head_of_studies).write({'is_convalidated': True})

    def test_cancelled_request_restores_the_grade(self):
        grade_line = self._enroll_and_grade(state='final')
        request = self._completed()
        self.assertTrue(grade_line.is_convalidated)
        request.sudo().write({'state': 'cancelled'})
        self.assertFalse(grade_line.is_convalidated)
        self.assertFalse(grade_line.has_final)

    def test_deleted_line_restores_the_grade(self):
        grade_line = self._enroll_and_grade(state='final')
        request = self._completed(self.subject | self.other_subject)
        self._line(request).sudo().unlink()
        self.assertFalse(grade_line.is_convalidated)
        request.sudo().unlink()
        self.assertFalse(request.exists())

    def test_rejected_duplicate_does_not_undo_a_grant(self):
        grade_line = self._enroll_and_grade(state='final')
        self._completed(grade=8)
        second = self._request()
        self._refuse(second.line_ids)
        self._close(second)
        self.assertEqual(second.state, 'rejected')
        self.assertTrue(grade_line.is_convalidated)
        self.assertEqual(grade_line.final_score, 8)

    def test_new_grade_lines_start_convalidated(self):
        self._completed(grade=9)
        grade_line = self._enroll_and_grade()
        self.assertTrue(grade_line.is_convalidated)
        self.assertEqual(grade_line.final_score, 9)

    def test_em_wizard_skips_convalidated_subjects(self):
        grade_line = self._enroll_and_grade()
        wizard = self.env['ems.em_grading_wizard'].create({'group_id': self.group.id})
        self.assertIn(grade_line, wizard._live_subject_lines(self.student))
        self._completed()
        self.assertNotIn(grade_line, wizard._live_subject_lines(self.student))

    # --- the history of a course still running --------------------------------

    def _history(self, course=None):
        return self.env['ems.student.year_record'].search([
            ('student_id', '=', self.student.id), ('course_id', '=', (course or self.course).id)])

    def test_completion_opens_a_provisional_history(self):
        """The history is where teachers look grades up, and the running course has none until
        it closes: completing opens it, marked as the current course, with only the subject."""
        self._enroll_and_grade()
        request = self._completed(grade=8)
        record = self._history()
        self.assertTrue(record.is_provisional)
        self.assertFalse(record.academic_result)
        self.assertFalse(record.title_obtained)
        self.assertEqual(record.study_id, self.study)
        self.assertEqual(record.group_id, self.group)
        self.assertEqual(record.subject_record_ids.subject_id, self.subject)
        self.assertEqual(record.subject_record_ids.final_grade, 8)
        self.assertEqual(record.subject_record_ids.convalidation_number, request.name)
        # Readable by every teacher, like the rest of the history (issue #393).
        self.assertEqual(record.with_user(self.teacher).subject_record_ids.final_grade, 8)

    def test_later_convalidations_join_the_same_record(self):
        self._completed()
        self._completed(self.other_subject, grade=6)
        record = self._history()
        self.assertEqual(len(record), 1)
        self.assertEqual(record.subject_record_ids.subject_id, self.subject | self.other_subject)

    def test_closing_the_course_completes_the_provisional_record(self):
        self._enroll_and_grade(self.other_subject)
        self._completed(grade=7)
        record = self._history()
        self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        self.assertEqual(self._history(), record)
        self.assertFalse(record.is_provisional)
        self.assertEqual(record.subject_record_ids.subject_id, self.subject | self.other_subject)
        convalidated = record.subject_record_ids.filtered('is_convalidated')
        self.assertEqual((convalidated.subject_id, convalidated.final_grade), (self.subject, 7))

    def test_leaving_the_group_freezes_despite_a_provisional_record(self):
        """freeze_on_leaving() skips a year already frozen; a provisional record is not one."""
        self._enroll_and_grade(self.other_subject)
        self._completed()
        record = self.env['ems.student.year_record'].freeze_on_leaving(self.student, self.group)
        self.assertEqual(record, self._history())
        self.assertFalse(record.is_provisional)
        self.assertEqual(record.subject_record_ids.subject_id, self.subject | self.other_subject)

    def test_revoked_on_a_running_course_leaves_no_trace(self):
        request = self._completed()
        self.assertTrue(self._history())
        request.sudo().write({'state': 'cancelled'})
        self.assertFalse(self._history())

    def test_grade_review_refuses_a_running_course(self):
        self._completed()
        record = self._history()
        wizard = self.env['ems.grade_review_wizard'].with_user(self.head_of_studies).create({
            'record_id': record.id, 'operation': 'remove',
            'subject_record_id': record.subject_record_ids.id, 'resolution': 'Test'})
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_year_record_keeps_the_withdrawn_subject(self):
        """Completing deleted the enrollment and its open grade line, yet the year the subject
        was convalidated in still records it as passed, with its file number."""
        self._enroll_and_grade()
        request = self._completed(grade=7)
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        self.assertTrue(subject_record.is_convalidated)
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.final_grade, 7)
        self.assertEqual(subject_record.convalidation_number, request.name)
        self.assertFalse(subject_record.final_pending)
        self.assertFalse(subject_record.outcome_record_ids)
        self.assertFalse(record.is_provisional)

    def test_year_record_of_a_closed_round_carries_the_file(self):
        self._enroll_and_grade(state='final')
        request = self._completed(grade=6)
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        self.assertEqual(subject_record.final_grade, 6)
        self.assertEqual(subject_record.convalidation_number, request.name)

    def test_frozen_year_record_gains_a_missing_subject(self):
        """A history frozen before the subject ever had a grade line gets it added when the
        convalidation of that same course is completed."""
        self._enroll_and_grade(self.other_subject)
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        self.assertNotIn(self.subject, record.subject_record_ids.subject_id)
        request = self._completed(grade=9)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        self.assertTrue(subject_record.is_convalidated)
        self.assertEqual(subject_record.final_grade, 9)
        self.assertEqual(subject_record.convalidation_number, request.name)

    def test_frozen_year_record_follows_a_late_resolution(self):
        self._enroll_and_grade()
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        self.assertEqual(subject_record.state, 'failed')
        request = self._resolved(grade=6)
        self.assertFalse(subject_record.is_convalidated)
        request.with_user(self.secretary).action_complete()
        self.assertTrue(subject_record.is_convalidated)
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.final_grade, 6)
        self.assertTrue(subject_record.has_final)
        request.sudo().write({'state': 'cancelled'})
        self.assertFalse(subject_record.is_convalidated)
        self.assertEqual(subject_record.state, 'failed')
        self.assertFalse(subject_record.has_final)

    def test_grade_review_leaves_a_convalidated_subject_alone(self):
        """Issue #493's grade review recomputes an archived subject from its own RAs; a
        convalidated one has none of its own, so recomputing it would wipe the resolution."""
        self._enroll_and_grade()
        self._completed(grade=8)
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        subject_record.sudo()._recompute_from_outcomes()
        self.assertTrue(subject_record.is_convalidated)
        self.assertEqual(subject_record.final_grade, 8)
        self.assertEqual(subject_record.state, 'passed')

    def test_other_course_year_records_are_left_alone(self):
        self._enroll_and_grade()
        record = self.env['ems.student.year_record'].generate_for_students(self.student, self.course)
        subject_record = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject)
        later_course = self.env['ems.course'].create({'start': 2095, 'end': 2096})
        self._completed(course_id=later_course.id)
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
        self._refuse(request.line_ids)
        self.assertEqual(Convalidation._ems_portal_requestable_subjects(self.student, self.study),
                         self.subject | self.other_subject)
