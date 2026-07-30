import base64
import importlib.util
import os

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestStudentDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Student Document Test', 'contact_type': 'student',
        })
        cls.other_student = cls.env['res.partner'].create({
            'name': 'Other Student Document Test', 'contact_type': 'student',
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


class TestStudentDocumentPortalAccess(TransactionCase):
    """Regression: portal ACL used to grant unrestricted write (see CLAUDE.md DTON
    notes) — portal users must never write/create ems.student.document directly via
    the ORM; every real mutation for the portal flow goes through sudo'd controller
    code in controllers/portal_enrollment.py instead."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Portal Access Student Document Test', 'contact_type': 'student',
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
