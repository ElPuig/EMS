from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
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
    cls.erasmus_user = create_role_user(cls, 'erasmus', 'test_erasmus_team')
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

    def test_publish_needs_a_modality_and_a_required_document(self):
        draft = self.env['ems.erasmus.call'].create({
            'name': 'Empty call', 'date_open': self.call.date_open, 'date_close': self.call.date_close,
        })
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
        application._ems_portal_save({'availability': 'Summer'}, {})
        self.assertEqual(application.availability, 'Summer')
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            application._ems_portal_save({'availability': 'Easter'}, {})

    def test_every_uploaded_version_is_kept(self):
        application = self._apply()
        upload(application, self.cv, name='v1.pdf')
        line = self._line(application, self.cv)
        line.action_mark_valid()
        upload(application, self.cv, name='v2.pdf')
        self.assertEqual(sorted(line.attachment_ids.mapped('name')), ['v1.pdf', 'v2.pdf'])
        self.assertEqual(line.review_state, 'pending', "A new file needs a new review")

    def test_state_only_changes_through_the_actions(self):
        application = self._apply()
        with self.assertRaises(UserError):
            application.state = 'admitted'

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
            application._ems_portal_save({'availability': 'Changed'}, {})
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
        application.with_user(self.hos_user).sanction_check = 'met'
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
        application.with_user(self.hos_user).sanction_check = 'not_met'
        self.assertEqual(application.sanction_check_user_id, self.hos_user)

    def test_sanction_check_reserved_to_head_of_studies(self):
        application = self._apply()
        with self.assertRaises(AccessError):
            application.with_user(self.erasmus_user).sanction_check = 'met'
        with self.assertRaises(AccessError):
            application.with_user(self.hos_user).requirements_check = 'met'
        application.with_user(self.hos_user).write({'sanction_check': 'met', 'sanction_check_note': 'Checked'})
        self.assertEqual(application.sanction_check, 'met')

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
