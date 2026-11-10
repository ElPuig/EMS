from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

from .common import create_level_study_group, create_role_user, mock_outgoing_email, next_student_id

PDF = b'%PDF-1.4 erasmus test'


def create_erasmus_fixtures(cls):
    """A published, accepting call with one modality for a test CFGM-like level, a required, an
    optional, a minors-only and a confidential document; an adult student of that level, a student
    of another level, and an Erasmus team user and a Head of Studies (login doubles as password)."""
    cls.level, cls.study, cls.group = create_level_study_group(cls, 'TERA', group={'course': 1})
    cls.other_level, _study, cls.other_group = create_level_study_group(cls, 'TERB')
    now = fields.Datetime.now()
    cls.call = cls.env['ems.erasmus.call'].create({
        'name': 'Test Erasmus Call',
        'date_open': now - timedelta(days=1),
        'date_close': now + timedelta(days=10),
        'modality_ids': [(0, 0, {'name': 'TGM', 'level_ids': [(6, 0, cls.level.ids)],
                                 'project': 'ka121_vet', 'places': 6})],
        'document_ids': [
            (0, 0, {'name': 'Europass CV', 'requirement': 'required', 'sequence': 1}),
            (0, 0, {'name': 'Language certificate', 'requirement': 'optional', 'sequence': 2}),
            (0, 0, {'name': 'Family authorization', 'requirement': 'minor', 'sequence': 3}),
            (0, 0, {'name': 'Fewer opportunities evidence', 'requirement': 'optional',
                    'confidential': True, 'sequence': 4}),
        ],
    })
    # Issue #767 fills the deadlines in from the closing date: the tests set the ones they need.
    cls.call.write({'subsanation_deadline': False, 'interview_deadline': False, 'claims_deadline': False,
                    'acceptance_deadline': False})
    cls.call.action_publish()
    cls.cv, cls.certificate, cls.authorization, cls.evidence = cls.call.document_ids.sorted('sequence')
    cls.student, cls.minor, cls.outsider = cls.env['res.partner'].create([
        {'name': 'Erasmus Test Student', 'contact_type': 'student', 'student_id': next_student_id(),
         'main_group_id': cls.group.id, 'birth_date': '2000-01-01',
         'email': 'erasmus.student@example.com'},
        {'name': 'Erasmus Test Minor', 'contact_type': 'student', 'student_id': next_student_id(),
         'main_group_id': cls.group.id, 'birth_date': '2015-01-01',
         'email': 'erasmus.minor@example.com'},
        {'name': 'Erasmus Test Outsider', 'contact_type': 'student', 'student_id': next_student_id(),
         'main_group_id': cls.other_group.id, 'birth_date': '2000-01-01'},
    ])
    cls.erasmus_user = create_role_user(cls, 'erasmus_coordinator', 'test_erasmus_team')
    cls.hos_user = create_role_user(cls, 'head_of_studies', 'test_erasmus_hos')
    cls.teacher_user = create_role_user(cls, 'teacher', 'test_erasmus_teacher')


def upload(application, call_document, name='file.pdf', content=PDF):
    application._ems_portal_save({}, {call_document.id: [(name, content)]})


@tagged('post_install', '-at_install')
class TestErasmusCall(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)

    def test_close_date_after_open_date(self):
        with self.assertRaises(ValidationError):
            self.call.copy({'date_close': self.call.date_open - timedelta(hours=1)})

    def test_a_new_call_shows_its_defaults_before_saving(self):
        """The 2026-11-04 usage test: the Documents tab was empty until the call was saved."""
        form = Form(self.env['ems.erasmus.call'])
        self.assertEqual(len(form.document_ids), 4, "No family authorisation: the receipt's copy informs the family")
        self.assertTrue(form.task_ids)
        form.audience = 'staff'
        self.assertEqual(len(form.document_ids), 1, "The staff call's own documents")
        self.assertFalse(form.modality_ids, "Issue #772: places per project instead.")
        self.assertFalse(form.document_ids._records[0]['single_file'], "A certificate per language")
        # Issue #767: a staff call hides its Documents tab.
        self.assertTrue(form._get_modifier('document_ids', 'invisible'))

    def test_publish_needs_a_modality_and_a_required_document(self):
        draft = self.env['ems.erasmus.call'].create({
            'name': 'Empty call', 'date_open': self.call.date_open, 'date_close': self.call.date_close,
        })
        draft.document_ids = [(5, 0, 0)]  # a new students' call brings its default documents
        with self.assertRaises(UserError):
            draft.action_publish()
        draft.modality_ids = [(0, 0, {'name': 'X', 'level_ids': [(6, 0, self.level.ids)]})]
        with self.assertRaises(UserError):
            draft.action_publish()
        draft.document_ids = [(0, 0, {'name': 'CV', 'requirement': 'required'})]
        draft.action_publish()
        self.assertEqual(draft.state, 'published')

    def test_duplicating_copies_modalities_and_documents(self):
        copy = self.call.copy()
        self.assertEqual(copy.state, 'draft')
        self.assertEqual(copy.modality_ids.mapped('name'), ['TGM'])
        self.assertEqual(len(copy.document_ids), 4)

    def test_a_level_belongs_to_one_modality_only(self):
        with self.assertRaises(ValidationError):
            self.call.modality_ids = [(0, 0, {'name': 'TGS', 'level_ids': [(6, 0, self.level.ids)]})]

    def test_accepting_only_between_the_dates(self):
        self.assertTrue(self.call.is_accepting)
        self.call.date_open = fields.Datetime.now() + timedelta(hours=1)
        self.assertFalse(self.call.is_accepting)
        self.call.write({'date_open': fields.Datetime.now() - timedelta(days=2),
                         'date_close': fields.Datetime.now() - timedelta(hours=1)})
        self.assertFalse(self.call.is_accepting)

    def test_eligibility_comes_from_the_modality_levels(self):
        self.assertEqual(self.call._ems_modality_for(self.student), self.call.modality_ids)
        self.assertFalse(self.call._ems_modality_for(self.outsider))
        self.assertIn(self.call, self.student._ems_erasmus_calls())
        self.assertNotIn(self.call, self.outsider._ems_erasmus_calls())
        self.assertTrue(self.student._ems_erasmus_portal_visible())
        self.assertFalse(self.outsider._ems_erasmus_portal_visible())

    def test_any_year_of_the_cycle_can_apply(self):
        self.group.course = 2
        self.assertEqual(self.call._ems_modality_for(self.student), self.call.modality_ids)

    def test_back_to_draft_only_without_submitted_applications(self):
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.student)
        self.call.action_back_to_draft()
        self.call.action_publish()
        upload(application, self.cv)
        application.action_submit()
        with self.assertRaises(UserError):
            self.call.action_back_to_draft()

    def test_closing_marks_drafts_as_not_submitted(self):
        Application = self.env['ems.erasmus.application']
        draft = Application._ems_portal_get_or_create(self.call, self.minor)
        submitted = Application._ems_portal_get_or_create(self.call, self.student)
        upload(submitted, self.cv)
        submitted.action_submit()
        self.call.action_close()
        self.assertEqual(self.call.state, 'closed')
        self.assertEqual(draft.state, 'not_submitted')
        self.assertEqual(submitted.state, 'submitted')


@tagged('post_install', '-at_install')
class TestErasmusApplication(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)

    def _apply(self, partner=None):
        return self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, partner or self.student)

    def _line(self, application, call_document):
        return application.document_ids.filtered(lambda line: line.call_document_id == call_document)

    def _mails(self, application):
        return self.env['mail.mail'].search([
            ('model', '=', 'ems.erasmus.application'), ('res_id', '=', application.id)])

    def test_application_gets_the_modality_and_one_line_per_document(self):
        application = self._apply()
        self.assertEqual(application.modality_id, self.call.modality_ids)
        self.assertEqual(application.state, 'draft')
        self.assertEqual(application.document_ids.call_document_id, self.call.document_ids)
        self.assertEqual(self._apply(), application, "One application per student and call")

    def test_a_new_students_call_brings_its_documents(self):
        """The 2026-11-03 review: the CV (PDF, with the Europass link), the video (a Drive link),
        the certificates and the evidence of fewer opportunities (only if declared). No family
        authorisation (2026-11-05): a minor's family gets a copy of the receipt instead."""
        call = self.env['ems.erasmus.call'].create({'name': 'Test defaults call', 'date_open': self.call.date_open,
                                                   'date_close': self.call.date_close})
        self.assertEqual([(document.upload_kind, document.requirement) for document in call.document_ids.sorted('sequence')],
                         [('pdf', 'required'), ('link', 'required'), ('file', 'optional'),
                          ('file', 'fewer_opportunities')])
        self.assertTrue(call.document_ids[:1].help_url.startswith('https://europass.europa.eu'))
        self.assertTrue(call.document_ids.filtered(lambda document: document.requirement == 'fewer_opportunities').confidential)

    def test_a_call_created_from_the_form_brings_its_defaults(self):
        """The form sends the one2many fields empty on a new call: the defaults still apply (found in
        the 2026-11-04 usage test, a call created from the app had no documents, steps, questions
        nor commitment letter)."""
        for audience in ('student', 'staff'):
            with Form(self.env['ems.erasmus.call']) as form:
                form.name = f'Form defaults call {audience}'
                form.audience = audience
                form.date_open = self.call.date_open
                form.date_close = self.call.date_close
            call = form.record
            self.assertTrue(call.document_ids, audience)
            self.assertTrue(call.preparation_document_ids, audience)
            self.assertTrue(call.task_ids, audience)
            if audience == 'student':
                self.assertTrue(call.self_assessment_question_ids)
                self.assertTrue(call.commitment_text)

    def test_documents_by_kind_and_fewer_opportunities(self):
        """A PDF-only document refuses other files, a link document takes a link (not a file), and
        the evidence of fewer opportunities is required only once the student declares them."""
        self.cv.upload_kind = 'pdf'
        video = self.env['ems.erasmus.call.document'].create({
            'call_id': self.call.id, 'name': 'Video', 'requirement': 'required', 'upload_kind': 'link', 'sequence': 5})
        self.evidence.requirement = 'fewer_opportunities'
        application = self._apply()
        with self.assertRaises(UserError):
            application._ems_portal_save({}, {self.cv.id: [('cv.docx', b'PK...')]})
        with self.assertRaises(UserError, msg="Named .pdf but not a PDF."):
            application._ems_portal_save({}, {self.cv.id: [('cv.pdf', b'not a pdf')]})
        application._ems_portal_save({}, {self.cv.id: [('cv.pdf', PDF)]})
        with self.assertRaises(UserError):
            application._ems_portal_save({}, {video.id: [('video.mp4', b'...')]})
        with self.assertRaises(UserError):
            application._ems_portal_save({}, {}, {video.id: 'drive.google.com/no-scheme'})
        with self.assertRaises(UserError, msg="The video is still missing."):
            application.action_submit()
        # A refused file in the same form does not lose the link (not assertRaises: its savepoint
        # would undo what the portal keeps).
        try:
            application._ems_portal_save({}, {self.cv.id: [('cv.pdf', b'not a pdf')]},
                                         {video.id: 'https://drive.google.com/file/d/test/view'})
        except UserError as error:
            self.assertIn(self.cv.name, str(error))
        else:
            self.fail("A CV that is not a PDF is refused.")
        link = self._line(application, video).attachment_ids
        self.assertEqual((link.type, link.url), ('url', 'https://drive.google.com/file/d/test/view'))
        evidence = self._line(application, self.evidence)
        self.assertFalse(evidence.is_required)
        self.assertEqual(evidence.file_state, 'not_applicable')
        application._ems_portal_save({'fewer_opportunities': True}, {})
        self.assertTrue(evidence.is_required)
        with self.assertRaises(UserError, msg="Declared: the evidence is required."):
            application.action_submit()
        application._ems_portal_save({}, {self.evidence.id: [('evidence.pdf', PDF)]})
        application.action_submit()
        self.assertEqual(application.state, 'submitted')

    def test_unique_per_call_and_student(self):
        application = self._apply()
        with self.assertRaises(Exception), self.cr.savepoint():
            application.copy()

    def test_cannot_apply_without_an_eligible_level(self):
        with self.assertRaises(UserError):
            self._apply(self.outsider)

    def test_cannot_apply_outside_the_dates(self):
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            self._apply()

    def test_submit_needs_the_required_documents(self):
        application = self._apply()
        with self.assertRaises(UserError):
            application.action_submit()
        upload(application, self.cv)
        application.action_submit()
        self.assertEqual(application.state, 'submitted')
        self.assertTrue(application.submit_date)

    def test_documents_for_minors_only_required_from_minors(self):
        self.assertFalse(self._line(self._apply(), self.authorization).is_required)
        minor_application = self._apply(self.minor)
        self.assertTrue(self._line(minor_application, self.authorization).is_required)
        upload(minor_application, self.cv)
        with self.assertRaises(UserError):
            minor_application.action_submit()
        upload(minor_application, self.authorization)
        minor_application.action_submit()
        self.assertEqual(minor_application.state, 'submitted')

    def test_submitting_emails_a_receipt_with_the_files(self):
        application = self._apply()
        upload(application, self.cv, name='my_cv.pdf')
        application.action_submit()
        mails = self._mails(application)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_to, 'erasmus.student@example.com')
        self.assertIn('my_cv.pdf', mails.body_html)
        application.action_submit()
        self.assertEqual(len(self._mails(application)), 2, "Every submission sends a new receipt")

    def test_answers_editable_until_the_closing_date(self):
        application = self._apply()
        application._ems_portal_save({'applicant_notes': 'Summer'}, {})
        self.assertEqual(application.applicant_notes, 'Summer')
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            application._ems_portal_save({'applicant_notes': 'Easter'}, {})

    def test_a_students_image_consent_is_their_authorisation_of_the_course(self):
        """The issue-#682 review: not asked again in the form, whatever the browser sends."""
        application = self._apply()
        application._ems_portal_save({'applicant_notes': 'Summer', 'image_consent': True}, {})
        self.assertEqual(application.image_consent, self.student.auth_image)

    def test_every_uploaded_version_is_kept(self):
        application = self._apply()
        upload(application, self.cv, name='v1.pdf')
        line = self._line(application, self.cv)
        line.action_mark_valid()
        upload(application, self.cv, name='v2.pdf')
        self.assertEqual(sorted(line.attachment_ids.mapped('name')), ['v1.pdf', 'v2.pdf'])
        self.assertEqual(line.review_state, 'pending', "A new file needs a new review")

    def test_only_the_newest_file_counts_and_a_draft_removes_a_file_by_mistake(self):
        """The 2026-11-04 usage test: a CV uploaded twice showed "cv.pdf, cv.pdf". The newest file
        of a document handed in as one counts (the receipt lists it alone); a document with several
        files keeps them all; a link shows its address; and a draft removes a file uploaded by
        mistake, a submitted application no longer."""
        self.certificate.single_file = False
        video = self.env['ems.erasmus.call.document'].create({
            'call_id': self.call.id, 'name': 'Video', 'requirement': 'optional', 'upload_kind': 'link', 'sequence': 5})
        application = self._apply()
        upload(application, self.cv, name='cv_old.pdf')
        upload(application, self.cv, name='cv_new.pdf')
        upload(application, self.certificate, name='english.pdf')
        upload(application, self.certificate, name='french.pdf')
        application._ems_portal_save({}, {}, {video.id: 'https://drive.google.com/file/d/test/view'})
        cv, certificate, link = (self._line(application, document) for document in (self.cv, self.certificate, video))
        self.assertEqual(cv.current_attachment_ids.mapped('name'), ['cv_new.pdf'])
        self.assertEqual(len(cv.attachment_ids), 2, "The earlier version is kept")
        self.assertEqual(sorted(certificate.current_attachment_ids.mapped('name')), ['english.pdf', 'french.pdf'])
        self.assertEqual(link.link_url, 'https://drive.google.com/file/d/test/view')
        old = cv.attachment_ids.filtered(lambda attachment: attachment.name == 'cv_old.pdf')
        application._ems_portal_remove_file(old.id)
        self.assertFalse(old.exists())
        with self.assertRaises(UserError, msg="Not a file of this application."):
            application._ems_portal_remove_file(self.env['ir.attachment'].create({'name': 'x', 'raw': PDF}).id)
        upload(application, self.cv, name='cv_newest.pdf')
        application.action_submit()
        body = self._mails(application).body_html
        self.assertIn('cv_newest.pdf', body)
        self.assertNotIn('cv_new.pdf', body)
        self.assertIn('french.pdf', body)
        self.assertIn('https://drive.google.com/file/d/test/view', body)
        with self.assertRaises(UserError, msg="Submitted: only the team removes a file."):
            application._ems_portal_remove_file(cv.attachment_ids[:1].id)

    def test_a_document_without_any_file_is_never_valid(self):
        """The 2026-11-04 usage test: it let the team admit an application without the document."""
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        with self.assertRaises(UserError):
            self._line(application, self.certificate).action_mark_valid()
        with self.assertRaises(UserError, msg="Nor from the list's own field."):
            self._line(application, self.certificate).review_state = 'valid'
        self.assertEqual(self._line(application, self.authorization).file_state, 'not_applicable')

    def test_corrections_need_a_deadline_still_to_come(self):
        """The 2026-11-04 usage test: without one the email gave no date and the corrections never
        closed."""
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        self._line(application, self.cv).action_mark_needs_change()
        for deadline in (False, fields.Datetime.now() - timedelta(hours=1)):
            self.call.subsanation_deadline = deadline
            with self.assertRaises(UserError):
                application.action_request_subsanation()
        self.call.subsanation_deadline = fields.Datetime.now() + timedelta(days=5)
        application.action_request_subsanation()
        self.assertIn(self.call._ems_local_deadline(), self._mails(application).sorted('id')[-1:].body_html)

    def test_a_draft_has_no_documents_for_the_team_to_review(self):
        application = self._apply()
        upload(application, self.cv)
        self.assertEqual(application.documents_to_review, 0)
        application.action_submit()
        self.assertEqual(application.documents_to_review, 1)

    def test_the_family_of_a_minor_follows_the_application_and_downloads_the_model(self):
        """The 2026-11-04 usage test: the family saw nothing of Erasmus+ until the commitment
        letter."""
        family = self.env['res.partner'].create({'name': 'Erasmus Test Family', 'contact_type': 'family'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': self.minor.id})
        self.assertFalse(family._ems_erasmus_portal_visible())
        application = self._apply(self.minor)
        self.assertEqual(family._ems_erasmus_guardian_applications(), application)
        self.assertTrue(family._ems_erasmus_portal_visible())
        self.assertFalse(self.student._ems_erasmus_guardian_applications(), "Only a family")

    def test_names_after_de_are_elided_in_catalan(self):
        Base = self.env['ems.base'].with_context(lang='ca_ES')
        self.assertEqual(Base.ems_elide("revisar l'esmena de Alumna Prova"), "revisar l'esmena d'Alumna Prova")
        self.assertEqual(Base.ems_elide("la proposta de Hug"), "la proposta d'Hug")
        self.assertEqual(Base.ems_elide("la proposta de Iolanda"), "la proposta de Iolanda")
        self.assertEqual(Base.ems_elide("la proposta de Pere"), "la proposta de Pere")
        self.assertEqual(self.env['ems.base'].with_context(lang='es_ES').ems_elide("la propuesta de Ana"),
                         "la propuesta de Ana")

    def test_state_only_changes_through_the_actions(self):
        application = self._apply()
        with self.assertRaises(AccessError):
            application.with_user(self.erasmus_user).state = 'admitted'

    def test_subsanation_round_trip(self):
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        with self.assertRaises(UserError):
            application.action_request_subsanation()
        line = self._line(application, self.cv)
        line.write({'review_comment': 'The photo is missing'})
        line.action_mark_needs_change()
        self.call.subsanation_deadline = fields.Datetime.now() + timedelta(days=10)
        application.action_request_subsanation()
        self.assertEqual(application.state, 'subsanation')
        self.assertIn('The photo is missing', self._mails(application)[0].body_html)
        # After the closing date the applicant can still upload what was asked for...
        self.call.action_close()
        with self.assertRaises(UserError):
            application._ems_portal_save({'applicant_notes': 'Changed'}, {})
        upload(application, self.cv, name='fixed.pdf')
        application.action_submit()
        self.assertEqual(application.state, 'submitted')
        self.assertEqual(line.review_state, 'pending')

    def test_subsanation_upload_closed_after_its_deadline(self):
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        self._line(application, self.cv).action_mark_needs_change()
        self.call.subsanation_deadline = fields.Datetime.now() + timedelta(days=10)
        application.action_request_subsanation()
        self.call.subsanation_deadline = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            upload(application, self.cv)

    def test_admit_needs_checks_and_valid_documents(self):
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        with self.assertRaises(UserError):
            application.action_admit()
        application.requirements_check = 'met'
        with self.assertRaises(UserError):
            application.action_admit()
        self._line(application, self.cv).action_mark_valid()
        application.action_admit()
        self.assertEqual(application.state, 'admitted')
        application.action_back_to_review()
        self.assertEqual(application.state, 'submitted')

    def test_exclude_needs_a_reason(self):
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        with self.assertRaises(UserError):
            application.action_exclude()
        application.exclusion_reason = 'Not enrolled in the cycle'
        application.action_exclude()
        self.assertEqual(application.state, 'excluded')

    def test_checks_record_author_and_date(self):
        application = self._apply()
        application.with_user(self.erasmus_user).requirements_check = 'met'
        self.assertEqual(application.requirements_check_user_id, self.erasmus_user)
        self.assertTrue(application.requirements_check_date)

    def test_head_of_studies_only_reads(self):
        application = self._apply()
        self.assertEqual(application.with_user(self.hos_user).partner_id, self.student)
        with self.assertRaises(AccessError):
            application.with_user(self.hos_user).requirements_check = 'met'

    def _strikes(self, count, partner=None):
        teacher = self.env['hr.employee'].search([], limit=1)
        return self.env['ems.strike'].create([{
            'student_id': (partner or self.student).id, 'teacher_id': teacher.id,
            'date': fields.Datetime.now() - timedelta(minutes=index + 1),
        } for index in range(count)])

    def _conduct(self, application):
        application.invalidate_recordset(['conduct_review', 'course_strike_count'])
        return application.course_strike_count, application.conduct_review

    def test_a_serious_conduct_record_only_warns_the_team(self):
        """Art. 6 (adriamt, 2026-11-03): as many warnings this course as the coexistence
        escalation threshold, or more, rule nobody out: the student applies and can be admitted, and
        the team sees the warning to exclude the application if the teaching team or the
        coexistence team say so."""
        self.env.company.strike_escalation_threshold = 3
        self._strikes(3, self.minor)
        self.assertIn(self.minor, self.call._ems_eligible_partners())
        application = self._apply()
        self._strikes(2)
        self.assertEqual(self._conduct(application), (2, False))
        self._strikes(1)
        self.assertEqual(self._conduct(application), (3, True))
        upload(application, self.cv)
        application.action_submit()
        application.requirements_check = 'met'
        self._line(application, self.cv).action_mark_valid()
        application.action_admit()
        self.assertEqual(application.state, 'admitted')

    def test_the_team_may_exclude_for_conduct(self):
        self.env.company.strike_escalation_threshold = 3
        self._strikes(3)
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        application.exclusion_reason = 'Art. 6: serious conduct incidents, heard the teaching team'
        application.action_exclude()
        self.assertEqual(application.state, 'excluded')

    def test_conduct_warnings_of_earlier_courses_do_not_count(self):
        self.env.company.strike_escalation_threshold = 3
        old = self._strikes(3)
        old.write({'date': fields.Datetime.now() - timedelta(days=800)})
        self.assertEqual(self._conduct(self._apply()), (0, False))

    def test_no_threshold_no_warning(self):
        self.env.company.strike_escalation_threshold = 0
        self._strikes(5)
        self.assertEqual(self._conduct(self._apply()), (5, False))

    def test_receipt_replies_go_to_the_erasmus_mailbox(self):
        self.env.company.erasmus_contact_email = 'erasmus.box@example.com'
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        mail = self.env['mail.mail'].search([('model', '=', application._name), ('res_id', '=', application.id)])
        self.assertIn('erasmus.box@example.com', mail.reply_to)

    def test_corrected_application_becomes_a_task_for_the_team(self):
        application = self._apply()
        upload(application, self.cv)
        application.action_submit()
        self._line(application, self.cv).action_mark_needs_change()
        self.call.subsanation_deadline = fields.Datetime.now() + timedelta(days=10)
        application.action_request_subsanation()
        self.assertFalse(application.activity_ids)
        upload(application, self.cv)
        application.action_submit()
        self.assertIn(self.erasmus_user, application.activity_ids.user_id)
        application.requirements_check = 'met'
        self._line(application, self.cv).action_mark_valid()
        application.action_admit()
        self.assertFalse(application.activity_ids, "Reviewing it marks the task done.")

    def test_head_of_studies_does_not_see_confidential_documents(self):
        application = self._apply()
        upload(application, self.evidence)
        self.env.invalidate_all()
        lines = application.with_user(self.hos_user).document_ids
        self.assertNotIn(self.evidence, lines.call_document_id)
        self.env.invalidate_all()
        self.assertIn(self.evidence, application.with_user(self.erasmus_user).document_ids.call_document_id)

    def test_teacher_sees_nothing(self):
        application = self._apply()
        with self.assertRaises(AccessError):
            application.with_user(self.teacher_user).read(['state'])
