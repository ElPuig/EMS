import io
from datetime import datetime, timedelta

import openpyxl

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus import upload
from .test_erasmus_scoring import ErasmusScoringCase
from ..models.erasmus.resolution import mask_document_id


class ErasmusResolutionCase(ErasmusScoringCase):
    """Scoring fixtures plus identity documents, one place in the modality and the call's claims
    and acceptance deadlines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.student.document_id = '12345678Z'
        cls.second.document_id = 'X1234567L'
        cls.call.modality_ids.places = 1
        # The claims period is over: the definitive resolution can be published (art. 14).
        cls.call.write({'claims_deadline': now - timedelta(hours=1), 'acceptance_deadline': now + timedelta(days=20)})

    def _scored_call(self):
        """Two admitted applications with a complete score, the student's higher, and the call
        closed: the student is first and the second student is on the reserve list."""
        self._current_grade(self.student, self.subject_a, 9)
        self._current_grade(self.second, self.subject_a, 6)
        first, second = self._admitted(), self._admitted(self.second)
        self.call.action_close()
        self._complete(first)
        self._complete(second)
        return first, second

    def _resolution(self, kind, **vals):
        return self.env['ems.erasmus.resolution'].with_user(self.erasmus_user).create({
            'call_id': self.call.id, 'kind': kind, **vals})

    def _publish(self, kind, **vals):
        resolution = self._resolution(kind, **vals)
        resolution.action_prepare()
        resolution.action_publish()
        return resolution

    def _publish_up_to_definitive(self):
        for kind in ('admission', 'provisional', 'definitive'):
            resolution = self._publish(kind)
        return resolution

    def _free_place_tasks(self):
        activity_type = self.env.ref('ems.mail_activity_erasmus_free_place')
        return self.call.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)

    def _mails(self, record):
        return self.env['mail.mail'].search([('model', '=', record._name), ('res_id', 'in', record.ids)])


@tagged('post_install', '-at_install')
class TestErasmusResolution(ErasmusResolutionCase):

    def test_result_email_names_the_applicant_and_the_list(self):
        """The email layout's header shows the line's name: never a technical reference."""
        self._admitted()
        self.call.action_close()
        line = self._publish('admission').line_ids[:1]
        self.assertTrue(line.display_name.startswith(f"{line.partner_id.name} - "))
        bodies = self._mails(line).mapped('body_html')
        self.assertTrue(bodies)
        self.assertFalse([body for body in bodies if 'ems.erasmus.resolution.line,' in body])

    def test_the_published_list_pdf_can_be_kept(self):
        """The PDF of a published list is kept for the project's records (attachment_use): Odoo can
        only do it when each list's page names its record. Tests render HTML, so check that page."""
        self._admitted()
        self.call.action_close()
        resolution = self._publish('admission')
        Report = self.env['ir.actions.report']
        report = Report._get_report('ems.action_report_erasmus_resolution')
        html = Report._render_qweb_html(report.id, resolution.ids)[0]
        _bodies, html_ids, *_rest = report._prepare_html(html, report_model=report.model)
        self.assertEqual(html_ids, resolution.ids)

    def test_published_lists_show_only_four_digits_of_the_identity_document(self):
        self.assertEqual(mask_document_id('12345678Z'), '***4567**')
        self.assertEqual(mask_document_id(' 12.345.678-z '), '***4567**')
        self.assertEqual(mask_document_id('X1234567L'), '****4567*')
        self.assertEqual(mask_document_id('PAA123456'), '***1234**')
        self.assertEqual(mask_document_id(False), '')

    def test_admission_list_needs_every_application_decided(self):
        first = self._admitted()
        pending = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.second)
        upload(pending, self.cv)
        pending.action_submit()
        self.call.action_close()
        resolution = self._resolution('admission')
        with self.assertRaises(UserError):
            resolution.action_prepare()
        pending.exclusion_reason = 'Documents missing'
        pending.action_exclude()
        resolution.action_prepare()
        lines = {line.application_id: line for line in resolution.line_ids}
        self.assertEqual(lines[first].result, 'admitted')
        self.assertEqual(lines[first].public_id, '***4567**')
        self.assertEqual(lines[pending].result, 'excluded')
        self.assertEqual(lines[pending].exclusion_reason, 'Documents missing')

    def test_missing_identity_document_blocks_preparing(self):
        self._admitted()
        self.call.action_close()
        self.student.document_id = False
        with self.assertRaises(UserError):
            self._resolution('admission').action_prepare()
        self.student.passport_id = 'PAA123456'
        self._resolution('admission').action_prepare()

    def test_resolutions_follow_their_order_and_are_published_once(self):
        self._scored_call()
        with self.assertRaises(UserError):
            self._resolution('provisional').action_prepare()
        self._publish('admission')
        with self.assertRaises(UserError):
            self._resolution('admission').action_prepare()
        with self.assertRaises(UserError):
            self._resolution('definitive').action_prepare()
        with self.assertRaises(UserError):
            self._resolution('rectification').action_prepare()

    def test_ranked_resolution_needs_every_score_complete(self):
        self._current_grade(self.student, self.subject_a, 9)
        application = self._admitted()
        self.call.action_close()
        self._publish('admission')
        with self.assertRaises(UserError):
            self._resolution('provisional').action_prepare()
        self._complete(application)
        self._resolution('provisional').action_prepare()

    def test_only_the_coordinator_publishes(self):
        """The mobility technician prepares the resolution; publishing it is the coordinator's approval."""
        self._admitted()
        self.call.action_close()
        technician = create_role_user(self, 'erasmus', 'test_erasmus_technician')
        resolution = self.env['ems.erasmus.resolution'].with_user(technician).create(
            {'call_id': self.call.id, 'kind': 'admission'})
        resolution.action_prepare()
        with self.assertRaises(AccessError):
            resolution.action_publish()
        resolution.with_user(self.erasmus_user).action_publish()
        self.assertEqual(resolution.state, 'published')
        self.assertEqual(resolution.published_by_id, self.erasmus_user)

    def test_published_resolution_is_frozen(self):
        first, _second = self._scored_call()
        self._publish('admission')
        provisional = self._publish('provisional')
        line = provisional.line_ids.filtered(lambda line: line.application_id == first)
        total = line.score_total
        first.language_level = 'c2'
        self.assertNotEqual(first.score_total, total)
        self.assertEqual(line.score_total, total)
        with self.assertRaises(UserError):
            provisional.with_user(self.erasmus_user).notes = 'Changed'
        with self.assertRaises(UserError):
            provisional.with_user(self.erasmus_user).unlink()
        with self.assertRaises(AccessError):
            line.with_user(self.erasmus_user).score_total = 99

    def test_provisional_ranks_emails_and_locks_interviews(self):
        first, second = self._scored_call()
        self._publish('admission')
        provisional = self._publish('provisional')
        results = {line.application_id: line.result for line in provisional.line_ids}
        self.assertEqual(results, {first: 'selected', second: 'reserve'})
        self.assertEqual(first.state, 'admitted', "Only the definitive resolution sets the result.")
        self.assertTrue(all(first.interview_ids.mapped('is_locked')))
        mails = self._mails(provisional.line_ids)
        self.assertEqual(sorted(mails.mapped('email_to')),
                         ['erasmus.second@example.com', 'erasmus.student@example.com'])
        self.assertNotIn('Erasmus Second Student', mails.filtered(
            lambda mail: mail.email_to == 'erasmus.student@example.com').body_html)

    def test_below_the_minimum_is_not_selected(self):
        first, second = self._scored_call()
        self.call.min_score = 99
        self._publish('admission')
        provisional = self._publish('provisional')
        self.assertEqual(set(provisional.line_ids.mapped('result')), {'not_selected'})

    def test_definitive_sets_results_and_offers_the_places(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        self.assertEqual((first.state, second.state), ('selected', 'reserve'))
        self.assertEqual(len(first.offer_ids), 1)
        self.assertEqual(first.offer_ids.deadline, self.call.acceptance_deadline)
        self.assertFalse(second.offer_ids)
        self.assertFalse(self._mails(first.offer_ids), "The result email already asks to accept.")

    def test_definitive_needs_a_future_acceptance_deadline(self):
        self._scored_call()
        self._publish('admission')
        self._publish('provisional')
        self.call.acceptance_deadline = fields.Datetime.now() - timedelta(hours=1)
        resolution = self._resolution('definitive')
        resolution.action_prepare()
        with self.assertRaises(UserError):
            resolution.action_publish()

    def test_accept_and_renounce(self):
        first, _second = self._scored_call()
        self._publish_up_to_definitive()
        offer = first.offer_ids
        offer.action_accept()
        self.assertEqual((offer.state, first.state), ('accepted', 'accepted'))
        with self.assertRaises(UserError):
            offer.action_renounce()

    def test_no_answer_after_the_deadline(self):
        first, _second = self._scored_call()
        self._publish_up_to_definitive()
        offer = first.offer_ids
        offer.sudo().deadline = fields.Datetime.now() - timedelta(minutes=1)
        with self.assertRaises(UserError):
            offer.action_accept()
        self.env['ems.erasmus.offer']._cron_expire_offers()
        self.assertEqual((offer.state, first.state), ('expired', 'renounced'))
        self.assertTrue(self._free_place_tasks(), "The place is free for the reserve.")

    def test_no_free_place_task_without_a_reserve(self):
        first, second = self._scored_call()
        self.call.modality_ids.places = 2
        self._publish_up_to_definitive()
        second.offer_ids.action_accept()
        first.offer_ids.action_renounce()
        self.assertFalse(self._free_place_tasks(), "No reserve left to offer it to.")

    def test_free_place_goes_to_the_next_reserve_only_when_confirmed(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        modality = self.call.modality_ids
        self.assertEqual(modality.free_places, 0)
        first.offer_ids.action_renounce('Personal reasons')
        self.assertEqual(first.state, 'renounced')
        self.assertEqual(first.offer_ids.renounce_reason, 'Personal reasons')
        self.assertEqual((modality.free_places, modality.next_reserve_id), (1, second))
        self.assertFalse(second.offer_ids, "A free place is never offered on its own.")
        tasks = self._free_place_tasks()
        self.assertIn(self.erasmus_user, tasks.user_id, "The Erasmus team gets a task to offer the free place.")
        self.assertEqual(len(tasks), len(tasks.user_id), "One task each.")
        self.assertIn(modality.name, tasks[0].summary)
        wizard = self.env['ems.erasmus.offer.wizard'].with_user(self.erasmus_user).with_context(
            active_id=self.call.id).create({'deadline': fields.Datetime.now() + timedelta(days=3)})
        self.assertEqual(wizard.application_id, second)
        wizard.action_confirm()
        self.assertFalse(self._free_place_tasks(), "Done once the place is offered.")
        self.assertTrue(second.offer_ids.from_reserve)
        self.assertEqual(self._mails(second.offer_ids).email_to, 'erasmus.second@example.com')
        self.assertEqual(modality.free_places, 0)
        second.offer_ids.action_accept()
        self.assertEqual(second.state, 'accepted')
        self.assertFalse(modality.next_reserve_id)

    def test_team_cancels_a_pending_offer(self):
        first, _second = self._scored_call()
        self._publish_up_to_definitive()
        with self.assertRaises(UserError):
            first.offer_ids.with_user(self.hos_user).action_cancel()
        first.offer_ids.with_user(self.erasmus_user).action_cancel()
        self.assertEqual(first.offer_ids.state, 'cancelled')
        self.assertEqual(self.call.modality_ids.free_places, 1)

    def test_rectification_needs_notes_and_keeps_answers(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        first.offer_ids.action_accept()
        # Claims upheld: now the second student goes first.
        second.write({'language_level': 'c2', 'fewer_opportunities_check': 'yes'})
        rectification = self._resolution('rectification')
        rectification.action_prepare()
        with self.assertRaises(UserError):
            rectification.action_publish()
        rectification.with_user(self.erasmus_user).notes = 'Language certificate of a claimant accepted.'
        # The first student keeps the place they accepted, and the second is selected: 2 people, 1 place.
        self.assertIn('2', rectification.places_warning)
        with self.assertRaises(UserError):
            rectification.action_publish()
        self.call.modality_ids.places = 2
        self.assertFalse(rectification.places_warning)
        rectification.action_publish()
        results = {line.application_id: line.result for line in rectification.line_ids}
        self.assertEqual(results, {first: 'reserve', second: 'selected'})
        self.assertEqual(first.state, 'accepted', "An answered offer is never undone by a rectification.")
        self.assertEqual(second.state, 'selected')
        self.assertEqual(second.offer_ids.state, 'pending')

    def test_claims_need_a_response_to_be_resolved(self):
        first, _second = self._scored_call()
        self._publish('admission')
        provisional = self._publish('provisional')
        claim = self.env['ems.erasmus.claim'].with_user(self.erasmus_user).create({
            'application_id': first.id, 'resolution_id': provisional.id, 'description': 'My interview score'})
        with self.assertRaises(UserError):
            claim.action_resolve()
        claim.response = 'Reviewed: the score stands.'
        claim.action_resolve()
        self.assertEqual(claim.state, 'resolved')
        self.assertTrue(claim.resolved_date)
        with self.assertRaises(AccessError):
            claim.with_user(self.hos_user).response = 'Changed'

    def test_definitive_waits_for_the_claims(self):
        """Art. 14: the definitive resolution answers the claims, so it waits for their deadline and
        for every open claim to be answered."""
        first, _second = self._scored_call()
        self._publish('admission')
        provisional = self._publish('provisional')
        self.call.claims_deadline = fields.Datetime.now() + timedelta(days=1)
        with self.assertRaises(UserError):
            self._resolution('definitive').action_prepare()
        self.call.claims_deadline = fields.Datetime.now() - timedelta(minutes=1)
        claim = self.env['ems.erasmus.claim'].with_user(self.erasmus_user).create({
            'application_id': first.id, 'resolution_id': provisional.id, 'description': 'My interview score'})
        with self.assertRaises(UserError):
            self._resolution('definitive').action_prepare()
        claim.response = 'Reviewed: the score stands.'
        claim.action_resolve()
        self._publish('definitive')

    def test_rectification_withdraws_the_offer_of_who_it_no_longer_selects(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        self.assertEqual(first.offer_ids.state, 'pending')
        second.write({'language_level': 'c2', 'fewer_opportunities_check': 'yes'})
        rectification = self._resolution('rectification', notes='Language certificate of a claimant accepted.')
        rectification.action_prepare()
        rectification.action_publish()
        self.assertEqual((first.state, first.offer_ids.state), ('reserve', 'cancelled'))
        with self.assertRaises(UserError):
            first.offer_ids.action_accept()
        self.assertEqual((second.state, second.offer_ids.state), ('selected', 'pending'))
        self.assertEqual(self.call.modality_ids.free_places, 0)

    def test_rectification_email_of_who_already_accepted(self):
        self.student.lang = 'en_US'
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        first.offer_ids.action_accept()
        second.write({'language_level': 'c2', 'fewer_opportunities_check': 'yes'})
        self.call.modality_ids.places = 2  # The first keeps the place they accepted.
        rectification = self._publish('rectification', notes='Language certificate of a claimant accepted.')
        body = self._mails(rectification.line_ids.filtered(lambda line: line.application_id == first)).body_html
        self.assertIn('You keep the place you have already accepted.', body)
        self.assertNotIn('reserve list', body)

    def test_export_the_participants_who_accepted(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        bank = self.env['res.bank'].create({'name': 'Erasmus Test Bank', 'bic': 'TESTESMMXXX'})
        self.student.write({'firstname': 'Erasmus Test', 'lastname': 'Student', 'birth_date': '2000-05-17',
                            'bank_ids': [(0, 0, {'acc_number': 'ES9121000418450200051332', 'bank_id': bank.id})]})
        with self.assertRaises(UserError):
            first._ems_participants_xlsx()
        first.offer_ids.action_accept()
        with self.assertRaises(AccessError):
            (first | second).with_user(self.hos_user)._ems_participants_xlsx()
        content = (first | second).with_user(self.erasmus_user)._ems_participants_xlsx()
        sheet = openpyxl.load_workbook(io.BytesIO(content))['Participantes']
        rows = list(sheet.iter_rows(values_only=True))
        self.assertEqual(rows[0][:3], ('Nombre', 'Apellidos', 'DNI'))
        self.assertEqual(rows[0][-1], 'Teléfono del tutor legal')
        self.assertEqual(len(rows), 2, "Only who accepted a place.")
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual((row['Nombre'], row['Apellidos'], row['DNI']), ('Erasmus Test', 'Student', '12345678Z'))
        self.assertEqual(row['Fecha de nacimiento'], datetime(2000, 5, 17))
        self.assertEqual((row['Ciclo formativo'], row['Curso']), (self.study.acronym, 1))
        self.assertEqual((row['Titular de la cuenta'], row['Banco'], row['BIC'], row['IBAN']),
                         (self.student.name, 'Erasmus Test Bank', 'TESTESMMXXX', 'ES9121000418450200051332'))
        self.assertFalse(row['Tutor legal'], "An adult has no legal guardian columns.")
        self.assertIn('/ems/erasmus/participants?application_ids=', first.with_user(
            self.erasmus_user).action_export_participants()['url'])

    def test_export_lists_every_legal_guardian_of_a_minor(self):
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.minor)
        mother, father = self.env['res.partner'].create([
            {'name': 'Erasmus Test Mother', 'contact_type': 'family', 'email': 'mother@example.com', 'phone': '600'},
            {'name': 'Erasmus Test Father', 'contact_type': 'family', 'phone': '700'},
        ])
        self.env['res.partner.relation'].create([{
            'left_partner_id': family.id, 'type_id': self.env.ref(xmlid).id, 'right_partner_id': self.minor.id,
        } for family, xmlid in ((mother, 'ems.relation_type_mother'), (father, 'ems.relation_type_father'))])
        names, emails, phones = application._ems_participant_row()[-3:]
        self.assertEqual(len(names.split(', ')), 2)
        order = [name.strip() for name in names.split(', ')]
        self.assertEqual(emails.split(', '), ['mother@example.com' if name == mother.name else '' for name in order])
        self.assertEqual(phones.split(', '), ['600' if name == mother.name else '700' for name in order])

    def test_head_of_studies_reads_but_does_not_publish(self):
        self._admitted()
        self.call.action_close()
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.resolution'].with_user(self.hos_user).create({
                'call_id': self.call.id, 'kind': 'admission'})
        resolution = self._publish('admission')
        self.assertEqual(resolution.with_user(self.hos_user).line_ids.result, 'admitted')


@tagged('post_install', '-at_install')
class TestPortalErasmusResolution(HttpCase, ErasmusResolutionCase):
    """Issue #685 - the applicant's results, the published list and the place offer on the portal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student_user, cls.second_user = cls.env['res.users'].with_context(no_reset_password=True).create([{
            'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
            'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        } for partner, login in ((cls.student, 'test_erasmus_res_student'),
                                 (cls.second, 'test_erasmus_res_second'))])

    def _answer(self, answer, **data):
        return self.url_open(f'/my/erasmus/call/{self.call.id}/offer',
                             data={'csrf_token': Request.csrf_token(self), 'answer': answer, **data})

    def test_published_list_has_no_names(self):
        self._scored_call()
        self._publish('admission')
        provisional = self._publish('provisional')
        self.authenticate(self.second_user.login, self.second_user.login)
        page = self.url_open(f'/my/erasmus/call/{self.call.id}')
        self.assertIn('o_ems_erasmus_results', page.text)
        listed = self.url_open(f'/my/erasmus/call/{self.call.id}/resolution/{provisional.id}')
        self.assertIn('***4567**', listed.text)
        self.assertIn('****4567*', listed.text)
        self.assertNotIn('Erasmus Test Student', listed.text)
        pdf = self.url_open(f'/my/erasmus/call/{self.call.id}/resolution/{provisional.id}/pdf')
        self.assertEqual(pdf.headers['Content-Type'], 'application/pdf')

    def test_draft_resolution_is_not_shown(self):
        self._scored_call()
        draft = self._resolution('admission')
        draft.action_prepare()
        self.authenticate(self.student_user.login, self.student_user.login)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/resolution/{draft.id}')
        self.assertTrue(response.url.endswith('/my/erasmus'))

    def test_selected_accepts_from_the_portal_and_only_their_own_offer(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        self.authenticate(self.second_user.login, self.second_user.login)
        self.assertIn('error=1', self._answer('accept').url, "The reserve has no offer to accept.")
        self.assertEqual(first.offer_ids.state, 'pending')
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertIn('o_ems_erasmus_offer', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self.assertIn('answered=1', self._answer('accept').url)
        self.assertEqual(first.state, 'accepted')

    def test_selected_renounces_from_the_portal(self):
        first, _second = self._scored_call()
        self._publish_up_to_definitive()
        self.authenticate(self.student_user.login, self.student_user.login)
        self._answer('renounce', reason='I found a job')
        self.assertEqual((first.state, first.offer_ids.renounce_reason), ('renounced', 'I found a job'))
