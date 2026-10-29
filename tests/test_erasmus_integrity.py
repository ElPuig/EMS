import json

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, tagged
from odoo.tools import format_date, mute_logger

from .test_erasmus import PDF
from .test_erasmus_integration import ErasmusGroupRecordsCase
from .test_erasmus_records import ErasmusRecordsCase

# What a client can put in the context of an RPC call: the flags the workflow used to trust.
FORGED_CONTEXT = {'ems_erasmus_state': True, 'ems_erasmus_payment_state': True, 'ems_erasmus_publish': True}


@tagged('post_install', '-at_install')
class TestErasmusWorkflowWrites(ErasmusRecordsCase):
    """Audit 2026-10-25 (R-25): a state, a decision, a signature or a frozen value only changes
    through the actions, never written directly (what an RPC call or a developer tool does), not
    even with a context the client chose."""

    def _refused(self, record, vals, context=None):
        with self.assertRaises(AccessError, msg=f"{record._name}: {vals}"):
            record.with_user(self.technician_user).with_context(**(context or {})).write(vals)

    def test_workflow_fields_only_change_through_the_actions(self):
        first, second = self._on_project()
        application = first.application_id
        draft = self.env['ems.erasmus.resolution'].create({'call_id': self.call.id, 'kind': 'rectification'})
        claim = self.env['ems.erasmus.claim'].create({'application_id': application.id, 'description': 'Test'})
        self._refused(draft, {'state': 'published'})
        self._refused(draft, {'published_by_id': self.technician_user.id})
        self._refused(first, {'state': 'done'})
        self._refused(second, {'proposal_state': 'validated'})
        self._refused(first, {'commitment_signed_date': '2026-01-01 10:00:00',
                              'commitment_signed_by_id': self.technician_user.id})
        self._refused(self.call, {'state': 'draft'})
        self._refused(application, {'grade_average_ems': 9.99})
        self._refused(application, {'strike_count': 0})
        self._refused(application, {'requirements_check_user_id': self.erasmus_user.id})
        self._refused(claim, {'state': 'resolved'})
        first.with_user(self.technician_user).write({'grant_amount': 900, 'city': 'Lyon'})

    def test_a_client_context_never_opens_the_workflow(self):
        first, _second = self._on_project()
        first.with_user(self.technician_user).write({'grant_amount': 1000})
        first.with_user(self.technician_user).action_request_prefinancing()
        published = self.call.resolution_ids.filtered(lambda resolution: resolution.state == 'published')[:1]
        self._refused(first.application_id, {'state': 'selected'}, FORGED_CONTEXT)
        self._refused(first, {'state': 'done'}, FORGED_CONTEXT)
        self._refused(first.payment_ids, {'state': 'paid'}, FORGED_CONTEXT)
        with self.assertRaises(UserError):
            published.with_user(self.erasmus_user).with_context(**FORGED_CONTEXT).write({'notes': 'Changed'})

    def test_a_record_starts_in_its_initial_state(self):
        Resolution = self.env['ems.erasmus.resolution'].with_user(self.technician_user)
        with self.assertRaises(AccessError):
            Resolution.create({'call_id': self.call.id, 'kind': 'rectification', 'state': 'published'})
        resolution = Resolution.create({'call_id': self.call.id, 'kind': 'rectification', 'state': 'draft'})
        self.assertEqual(resolution.state, 'draft', "The initial value, sent by the form, is accepted.")


@tagged('post_install', '-at_install')
class TestErasmusWorkflowRpc(HttpCase, ErasmusRecordsCase):
    """The same through the real JSON-RPC route the web client uses, with the context in the call."""

    def test_call_kw_with_a_forged_context_is_refused(self):
        first, _second = self._on_project()
        self.authenticate(self.technician_user.login, self.technician_user.login)
        with mute_logger('odoo.http'), self.assertRaises(Exception):
            self.make_jsonrpc_request('/web/dataset/call_kw/ems.erasmus.mobility/write', {
                'model': 'ems.erasmus.mobility', 'method': 'write', 'args': [first.ids, {'state': 'done'}],
                'kwargs': {'context': FORGED_CONTEXT}})
        first.invalidate_recordset()
        self.assertEqual(first.state, 'preparing')


@tagged('post_install', '-at_install')
class TestErasmusGroupWorkflowWrites(ErasmusGroupRecordsCase):
    """R-25 in the group mobilities, and the leader's own limits with a forged context."""

    def test_leader_and_team_cannot_skip_the_group_workflow(self):
        registrations = self._ranked()
        for user in (self.leader_user, self.technician_user):
            with self.assertRaises(AccessError):
                self.mobility.with_user(user).with_context(**FORGED_CONTEXT).write({'state': 'done'})
        with self.assertRaises(AccessError):
            registrations[-1].with_user(self.leader_user).with_context(**FORGED_CONTEXT).write(
                {'result_override': 'selected', 'override_reason': 'Forged'})
        self.mobility.with_user(self.leader_user).action_submit_proposal()
        self.mobility.with_user(self.coordinator_user).action_approve_selection()
        with self.assertRaises(AccessError):
            self._student().with_user(self.technician_user).write({'commitment_signed_date': '2026-01-01 10:00:00'})


@tagged('post_install', '-at_install')
class TestErasmusEvidenceKept(ErasmusRecordsCase):
    """R-01: a record that holds evidence (a file, a valid document, a signature, a payment) is never
    deleted, not even through what it holds (its file, or a cascade from its parent)."""

    def test_a_valid_document_and_its_files_are_kept(self):
        first, _second = self._on_project()
        health = self._line(first, 'European Health Insurance Card')
        health._ems_add_files([('health.pdf', PDF)])
        health.action_mark_valid()
        team = self.technician_user
        attachment = health.attachment_ids.with_user(team)
        with self.assertRaises(UserError):
            health.with_user(team).unlink()
        with self.assertRaises(UserError):
            attachment.unlink()
        with self.assertRaises(UserError):
            attachment.write({'raw': b'%PDF-1.4 replaced'})
        with self.assertRaises(UserError):
            attachment.write({'res_id': self._line(first, 'OLS certificate').id})
        self.assertEqual(health.attachment_ids.raw, PDF)
        attachment.write({'description': 'Checked'})

    def test_a_record_with_files_is_not_deleted_with_them(self):
        first, second = self._on_project()
        self._line(first, 'OLS certificate')._ems_add_files([('ols.pdf', PDF)])
        team = self.technician_user
        with self.assertRaises(UserError):
            first.with_user(team).unlink()
        with self.assertRaises(UserError):
            first.application_id.document_ids.filtered('attachment_ids')[:1].with_user(team).unlink()
        self.assertTrue(first.exists())

    def test_a_proposal_refuses_the_files_every_upload_refuses(self):
        """R-11: the host's commitment of an own proposal goes through check_upload too."""
        _first, second = self._on_project()
        second._ems_set_state('choosing', proposal_state=False)
        with self.assertRaises(UserError):
            second._ems_portal_propose({'proposal_host': 'Test host', 'proposal_country_id': self.env.ref('base.de').id},
                                       [('page.html', b'<html><script>alert(1)</script></html>')])

    def test_the_receipt_of_a_paid_payment_is_kept(self):
        first, _second = self._on_project()
        first.write({'grant_amount': 1000})
        first.action_request_prefinancing()
        self._transfer(first.payment_ids, self.secretary_user)
        with self.assertRaises(UserError):
            first.payment_ids.receipt_ids.with_user(self.technician_user).unlink()


@tagged('post_install', '-at_install')
class TestErasmusGroupEvidenceKept(ErasmusGroupRecordsCase):
    """R-01 in a group mobility: a participant who signed and a mobility with a selection (its draws,
    enrolments and files) are never deleted; a cascade would skip the draws' own guard."""

    def test_a_signed_participant_and_a_selected_mobility_are_kept(self):
        self._approved()
        self._confirm_destination()
        student = self._student()
        student.action_sign_commitment(True, '10.0.0.1')
        with self.assertRaises(UserError):
            student.with_user(self.coordinator_user).unlink()
        with self.assertRaises(UserError):
            self.mobility.with_user(self.coordinator_user).unlink()
        self.assertTrue(self.mobility.registration_ids)


@tagged('post_install', '-at_install')
class TestErasmusExportCoverage(ErasmusRecordsCase):
    """R-02: an archived record is still in the project's ZIP (marked as such) and counted; what a
    project export leaves out on purpose is listed in its manifest and index, never silently."""

    def test_archived_mobility_stays_in_the_project_export(self):
        first, second = self._on_project()
        second.with_user(self.technician_user).write({'active': False})
        self.assertEqual(self.project.record_count, 2)
        names, contents, _export = self._export(self.technician_user, scope='project', project_id=self.project.id)
        root = names[0].split('/')[0]
        folder = self.env['ems.erasmus.export']._ems_record_folder(second)
        self.assertTrue(any(f'/{folder}/' in name for name in names))
        notes = [row['Notes'] for row in self._index(contents, root) if row['Participant'] == second.partner_id.name]
        self.assertTrue(notes and all(note.startswith("Archived") for note in notes), notes)

    def test_what_a_project_export_leaves_out_is_listed(self):
        first, second = self._on_project()
        second.with_user(self.technician_user).write({'cancel_reason': 'Test'})
        second.with_user(self.technician_user).action_cancel()
        names, contents, _export = self._export(self.technician_user, scope='project', project_id=self.project.id)
        root = names[0].split('/')[0]
        manifest = json.loads(contents[f'{root}/manifest.json'])
        self.assertEqual([(item['record'], item['reason']) for item in manifest['excluded']],
                         [(second.display_name, "Cancelled")])
        self.assertIn("Not exported: Cancelled", {row['Notes'] for row in self._index(contents, root)})


@tagged('post_install', '-at_install')
class TestErasmusGroupExportCoverage(ErasmusGroupRecordsCase):

    def test_a_withdrawn_participant_is_listed_as_left_out(self):
        self._approved()
        teacher = self.mobility.participant_ids.filtered(lambda participant: participant.role != 'student')[:1]
        teacher.sudo().write({'state': 'withdrawn'})
        names, contents, _export = self._export(self.coordinator_user, scope='group', group_mobility_id=self.mobility.id)
        root = names[0].split('/')[0]
        manifest = json.loads(contents[f'{root}/manifest.json'])
        self.assertIn((teacher.display_name, "Withdrawn"),
                      [(item['record'], item['reason']) for item in manifest['excluded']])


@tagged('post_install', '-at_install')
class TestErasmusPaymentTrace(ErasmusRecordsCase):
    """R-24, R-13 and a concurrency gap: an undone transfer leaves who, when and its receipts in the
    payment's history; a payment is never requested for a mobility that is not under way; the first
    and the final payment exist once per mobility, whatever the timing of two requests."""

    def test_undoing_a_transfer_keeps_its_trace(self):
        first, _second = self._on_project()
        first.write({'grant_amount': 1000})
        first.action_request_prefinancing()
        payment = first.payment_ids
        self._transfer(payment, self.secretary_user)
        receipt, paid_date = payment.receipt_ids, payment.paid_date
        self._undo(payment, self.secretary_user)
        self.assertEqual(payment.state, 'to_pay')
        message = payment.message_ids.filtered(lambda message: receipt in message.attachment_ids)[:1]
        self.assertTrue(message, "The receipts stay attached to the payment's history.")
        self.assertIn(self.secretary_user.name, message.body)
        self.assertIn(format_date(self.env, paid_date), message.body)
        self.assertTrue(receipt.exists())

    def test_no_payment_for_a_mobility_not_under_way(self):
        first, second = self._on_project()
        second.with_user(self.technician_user).write({'cancel_reason': 'Test', 'grant_amount': 500})
        second.with_user(self.technician_user).action_cancel()
        with self.assertRaises(UserError):
            second.with_user(self.technician_user).action_request_prefinancing()

    @mute_logger('odoo.sql_db')
    def test_the_first_payment_exists_once_per_mobility(self):
        first, _second = self._on_project()
        first.write({'grant_amount': 1000})
        first.action_request_prefinancing()
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['ems.erasmus.payment'].create({'mobility_id': first.id, 'kind': 'prefinancing',
                                                        'amount': 1})
                self.env.flush_all()

    def test_a_paid_invoice_cannot_change(self):
        first, second = self._on_project()
        invoice = self._invoice(first | second, 300, project_id=self.project.id)
        self._transfer(invoice, self.secretary_user)
        with self.assertRaises(UserError):
            invoice.with_user(self.technician_user).write({'amount': 1})


@tagged('post_install', '-at_install')
class TestErasmusEvaluationsKept(ErasmusRecordsCase):
    """R-10: a submitted interview is part of the selection; only one still to score is deleted."""

    def test_a_submitted_interview_is_never_deleted(self):
        first, _second = self._on_project()
        interviews = first.application_id.sudo().interview_ids
        submitted = interviews.filtered(lambda interview: interview.state == 'submitted')[:1]
        self.assertTrue(submitted)
        with self.assertRaises(UserError):
            submitted.with_user(self.erasmus_user).unlink()
        draft = self.env['ems.erasmus.interview'].create({'application_id': first.application_id.id,
                                                          'evaluator_id': self.teacher_user.id})
        draft.with_user(self.erasmus_user).unlink()


@tagged('post_install', '-at_install')
class TestErasmusCombinedRoles(ErasmusRecordsCase):
    """Roles held together, and roles taken away: a Head of Studies who also teaches in a group
    mobility only reads the individual records; an evaluator whose interview is reassigned stops
    reading it."""

    def test_head_of_studies_who_is_a_group_teacher_only_reads_individual_records(self):
        first, _second = self._on_project()
        self.hos_user.groups_id = [(4, self.env.ref('ems.group_erasmus_group_teacher').id)]
        ols = self._line(first, 'OLS certificate')
        ols._ems_add_files([('ols.pdf', PDF)])
        ols.with_user(self.hos_user).read(['review_state'])
        with self.assertRaises(AccessError):
            ols.with_user(self.hos_user).write({'review_state': 'valid'})

    def test_an_evaluator_whose_interview_is_reassigned_stops_reading_it(self):
        first, _second = self._on_project()
        interview = self.env['ems.erasmus.interview'].create({'application_id': first.application_id.id,
                                                              'evaluator_id': self.teacher_user.id})
        interview.with_user(self.teacher_user).read(['motivation'])
        interview.with_user(self.erasmus_user).write({'evaluator_id': self.hos_user.id})
        self.assertFalse(self.teacher_user.has_group('ems.group_erasmus_evaluator'))
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            interview.with_user(self.teacher_user).read(['motivation'])


@tagged('post_install', '-at_install')
class TestErasmusGroupCombinedRoles(ErasmusGroupRecordsCase):

    def test_a_replaced_leader_stops_reading_the_group(self):
        self.mobility.with_user(self.coordinator_user).write({'leader_id': self.other_teacher.id})
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            self.mobility.with_user(self.leader_user).read(['name'])
        self.mobility.with_user(self.other_teacher_user).read(['name'])

