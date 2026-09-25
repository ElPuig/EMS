import base64
import importlib.util
import io
import os
import zipfile

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import TransactionCase
from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user, next_student_id,
)


class TestStudentDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Student Document Test', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        cls.other_student = cls.env['res.partner'].create({
            'name': 'Other Student Document Test', 'contact_type': 'student', 'student_id': next_student_id(),
        })

    def _create(self, **vals):
        base_vals = {'partner_id': self.student.id, 'doc_type': 'other'}
        base_vals.update(vals)
        return self.env['ems.student.document'].create(base_vals)

    # --- create() side effects ---------------------------------------------

    def test_create_pending_document_schedules_note_and_activity(self):
        reviewer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Doc Reviewer', 'login': 'test_doc_reviewer',
        })
        self.env.ref('ems.mail_activity_student_document_review').ems_assignee_ids = [(6, 0, reviewer.ids)]

        document = self._create(status='pending')

        note = document.message_ids.filtered(lambda m: 'submitted for review' in (m.body or ''))
        self.assertTrue(note)
        self.assertIn(self.student, document.message_partner_ids)
        activity = document.activity_ids.filtered(lambda a: a.user_id == reviewer)
        self.assertTrue(activity)
        # The reviewer gets a task, not a follower subscription (avoids a duplicate email).
        self.assertNotIn(reviewer.partner_id, document.message_partner_ids)

    def test_create_non_pending_document_skips_note_and_activity(self):
        document = self._create(status='approved', doc_type='dni')
        submitted_note = document.message_ids.filtered(lambda m: 'submitted for review' in (m.body or ''))
        self.assertFalse(submitted_note)
        self.assertFalse(document.activity_ids)

    # --- _compute_name -------------------------------------------------------

    def test_compute_name_includes_doc_label_and_student(self):
        document = self._create(doc_type='dni')
        self.assertIn('DNI / NIE', document.name)
        self.assertIn(self.student.name, document.name)

    def test_compute_name_benefit_includes_benefit_label(self):
        document = self._create(doc_type='benefit', benefit_type='disability')
        self.assertIn('Disability (>33%)', document.name)

    # --- _compute_doc_file_link -----------------------------------------------

    def test_doc_file_link_empty_without_file(self):
        document = self._create()
        self.assertEqual(document.doc_file_link, '')

    def test_doc_file_link_with_file(self):
        document = self._create(
            doc_file=base64.b64encode(b'scan-bytes'), doc_file_name='scan.pdf')
        self.assertIn('scan.pdf', document.doc_file_link)
        self.assertIn('/web/content/', document.doc_file_link)

    # --- _check_single_pending_iban -------------------------------------------

    def test_single_pending_iban_raises_on_duplicate(self):
        self._create(doc_type='iban', doc_value='ES9121000418450200051332', status='pending')
        with self.assertRaises(ValidationError):
            self._create(doc_type='iban', doc_value='ES6421000418450200051333', status='pending')

    def test_single_pending_iban_allows_second_when_first_approved(self):
        first = self._create(doc_type='iban', doc_value='ES9121000418450200051332', status='pending')
        first.action_approve()
        second = self._create(doc_type='iban', doc_value='ES6421000418450200051333', status='pending')
        self.assertTrue(second.id)

    def test_single_pending_iban_allows_different_students(self):
        self._create(doc_type='iban', doc_value='ES9121000418450200051332', status='pending')
        other = self.env['ems.student.document'].create({
            'partner_id': self.other_student.id, 'doc_type': 'iban',
            'doc_value': 'ES6421000418450200051333', 'status': 'pending',
        })
        self.assertTrue(other.id)

    # --- action_approve / _apply_bank_account ---------------------------------

    def test_action_approve_iban_creates_bank_account(self):
        document = self._create(doc_type='iban', doc_value='es9121000418450200051332', doc_value2='John Doe')
        document.action_approve()
        self.assertEqual(document.status, 'approved')
        self.assertEqual(document.review_uid, self.env.user)
        bank = self.env['res.partner.bank'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(len(bank), 1)
        # base_iban reformats acc_number with spaces for display purposes.
        self.assertEqual(bank.acc_number.replace(' ', ''), 'ES9121000418450200051332')
        self.assertEqual(bank.acc_holder_name, 'John Doe')
        self.assertTrue(bank.allow_out_payment)

    def test_action_approve_iban_updates_existing_bank_account(self):
        existing = self.env['res.partner.bank'].create({
            'acc_number': 'ES9121000418450200051332', 'partner_id': self.student.id,
            'allow_out_payment': False,
        })
        document = self._create(
            doc_type='iban', doc_value='es9121000418450200051332', doc_value2='Updated Holder')
        document.action_approve()
        self.assertTrue(existing.active)
        self.assertEqual(existing.acc_holder_name, 'Updated Holder')
        self.assertTrue(existing.allow_out_payment)

    def test_action_approve_iban_deactivates_other_accounts(self):
        old = self.env['res.partner.bank'].create({
            'acc_number': 'ES8200000000000000000000', 'partner_id': self.student.id,
        })
        document = self._create(doc_type='iban', doc_value='ES9121000418450200051332')
        document.action_approve()
        self.assertFalse(old.active)

    def test_action_approve_removes_previous_approved_of_same_type(self):
        old = self._create(doc_type='dni', status='approved')
        new = self._create(doc_type='dni')
        new.action_approve()
        self.assertFalse(old.exists())
        self.assertEqual(new.status, 'approved')

    # --- migration: backfill IBAN trust (18.0.0.22.0) ---------------------------

    @classmethod
    def _load_post_migrate_module(cls):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migrations', '18.0.0.22.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('ems_post_migrate_18_0_0_22_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_backfills_trust_for_approved_iban_document(self):
        # Simulates a document approved through the pre-fix portal renewal route:
        # status='approved' but the bank was never actually trusted.
        bank = self.env['res.partner.bank'].create({
            'acc_number': 'ES9121000418450200051332', 'partner_id': self.student.id,
        })
        document = self._create(
            doc_type='iban', doc_value='ES9121000418450200051332',
            doc_value2='Migration Holder', status='approved')
        self.assertFalse(bank.allow_out_payment)

        migration = self._load_post_migrate_module()
        migration._backfill_iban_trust(self.env)
        bank.invalidate_recordset()

        self.assertTrue(bank.allow_out_payment)

    def test_migration_ignores_non_iban_and_pending_documents(self):
        pending_iban = self._create(doc_type='iban', doc_value='ES1000000000000000000001')
        other_type = self._create(doc_type='dni', status='approved')

        migration = self._load_post_migrate_module()
        # Must not raise for documents with no bank to touch.
        migration._backfill_iban_trust(self.env)

        self.assertEqual(pending_iban.status, 'pending')
        self.assertEqual(other_type.status, 'approved')

    # --- action_approve / _apply_benefit ---------------------------------------

    def test_action_approve_benefit_creates_student_benefit(self):
        document = self._create(
            doc_type='benefit', benefit_type='disability',
            doc_file=base64.b64encode(b'proof'), doc_file_name='proof.pdf')
        document.action_approve()
        benefit = self.env['ems.student.benefit'].search([('student_id', '=', self.student.id)])
        self.assertEqual(len(benefit), 1)
        self.assertEqual(benefit.benefit_type, 'disability')
        self.assertEqual(benefit.category, 'exemption')

    def test_action_approve_benefit_different_types_coexist(self):
        # _apply_benefit only clears a PREVIOUS ems.student.benefit of the SAME
        # benefit_type — a student can hold several different benefits at once
        # (ems.student.benefit has no student-wide uniqueness, only per-type).
        first = self._create(doc_type='benefit', benefit_type='disability')
        first.action_approve()
        first_benefit = self.env['ems.student.benefit'].search([('student_id', '=', self.student.id)])

        second = self._create(doc_type='benefit', benefit_type='scholarship')
        second.action_approve()

        self.assertTrue(first_benefit.exists())
        benefits = self.env['ems.student.benefit'].search([('student_id', '=', self.student.id)])
        self.assertEqual(set(benefits.mapped('benefit_type')), {'disability', 'scholarship'})

    def test_action_approve_benefit_same_type_replaces_previous(self):
        first = self._create(doc_type='benefit', benefit_type='disability')
        first.action_approve()
        second = self._create(doc_type='benefit', benefit_type='disability')
        second.action_approve()
        benefits = self.env['ems.student.benefit'].search([('student_id', '=', self.student.id)])
        self.assertEqual(len(benefits), 1)

    def test_action_approve_clears_activities(self):
        reviewer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Doc Reviewer 2', 'login': 'test_doc_reviewer2',
        })
        self.env.ref('ems.mail_activity_student_document_review').ems_assignee_ids = [(6, 0, reviewer.ids)]
        document = self._create(status='pending')
        self.assertTrue(document.activity_ids)
        document.action_approve()
        self.assertFalse(document.activity_ids)

    # --- action_reject / action_cancel / action_reset_to_pending --------------

    def test_action_reject_sets_status_and_logs_reason(self):
        document = self._create(doc_type='dni')
        document.rejection_reason = 'Blurry scan'
        document.action_reject()
        self.assertEqual(document.status, 'rejected')
        self.assertEqual(document.review_uid, self.env.user)
        last_message = document.message_ids.sorted('id')[-1]
        self.assertIn('Blurry scan', last_message.body)

    def test_action_cancel_sets_status(self):
        document = self._create(doc_type='dni')
        document.action_cancel()
        self.assertEqual(document.status, 'cancelled')

    def test_action_reset_to_pending_clears_review_fields_and_reschedules(self):
        document = self._create(doc_type='dni')
        document.action_reject()
        document.rejection_reason = 'Illegible'
        document.action_reset_to_pending()
        self.assertEqual(document.status, 'pending')
        self.assertFalse(document.review_uid)
        self.assertFalse(document.review_date)
        self.assertFalse(document.rejection_reason)

    # --- _doc_label ------------------------------------------------------------

    def test_doc_label_known_type(self):
        document = self._create(doc_type='medical')
        self.assertEqual(document._doc_label(), 'Medical card (TIS)')

    # --- Labels follow the reader's language ------------------------------------

    def _translate_selection(self, xmlid, label):
        # Set on purpose rather than relying on i18n/ca_ES.po, so a test database loaded without
        # the Catalan translations still proves the label goes through the translation layer.
        self.env['res.lang']._activate_lang('ca_ES')
        self.env.ref(xmlid).with_context(lang='ca_ES').name = label

    def test_doc_label_follows_language(self):
        self._translate_selection('ems.selection__ems_student_document__doc_type__medical', 'Targeta TIS')
        document = self._create(doc_type='medical')
        self.assertEqual(document.with_context(lang='ca_ES')._doc_label(), 'Targeta TIS')
        self.assertEqual(document.with_context(lang='en_US')._doc_label(), 'Medical card (TIS)')

    def test_name_follows_reader_language(self):
        """Not stored: the same record reads in each reader's own language."""
        self._translate_selection('ems.selection__ems_student_document__doc_type__benefit', 'Bonificació')
        self._translate_selection('ems.selection__ems_student_benefit__benefit_type__disability', 'Discapacitat')
        document = self._create(doc_type='benefit', benefit_type='disability')
        catalan = document.with_context(lang='ca_ES').name
        self.assertIn('Bonificació', catalan)
        self.assertIn('Discapacitat', catalan)
        self.assertIn('Disability (>33%)', document.with_context(lang='en_US').name)

    def test_benefit_type_shows_translated_label(self):
        """benefit_type offers the same (translated) choices as ems.student.benefit, so lists
        and forms show the label instead of the internal key."""
        self._translate_selection('ems.selection__ems_student_benefit__benefit_type__large_family_gen',
                                  'Família nombrosa (prova)')
        field = self.env['ems.student.document']._fields['benefit_type']
        catalan = dict(field._description_selection(self.env(context={'lang': 'ca_ES'})))
        self.assertEqual(catalan['large_family_gen'], 'Família nombrosa (prova)')

    def test_name_search_finds_document_by_student(self):
        document = self._create(doc_type='dni')
        found = self.env['ems.student.document'].name_search(self.student.name)
        self.assertIn(document.id, [record_id for record_id, _name in found])

    def test_messages_and_task_use_translated_label(self):
        self._translate_selection('ems.selection__ems_student_document__doc_type__passport', 'Passaport')
        reviewer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Doc Reviewer', 'login': 'test_doc_reviewer_lang',
        })
        self.env.ref('ems.mail_activity_student_document_review').ems_assignee_ids = [(6, 0, reviewer.ids)]
        Document = self.env['ems.student.document'].with_context(lang='ca_ES')
        document = Document.create({'partner_id': self.student.id, 'doc_type': 'passport'})
        self.assertIn('Passaport', document.activity_ids.summary)
        document.action_approve()
        self.assertIn('Passaport', document.message_ids.sorted('id')[-1].body)


class TestStudentDocumentPortalAccess(TransactionCase):
    """Regression: portal ACL used to grant unrestricted write (see CLAUDE.md DTON
    notes) — portal users must never write/create ems.student.document directly via
    the ORM; every real mutation for the portal flow goes through sudo'd controller
    code in controllers/portal_enrollment.py instead."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Portal Access Student Document Test', 'contact_type': 'student', 'student_id': next_student_id(),
            'email': 'portal.doc.test@example.com',
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal User (Student Document)', 'login': 'portal.doc.test@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.student.user_ids = [(4, cls.portal_user.id)]
        cls.document = cls.env['ems.student.document'].create({
            'partner_id': cls.student.id, 'doc_type': 'other',
        })

    def test_portal_user_can_read_own_document(self):
        self.assertTrue(self.document.with_user(self.portal_user).exists())

    def test_portal_user_cannot_write_document(self):
        with self.assertRaises(AccessError):
            self.document.with_user(self.portal_user).write({'doc_type': 'dni'})

    def test_portal_user_cannot_create_document_directly(self):
        with self.assertRaises(AccessError):
            self.env['ems.student.document'].with_user(self.portal_user).create({
                'partner_id': self.student.id, 'doc_type': 'other',
            })


def create_tutored_students_with_credentials(cls, prefix):
    """A tutor user with one tutored student and one student of another group, each with a
    Google credentials PDF, plus a DNI on the tutored one. Sets cls.tutor_user, cls.tutor, cls.student,
    cls.other_student, cls.credentials, cls.dni and cls.other_credentials."""
    cls.tutor_user = create_role_user(cls, 'tutor', f'test_tutor_{prefix.lower()}')
    cls.tutor = create_role_employee(cls, cls.tutor_user)
    __, __, group = create_level_study_group(cls, f'{prefix}T', group={'tutor_id': cls.tutor.id})
    __, __, other_group = create_level_study_group(cls, f'{prefix}O')
    Partner = cls.env['res.partner']
    cls.student = Partner.create({
        'name': f'{prefix} Tutored Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'main_group_id': group.id,
    })
    cls.other_student = Partner.create({
        'name': f'{prefix} Other Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'main_group_id': other_group.id,
    })
    Document = cls.env['ems.student.document']
    cls.credentials = Document.create({
        'partner_id': cls.student.id, 'doc_type': 'google_credentials', 'status': 'approved',
        'doc_file': base64.b64encode(b'credentials-pdf'), 'doc_file_name': 'credentials.pdf',
    })
    cls.dni = Document.create({'partner_id': cls.student.id, 'doc_type': 'dni', 'status': 'approved'})
    cls.other_credentials = Document.create({
        'partner_id': cls.other_student.id, 'doc_type': 'google_credentials', 'status': 'approved',
        'doc_file': base64.b64encode(b'other-credentials-pdf'), 'doc_file_name': 'other.pdf',
    })


class TestStudentDocumentTutorAccess(TransactionCase):
    """Issue #478: tutors read their own students' Google credentials PDF - and nothing else
    from the Documentation tab (DNI, IBAN, medical card... stay with secretary/admin)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_tutored_students_with_credentials(cls, 'TSD')

    def _documents_seen_by(self, user):
        return self.env['ems.student.document'].with_user(user).search(
            [('id', 'in', (self.credentials | self.dni | self.other_credentials).ids)])

    def test_tutor_reads_only_own_students_credentials(self):
        self.assertEqual(self._documents_seen_by(self.tutor_user), self.credentials)

    def test_tutor_sees_only_credentials_in_documentation_tab(self):
        self.assertEqual(self.student.with_user(self.tutor_user).document_ids, self.credentials)

    def test_tutor_downloads_credentials_file(self):
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'ems.student.document'), ('res_field', '=', 'doc_file'),
            ('res_id', '=', self.credentials.id),
        ])
        self.assertEqual(attachment.with_user(self.tutor_user).datas, base64.b64encode(b'credentials-pdf'))

    def test_tutor_cannot_modify_credentials(self):
        credentials = self.credentials.with_user(self.tutor_user)
        with self.assertRaises(AccessError):
            credentials.write({'status': 'pending'})
        with self.assertRaises(AccessError):
            credentials.unlink()
        with self.assertRaises(AccessError):
            self.env['ems.student.document'].with_user(self.tutor_user).create({
                'partner_id': self.student.id, 'doc_type': 'google_credentials',
            })

    def test_secretary_who_tutors_still_sees_every_document(self):
        # The tutor rule must not narrow staff who also tutor a group (academic admin implies
        # group_tutor through the Head of Studies chain, and a secretary may teach too).
        self.tutor_user.groups_id = [(4, self.env.ref('ems.group_secretary').id)]
        self.assertEqual(len(self._documents_seen_by(self.tutor_user)), 3)

    def test_academic_admin_sees_every_document(self):
        admin = create_role_user(self, 'academic_admin', 'test_admin_student_document')
        self.assertEqual(len(self._documents_seen_by(admin)), 3)

    def test_documentation_section_only_for_who_can_read_some_document(self):
        # The student form's Documentation section hides itself instead of showing an empty list
        # to someone the rules let read nothing of this student (issue #511 follow-up).
        teacher = create_role_user(self, 'teacher', 'test_teacher_student_document')
        secretary = create_role_user(self, 'secretary', 'test_secretary_student_document')
        tac = create_role_user(self, 'tac', 'test_tac_section_student_document')
        for user, student, expected in (
                (self.tutor_user, self.student, True), (self.tutor_user, self.other_student, False),
                (teacher, self.student, False), (secretary, self.other_student, True),
                (tac, self.other_student, True)):
            self.assertEqual(student.with_user(user).can_see_documents, expected, (user.login, student.name))


class TestStudentDocumentTacAccess(TransactionCase):
    """Issue #478: the TAC team reads every student's Google credentials (they reset them), and
    nothing else from the Documentation tab."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_tutored_students_with_credentials(cls, 'TAC')
        cls.tac = create_role_user(cls, 'tac', 'test_tac_student_document')

    def test_tac_reads_every_students_credentials_only(self):
        documents = self.env['ems.student.document'].with_user(self.tac).search(
            [('id', 'in', (self.credentials | self.dni | self.other_credentials).ids)])
        self.assertEqual(documents, self.credentials | self.other_credentials)

    def test_tac_cannot_modify_credentials(self):
        with self.assertRaises(AccessError):
            self.credentials.with_user(self.tac).write({'status': 'pending'})

    def test_tac_downloads_every_students_credentials(self):
        students = (self.student | self.other_student).with_user(self.tac)
        self.assertEqual(students._get_google_credentials_documents(), self.credentials | self.other_credentials)


class TestStudentDocumentHeadOfStudiesAccess(TransactionCase):
    """Issue #483: Head of Studies and Director read the Google credentials of the students whose
    tutor sits below them, through the tutor rule itself - still read only, and still nothing
    else from the Documentation tab."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_tutored_students_with_credentials(cls, 'HSD')
        create_head_of_studies_branch(cls, 'HSD', cls.tutor)

    def _documents_seen_by(self, user):
        return self.env['ems.student.document'].with_user(user).search(
            [('id', 'in', (self.credentials | self.dni | self.other_credentials).ids)])

    def test_head_of_studies_reads_their_branch_credentials_only(self):
        self.assertEqual(self._documents_seen_by(self.head_of_studies), self.credentials)

    def test_other_head_of_studies_reads_no_credentials(self):
        self.assertFalse(self._documents_seen_by(self.other_head_of_studies))

    def test_department_chief_reads_their_department_credentials_only(self):
        self.assertEqual(self._documents_seen_by(self.department_chief), self.credentials)
        self.assertFalse(self._documents_seen_by(self.other_department_chief))

    def test_director_reads_every_tutored_students_credentials(self):
        director = create_role_user(self, 'director', 'test_director_student_document', name='HSD Director')
        self.env.company.director_id = create_role_employee(self, director)
        self.assertEqual(self._documents_seen_by(director), self.credentials)

    def test_head_of_studies_cannot_modify_credentials(self):
        with self.assertRaises(AccessError):
            self.credentials.with_user(self.head_of_studies).write({'status': 'pending'})

    def test_head_of_studies_downloads_their_branch_credentials(self):
        students = (self.student | self.other_student).with_user(self.head_of_studies)
        self.assertEqual(students._get_google_credentials_documents(), self.credentials)


class TestGoogleCredentialsBulkDownload(TransactionCase):
    """Issue #478: "Download Google credentials" on the students list."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_tutored_students_with_credentials(cls, 'GCD')

    def test_action_downloads_only_readable_credentials(self):
        students = (self.student | self.other_student).with_user(self.tutor_user)
        action = students.action_download_google_credentials()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['url'], f'/ems/google_credentials/download?partner_ids={self.student.id}')

    def test_action_without_readable_credentials_raises(self):
        with self.assertRaises(UserError):
            self.other_student.with_user(self.tutor_user).action_download_google_credentials()

    def test_only_latest_credentials_per_student(self):
        newer = self.env['ems.student.document'].create({
            'partner_id': self.student.id, 'doc_type': 'google_credentials', 'status': 'approved',
            'doc_file': base64.b64encode(b'newer-pdf'), 'doc_file_name': 'newer.pdf',
        })
        self.assertEqual(self.student._get_google_credentials_documents(), newer)

    def test_secretary_gets_every_student(self):
        secretary = create_role_user(self, 'secretary', 'test_secretary_gcd')
        documents = (self.student | self.other_student).with_user(secretary)._get_google_credentials_documents()
        self.assertEqual(documents, self.credentials | self.other_credentials)


@tagged('post_install', '-at_install')
class TestGoogleCredentialsDownloadRoute(HttpCase):
    """The download route re-checks access itself: a tutor editing the URL by hand still only
    gets their own students' PDFs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_tutored_students_with_credentials(cls, 'GCR')

    def test_route_zips_only_readable_credentials(self):
        self.authenticate(self.tutor_user.login, self.tutor_user.login)
        response = self.url_open(
            f'/ems/google_credentials/download?partner_ids={self.student.id},{self.other_student.id}')
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 1)
            self.assertIn(self.student.name, names[0])
            self.assertEqual(archive.read(names[0]), b'credentials-pdf')

    def test_route_without_readable_credentials_is_not_found(self):
        self.authenticate(self.tutor_user.login, self.tutor_user.login)
        response = self.url_open(f'/ems/google_credentials/download?partner_ids={self.other_student.id}')
        self.assertEqual(response.status_code, 404)
