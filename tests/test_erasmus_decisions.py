from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .test_erasmus import PDF
from .test_erasmus_integration import ErasmusGroupRecordsCase
from .test_erasmus_mobility import tick_signatures
from .test_erasmus_records import ErasmusRecordsCase
from .test_erasmus_scoring import ErasmusScoringCase


@tagged('post_install', '-at_install')
class TestErasmusDecisionsAccess(ErasmusRecordsCase):
    """D-14 and D-4: the Head of Studies reads the total and the rank, the conduct warnings and the
    exclusion reason, but not the criteria nor what the applicant declares about fewer opportunities."""

    def test_head_of_studies_reads_the_total_only(self):
        first, _second = self._on_project()
        application = first.application_id.with_user(self.hos_user)
        self.env.invalidate_all()
        self.assertTrue(application.read(['score_total', 'rank', 'course_strike_count', 'exclusion_reason']))
        for name in ('score_a', 'score_b', 'score_c', 'score_e', 'score_f', 'fewer_opportunities'):
            with self.assertRaises(AccessError, msg=name):
                application.read([name])
        line = self.env['ems.erasmus.resolution.line'].search(
            [('application_id', '=', first.application_id.id), ('score_total', '!=', 0)], limit=1)
        self.assertTrue(line.with_user(self.hos_user).read(['score_total']))
        with self.assertRaises(AccessError):
            line.with_user(self.hos_user).read(['score_a'])
        self.assertTrue(first.application_id.with_user(self.technician_user).read(['score_a', 'fewer_opportunities']))

    def test_groups_menu_hidden_from_the_erasmus_technician(self):
        """D-6: the technician only reads the groups to pick a group mobility's eligible groups."""
        menu = self.env.ref('ems.menu_groups')
        visible = self.env['ir.ui.menu'].with_user(self.technician_user)._visible_menu_ids()
        self.assertNotIn(menu.id, visible)
        self.assertIn(menu.id, self.env['ir.ui.menu'].with_user(self.teacher_user)._visible_menu_ids())


@tagged('post_install', '-at_install')
class TestErasmusDecisionsRecords(ErasmusRecordsCase):
    """D-1, D-2, D-5, D-8, D-10, D-12, D-17 and D-18 on the individual mobilities."""

    # --- D-2 ---

    def test_a_project_document_with_files_is_kept(self):
        Document = self.env['ems.erasmus.project.document'].with_user(self.technician_user)
        empty = Document.create({'project_id': self.project.id, 'name': 'Empty'})
        kept = Document.create({'project_id': self.project.id, 'name': 'Grant agreement',
                                'attachment_ids': [(0, 0, {'name': 'agreement.pdf', 'raw': PDF})]})
        with self.assertRaises(UserError):
            kept.unlink()
        empty.unlink()

    def test_a_file_is_removed_with_a_reason_kept_in_the_history(self):
        first, _second = self._on_project()
        line = self._line(first, 'OLS certificate')
        line._ems_add_files([('wrong.pdf', PDF)])
        attachment = line.attachment_ids
        with self.assertRaises(UserError):
            line.with_user(self.technician_user).write({'attachment_ids': [(3, attachment.id)]})
        action = line.with_user(self.technician_user).action_remove_file()
        wizard = self.env[action['res_model']].with_user(self.technician_user).with_context(
            action['context']).create({'attachment_id': attachment.id, 'reason': 'Uploaded to the wrong document'})
        wizard.action_confirm()
        self.assertFalse(line.attachment_ids)
        message = first.message_ids.filtered(lambda message: attachment in message.attachment_ids)
        self.assertIn('Uploaded to the wrong document', message.body)
        self.assertIn(self.technician_user.name, message.body)
        self.assertTrue(attachment.exists())
        line._ems_add_files([('right.pdf', PDF)])
        line.action_mark_valid()
        wizard = self.env['ems.erasmus.file.removal.wizard'].with_user(self.technician_user).create(
            {'line_id': line.id, 'attachment_id': line.attachment_ids.id, 'reason': 'Too late'})
        with self.assertRaises(UserError):
            wizard.action_confirm()

    # --- D-1 ---

    def test_a_signed_document_is_valid_once_every_signature_is_ticked(self):
        first, _second = self._on_project()
        agreement = self._line(first, 'Grant agreement')
        required = agreement.signature_ids.filtered('is_required')
        self.assertEqual(set(required.mapped('signer')), {'participant', 'director'}, "The guardian only for a minor.")
        agreement.prepared_attachment_ids = self.env['ir.attachment'].create({'name': 'to_sign.pdf', 'raw': PDF})
        first._ems_portal_upload({agreement.call_document_id.id: [('signed.pdf', PDF)]})
        with self.assertRaises(UserError):
            agreement.with_user(self.technician_user).action_mark_valid()
        participant = agreement.signature_ids.filtered(lambda signature: signature.signer == 'participant')
        participant.with_user(self.technician_user).write({'signed': True})
        self.assertEqual((participant.signed_user_id, bool(participant.signed_date)), (self.technician_user, True))
        self.assertIn('Director', agreement.signatures_missing)
        with self.assertRaises(AccessError):
            participant.with_user(self.hos_user).write({'signed': False})
        tick_signatures(agreement)
        agreement.with_user(self.technician_user).action_mark_valid()
        self.assertEqual(agreement.file_state, 'complete')
        with self.assertRaises(UserError):
            participant.with_user(self.technician_user).write({'signed': False})
        with self.assertRaises(UserError):
            agreement.signature_ids.unlink()
        self.assertIn('ticked', ' '.join(first.message_ids.mapped('body')))

    def test_new_signers_of_a_call_document_reach_its_lines(self):
        first, _second = self._on_project()
        agreement = self._line(first, 'Grant agreement')
        agreement.call_document_id.sign_host = True
        self.assertIn('host', agreement.signature_ids.mapped('signer'))
        agreement.call_document_id.sign_host = False
        self.assertNotIn('host', agreement.signature_ids.mapped('signer'))

    # --- D-18 ---

    def test_undoing_a_transfer_needs_a_reason(self):
        first, _second = self._on_project()
        first.write({'grant_amount': 1000})
        first.action_request_prefinancing()
        payment = first.payment_ids
        self._transfer(payment, self.secretary_user)
        action = payment.with_user(self.secretary_user).action_mark_unpaid()
        self.assertEqual(payment.state, 'paid', "Undoing opens the wizard, it does not undo by itself.")
        Wizard = self.env[action['res_model']].with_user(self.secretary_user).with_context(action['context'])
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            Wizard.create({}).action_confirm()
        Wizard.create({'reason': 'Paid to the wrong account'}).action_confirm()
        self.assertEqual(payment.state, 'to_pay')
        self.assertIn('Paid to the wrong account', payment.message_ids[:1].body)
        with self.assertRaises(AccessError):
            payment.with_user(self.technician_user).action_mark_unpaid()

    # --- D-10 ---

    def test_every_participants_spreadsheet_download_is_logged(self):
        first, second = self._on_project()
        applications = (first | second).application_id
        applications.with_user(self.erasmus_user)._ems_participants_xlsx()
        log = self.env['ems.erasmus.export'].search([('scope', '=', 'participants'), ('call_id', '=', self.call.id)])
        self.assertEqual((log.requester_id, log.participant_count, log.state), (self.erasmus_user, 2, 'done'))
        self.assertIn(self.erasmus_user.name, self.call.message_ids[:1].body)

    # --- D-8 and D-5 ---

    def _back_home(self, mobility):
        today = self.env['ems.datetime_utils'].get_local_today()
        mobility.sudo().write({'date_start': today - timedelta(days=40), 'date_end': today - timedelta(days=10)})

    def test_the_participant_answers_the_eu_survey_and_the_team_validates_it(self):
        first, _second = self._on_project()
        today = self.env['ems.datetime_utils'].get_local_today()
        first.sudo().write({'date_start': today + timedelta(days=5), 'date_end': today + timedelta(days=35)})
        self.assertEqual(first.eu_survey_deadline, today + timedelta(days=65))
        with self.assertRaises(UserError):
            first._ems_portal_eu_survey()
        self._back_home(first)
        self.assertNotIn('Final report (EU Survey)', first.task_ids.mapped('name'), "Not a checklist step any more.")
        with self.assertRaises(UserError):
            first.with_user(self.technician_user).action_eu_survey_validate()
        first._ems_portal_eu_survey()
        self.assertEqual(first.eu_survey_state, 'done')
        self.assertIn(self.technician_user, first.activity_ids.user_id)
        with self.assertRaises(AccessError):
            first.with_user(self.hos_user).action_eu_survey_validate()
        first.with_user(self.technician_user).action_eu_survey_validate()
        self.assertEqual(first.eu_survey_state, 'validated')
        with self.assertRaises(AccessError):
            first.with_user(self.technician_user).write({'eu_survey_state': 'pending'})

    def test_closing_needs_the_whole_record_the_project_the_survey_and_nothing_to_pay(self):
        first, second = self._accepted_on_project()
        team = first.with_user(self.technician_user)
        for stage in ('preparation', 'return'):
            self._complete_stage(first, stage)
        self._back_home(first)
        first.write({'grant_amount': 1000})
        first.action_request_prefinancing()
        self._transfer(first.payment_ids, self.secretary_user)
        with self.assertRaisesRegex(UserError, 'EU Survey'):
            team.action_close()
        first._ems_portal_eu_survey()
        team.action_eu_survey_validate()
        with self.assertRaisesRegex(UserError, 'pay'):
            team.action_close()
        first.action_request_final_payment()
        with self.assertRaisesRegex(UserError, 'pay'):
            team.action_close()
        self._transfer(first.payment_ids.filtered(lambda payment: payment.state == 'to_pay'), self.secretary_user)
        invoice = self._invoice(first | second, 100, project_id=self.project.id)
        with self.assertRaisesRegex(UserError, 'pay'):
            team.action_close()
        self._transfer(invoice, self.secretary_user)
        first.project_id = False
        with self.assertRaisesRegex(UserError, 'project'):
            team.action_close()
        first.project_id = self.project
        team.action_close()
        self.assertEqual(first.state, 'done')

    def _accepted_on_project(self):
        first, second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self.modality.project = 'ka121_vet'
        (first | second).project_id = self.project
        return first, second

    # --- D-12 ---

    def test_the_coordination_is_told_once_when_the_keeping_period_is_over(self):
        today = self.env['ems.datetime_utils'].get_local_today()
        self.project.write({'budget': 50000, 'final_payment_date': today - timedelta(days=3 * 366)})
        held = self.env['ems.erasmus.project'].create({
            'name': 'TEST-HELD', 'kind': 'ka121_vet', 'budget': 50000, 'retention_hold': True,
            'retention_note': 'SEPIE audit', 'final_payment_date': today - timedelta(days=3 * 366)})
        Project = self.env['ems.erasmus.project']
        Project._cron_retention_notice()
        self.assertEqual(self.project.retention_notice_date, today)
        self.assertIn(self.erasmus_user, self.project.activity_ids.user_id)
        self.assertFalse(held.activity_ids)
        count = len(self.project.activity_ids)
        Project._cron_retention_notice()
        self.assertEqual(len(self.project.activity_ids), count, "Once per project.")

    # --- D-17 ---

    def test_cancelled_mobilities_with_evidence_go_in_the_project_zip_apart(self):
        first, second = self._on_project()
        self._line(second, 'OLS certificate')._ems_add_files([('ols.pdf', PDF)])
        tickets = self._line(first, 'Tickets or boarding passes')
        tickets._ems_add_files([('tickets.pdf', PDF)])
        tickets.action_mark_valid()
        for mobility in (first, second):
            mobility.with_user(self.technician_user).write({'cancel_reason': 'Test'})
            mobility.with_user(self.technician_user).action_cancel()
        names, _contents, _export = self._export(self.technician_user, scope='project', project_id=self.project.id)
        root = names[0].split('/')[0]
        kept = [name for name in names if '/99_Cancellades_i_retirades/' in name]
        self.assertTrue(any('tickets.pdf' in name for name in kept), "A validated document: the record goes in.")
        self.assertFalse(any('ols.pdf' in name for name in names), "Only uploaded, not validated: listed only.")
        manifest = _contents[f'{root}/manifest.json'].decode()
        self.assertIn(second.display_name, manifest)
        self.assertNotIn(first.display_name, manifest.split('"excluded"')[1])


@tagged('post_install', '-at_install')
class TestErasmusDecisionsGroup(ErasmusGroupRecordsCase):
    """D-1 and D-17 on group mobilities; D-8 keeps working through the shared EU Survey."""

    def test_signatures_of_a_group_document_and_withdrawn_participants_in_the_zip(self):
        self._approved()
        self._confirm_destination()
        student, other = self.mobility.participant_ids.filtered(lambda participant: participant.role == 'student')[:2]
        signed = student.document_ids.filtered('signers')[:1]
        self.assertTrue(signed.signature_ids)
        self._upload(signed)
        with self.assertRaises(UserError):
            signed.with_user(self.leader_user).action_mark_valid()
        with self.assertRaises(AccessError):
            signed.signature_ids[:1].with_user(self.companion_user).write({'signed': True})
        signed.signature_ids.with_user(self.leader_user).write({'signed': True})
        signed.with_user(self.leader_user).action_mark_valid()
        (student | other).sudo().write({'state': 'withdrawn'})
        names, _contents, _export = self._export(self.coordinator_user, scope='project', project_id=self.project.id)
        kept = [name for name in names if '/99_Cancellades_i_retirades/' in name]
        self.assertTrue(any(student.partner_id.name in name for name in kept))
        self.assertFalse(any(other.partner_id.name in name for name in kept), "Nothing signed: listed only.")


@tagged('post_install', '-at_install')
class TestErasmusDecisionsDraw(ErasmusScoringCase):
    """D-13: the ties of an individual call, drawn by EMS and kept, as in a group mobility."""

    def test_the_coordinator_draws_the_ties_and_the_draw_is_kept(self):
        self._current_grade(self.student, self.subject_a, 6)
        self._current_grade(self.second, self.subject_a, 6)
        first = self._admitted()
        second = self._admitted(self.second)
        self.call.action_close()
        self._complete(first)
        self._complete(second)
        self.assertTrue(self.call.needs_draw)
        with self.assertRaises(AccessError):
            first.with_user(self.erasmus_user).write({'draw_order': 1})
        with self.assertRaises(AccessError):
            self.call.with_user(self.hos_user).action_draw_ties()
        self.call.with_user(self.erasmus_user).action_draw_ties()
        self.assertEqual(sorted((first | second).mapped('draw_order')), [1, 2])
        self.assertEqual(sorted((first | second).mapped('rank')), [1, 2])
        self.assertFalse(self.call.needs_draw)
        draw = self.call.draw_ids
        self.assertEqual((len(draw), draw.user_id, draw.tied_count), (1, self.erasmus_user, 2))
        self.assertEqual(draw.line_ids.application_id, first | second)
        with self.assertRaises(UserError):
            draw.write({'score_total': 0})
        with self.assertRaises(UserError):
            draw.unlink()
        with self.assertRaises(UserError):
            self.call.with_user(self.erasmus_user).action_draw_ties()
