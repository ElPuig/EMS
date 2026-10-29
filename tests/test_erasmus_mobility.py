from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import create_role_employee, create_role_user
from .test_erasmus import PDF
from .test_erasmus_resolution import ErasmusResolutionCase
from .test_erasmus_staff import ErasmusStaffCase


def tick_signatures(lines):
    """What the team does on a signed copy before marking it valid (audit D-1)."""
    lines.sudo().signature_ids.write({'signed': True})


class ErasmusMobilityCase(ErasmusResolutionCase):
    """Two places in the modality: both students are selected and accept them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call.modality_ids.places = 2
        cls.modality = cls.call.modality_ids

    def _accepted(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        (first | second).offer_ids.action_accept()
        return first.mobility_ids, second.mobility_ids

    def _destinations(self, *places):
        return self.env['ems.erasmus.destination'].create([{
            'call_id': self.call.id, 'modality_id': self.modality.id, 'name': f'Test destination {index}',
            'country_id': self.env.ref('base.de').id, 'city': f'City {index}', 'places': count, 'sequence': index,
            'date_start': date(2027, 6, 1), 'date_end': date(2027, 6, 30),
        } for index, count in enumerate(places, 1)])

    def _complete_stage(self, mobility, stage, guardian=True):
        lines = mobility.document_ids.filtered(lambda line: line.stage == stage and line.is_required)
        provided = lines.filtered(lambda line: line.handled_by == 'team')
        provided.prepared_attachment_ids = self.env['ir.attachment'].create({'name': 'policy.pdf', 'raw': PDF})
        mobility._ems_portal_upload({line.call_document_id.id: [('signed.pdf', PDF)] for line in lines - provided})
        # What someone signs is complete once the team checks it, its own documents (sBID) included.
        tick_signatures(lines)
        (lines - provided | provided.filtered('signers')).action_mark_valid()
        mobility.task_ids.filtered(lambda task: task.stage == stage).write({'done': True})
        if stage == 'preparation' and mobility.commitment_pending:
            mobility.action_sign_commitment(True, '127.0.0.1')
        if stage == 'preparation' and guardian and mobility.commitment_guardian_pending:
            mobility.action_sign_commitment(True, '127.0.0.1', guardian=True)

    def _minor_with_family(self):
        """The first student becomes a minor with a family contact."""
        self.student.birth_date = date(self.env['ems.datetime_utils'].get_local_today().year - 16, 1, 1)
        family = self.env['res.partner'].create({
            'name': 'Erasmus Test Family', 'contact_type': 'family', 'email': 'erasmus.family@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': self.student.id})
        return family


@tagged('post_install', '-at_install')
class TestErasmusMobility(ErasmusMobilityCase):

    def test_accepting_a_place_starts_the_mobility_with_its_documents_and_checklist(self):
        first, _second = self._accepted()
        self.assertEqual(first.state, 'choosing')
        self.assertEqual(first.level_id, self.level)
        stages = set(first.document_ids.mapped('stage'))
        self.assertEqual(stages, {'preparation', 'return'})
        self.assertTrue(first.task_ids)
        self.assertNotIn(first.document_ids, first.application_id.document_ids,
                         "The application keeps only the documents it was submitted with.")
        minors_only = first.document_ids.filtered(lambda line: line.call_document_id.requirement == 'minor')
        self.assertFalse(any(minors_only.mapped("is_required")), "The student is an adult.")
        self.assertIn('host entity', first.document_ids.filtered(
            lambda line: line.call_document_id.sign_host)[:1].signers)

    def test_the_director_signs_the_grant_agreement_and_the_coordinator_the_learning_agreement(self):
        documents = self.call.preparation_document_ids
        grant, learning = (documents.filtered(lambda document, name=name: document.name == name)
                           for name in ("Grant agreement", "Learning agreement"))
        self.assertEqual(grant.signers, "participant, legal guardian, director")
        self.assertEqual(learning.signers, "participant, legal guardian, Erasmus coordinator, host entity")

    def test_project_documents_and_steps_only_reach_that_project(self):
        """The test modality is KA121-VET: it gets the Europass mobility document, never the
        recognition of ECTS credits nor the virtual component, which are KA131-HED's."""
        first, _second = self._accepted()
        names = first.document_ids.call_document_id.mapped('name')
        self.assertIn("Europass mobility document", names)
        self.assertNotIn("Recognition of ECTS credits", names)
        self.assertNotIn("Virtual component", names)

    def _line(self, mobility, name):
        return mobility.document_ids.filtered(lambda line: line.name == name)

    def test_sbid_documents_are_required_only_for_a_curricular_work_placement(self):
        first, _second = self._accepted()
        self.assertEqual(first.placement_type, 'curricular', "A student's stay is curricular by default.")
        sbid = self._line(first, "sBID agreement (REF5)") | self._line(first, "sBID activity plan (REF6)")
        self.assertEqual(len(sbid), 2)
        self.assertTrue(all(sbid.mapped('is_required')))
        for placement in ('extracurricular', 'graduate'):
            first.placement_type = placement
            self.assertFalse(any(sbid.mapped('is_required')), placement)
            self.assertTrue(first.document_ids.filtered(lambda line: line in sbid), "They can still be attached.")

    def test_a_vet_stay_gets_the_europass_document_and_no_ects_nor_virtual_component(self):
        first, _second = self._accepted()
        first.write({'date_start': date(2027, 6, 1), 'date_end': date(2027, 6, 14)})
        self.assertTrue(self._line(first, "Europass mobility document").is_required)
        self.assertTrue(self._line(first, "Certificate of stay").is_required, "Students keep the certificate in VET.")
        self.assertFalse(self._line(first, "Recognition of ECTS credits"))
        self.assertFalse(first.is_short_blended, "Only a KA131-HED stay is blended.")
        self.assertFalse(self._line(first, "Virtual component"))

    def test_hed_ects_recognition_only_for_a_curricular_work_placement(self):
        self.modality.project = 'ka131_hed'
        first, _second = self._accepted()
        ects = self._line(first, "Recognition of ECTS credits")
        self.assertTrue(ects.is_required)
        self.assertFalse(self._line(first, "Europass mobility document"), "KA131-HED has no Europass document.")
        first.placement_type = 'graduate'
        self.assertFalse(ects.is_required)
        first.placement_type = 'extracurricular'
        self.assertFalse(ects.is_required)

    def test_the_virtual_component_is_asked_for_only_in_a_short_hed_stay(self):
        self.modality.project = 'ka131_hed'
        first, _second = self._accepted()
        virtual = self._line(first, "Virtual component")
        self.assertEqual(virtual.handled_by, 'participant', "The student uploads their preparation.")
        self.assertFalse(virtual.is_required, "No dates yet: not known to be short.")
        first.write({'date_start': date(2027, 6, 1), 'date_end': date(2027, 6, 30)})
        self.assertTrue(first.is_short_blended, "30 days: short blended.")
        self.assertTrue(virtual.is_required)
        first.date_end = date(2027, 7, 1)
        self.assertFalse(virtual.is_required, "31 days: a long stay, no virtual component.")

    def test_a_short_blended_step_counts_only_in_a_short_hed_stay(self):
        self.modality.project = 'ka131_hed'
        self.env['ems.erasmus.call.task'].create({
            'call_id': self.call.id, 'name': 'Short blended step', 'requirement': 'short_blended'})
        first, _second = self._accepted()
        first.write({'date_start': date(2027, 6, 1), 'date_end': date(2027, 8, 31)})
        self._complete_stage(first, 'preparation')
        step = first.task_ids.filtered(lambda task: task.name == 'Short blended step')
        step.done = False
        self.assertTrue(first.preparation_complete, "A three-month stay: the step does not count.")
        self.assertTrue(self._line(first, "Virtual component"), "The document is there, just not asked for.")
        first.date_end = date(2027, 6, 30)
        self.assertFalse(first.preparation_complete, "A short stay: the step and the virtual component count.")

    def test_the_virtual_component_opens_a_month_before_leaving(self):
        self.modality.project = 'ka131_hed'
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        virtual = self._line(first, "Virtual component")
        self.assertEqual((virtual.open_date, virtual.deadline), (date(2027, 5, 2), date(2027, 5, 31)),
                         "Opens a month before leaving, due the day before.")
        self.assertTrue(virtual.is_required, "The destination's 30 days: short blended.")
        self.assertFalse(virtual._ems_is_open())
        self.assertNotIn(virtual, first._ems_documents_to_correct(), "Not reminded before it opens.")
        first._ems_portal_upload({virtual.call_document_id.id: [('virtual.pdf', PDF)]})
        self.assertFalse(virtual.attachment_ids, "Not uploaded before it opens.")
        today = self.env['ems.datetime_utils'].get_local_today()
        first.write({'date_start': today + timedelta(days=10), 'date_end': today + timedelta(days=20)})
        self.assertTrue(virtual._ems_is_open())
        self.assertIn(virtual, first._ems_documents_to_correct())
        first._ems_portal_upload({virtual.call_document_id.id: [('virtual.pdf', PDF)]})
        self.assertEqual(virtual.attachment_ids.mapped('name'), ['virtual.pdf'])

    def test_weekly_self_assessment_during_the_stay(self):
        questions = self.call.self_assessment_question_ids
        self.assertEqual(questions.mapped('kind'), ['text', 'text', 'rating', 'text'], "A students' call has them.")
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        today = self.env['ems.datetime_utils'].get_local_today()
        first.write({'date_start': today - timedelta(days=10), 'date_end': today + timedelta(days=10)})
        self.assertEqual([week[0] for week in first._ems_self_assessment_weeks()], [1, 2, 3])
        self.assertEqual([week[0] for week in first._ems_self_assessments_open()], [1, 2], "Weeks already begun.")
        self.assertEqual([week[0] for week in first._ems_self_assessments_missing()], [1], "Weeks already over.")
        answers = {question.id: '4' if question.kind == 'rating' else 'Test answer' for question in questions}
        for week, values in ((3, answers), (1, {**answers, questions[0].id: ' '}),
                             (1, {**answers, questions[2].id: '7'})):
            with self.assertRaises(UserError):
                first._ems_portal_self_assessment(week, values)
        sent = len(self._mails(first))
        self.env['ems.erasmus.mobility']._cron_remind_documents()
        self.assertEqual(len(self._mails(first)), sent + 1)
        self.assertIn((today - timedelta(days=10)).strftime('%d/%m/%Y'), self._mails(first).sorted('id')[-1].body_html,
                      "Reminded of the week over (the mail is in the student's language).")
        first._ems_portal_self_assessment(1, answers)
        assessment = first.self_assessment_ids
        self.assertEqual((assessment.week, assessment.date_from, assessment.rating), (1, today - timedelta(days=10), 4))
        self.assertEqual(first.self_assessment_progress, '1 / 3')
        self.assertFalse(first._ems_self_assessments_missing())
        with self.assertRaises(UserError):
            first._ems_portal_self_assessment(1, answers)
        questions[0].name = 'Changed question'
        self.assertIn("What did you do this week?", assessment.answers_html, "The question as it was asked.")
        # Under tests Odoo renders reports as HTML, not PDF.
        report, _type = self.env['ir.actions.report']._render_qweb_pdf(
            'ems.action_report_erasmus_self_assessment', first.ids)
        self.assertIn(b'Test answer', report)

    def test_documents_only_for_some_modalities(self):
        gs_only = self.env['ems.erasmus.call.document'].create({
            'call_id': self.call.id, 'stage': 'preparation', 'name': 'GS only',
            'modality_ids': [(0, 0, {'call_id': self.call.id, 'name': 'Other modality'})]})
        first, _second = self._accepted()
        self.assertNotIn(gs_only, first.document_ids.call_document_id)

    def test_a_modality_with_one_destination_assigns_it_directly(self):
        first, second = self._accepted()
        destination = self._destinations(2)
        self.call.with_user(self.erasmus_user).action_open_destination_choice()
        self.assertEqual((first.state, second.state), ('preparing', 'preparing'))
        self.assertEqual(first.destination_id, destination)
        self.assertEqual((first.city, first.date_start), ('City 1', date(2027, 6, 1)))
        self.assertEqual(destination.free_places, 0)
        self.assertTrue(self._mails(first))

    def test_assigning_a_destination_with_one_host_entity_sets_it_and_its_tutor(self):
        first, second = self._accepted()
        host = self.env['res.partner'].create({'name': 'Test Host School', 'is_company': True, 'is_erasmus_host': True})
        tutor = self.env['res.partner'].create({'name': 'Test Tutor', 'parent_id': host.id, 'type': 'contact'})
        destination = self._destinations(2)
        destination.host_partner_ids = host
        self.call.action_open_destination_choice()
        self.assertEqual((first.host_partner_id, first.host_contact_id), (host, tutor))

    def test_choice_opens_only_after_the_definitive_resolution_with_destinations(self):
        self._scored_call()
        with self.assertRaises(UserError):
            self.call.action_open_destination_choice()
        self._publish_up_to_definitive()
        with self.assertRaises(UserError):
            self.call.action_open_destination_choice()

    def test_turns_in_rank_order(self):
        first, second = self._accepted()
        cyprus, germany = self._destinations(1, 1)
        self.call.action_open_destination_choice()
        self.assertTrue(first.turn_deadline)
        self.assertFalse(second.turn_deadline, "One turn at a time per modality.")
        self.assertTrue(self._mails(first))
        with self.assertRaises(UserError):
            second.action_choose_destination(germany)
        first.action_choose_destination(cyprus)
        self.assertEqual((first.state, first.destination_id), ('preparing', cyprus))
        self.assertTrue(second.turn_deadline)
        self.assertEqual(second._ems_choices(), germany, "A full destination is not offered.")
        with self.assertRaises(UserError):
            second.action_choose_destination(cyprus)
        second.action_choose_destination(germany)
        self.assertEqual(second.state, 'preparing')

    def test_destinations_suit_the_levels_they_are_for(self):
        first, _second = self._accepted()
        cyprus, germany = self._destinations(1, 1)
        cyprus.level_ids = self.other_level
        self.call.action_open_destination_choice()
        self.assertEqual(first._ems_choices(), germany)
        with self.assertRaises(UserError):
            first.action_choose_destination(cyprus)

    def test_no_answer_in_the_turn_passes_it_and_keeps_the_place(self):
        """Art. 15: who does not answer in their turn chooses among what is left at the end."""
        first, second = self._accepted()
        _cyprus, germany = self._destinations(1, 1)
        self.call.action_open_destination_choice()
        first.with_context(ems_erasmus_state=True).sudo().turn_deadline = fields.Datetime.now() - timedelta(minutes=1)
        self.env['ems.erasmus.mobility']._cron_expire_turns()
        self.assertEqual((first.state, first.turn_missed, first.turn_deadline), ('choosing', True, False))
        self.assertEqual(first.application_id.state, 'accepted')
        self.assertTrue(second.turn_deadline)
        with self.assertRaises(UserError):
            first.action_choose_destination(germany)
        second.action_choose_destination(_cyprus)
        self.assertTrue(first.free_choice)
        self.assertEqual(first._ems_choices(), germany)
        first.action_choose_destination(germany)
        self.assertEqual((first.state, first.destination_id), ('preparing', germany))

    def test_team_sets_the_destination_agreed_with_the_student(self):
        """None of the centre's destinations suits: the team agrees another one (e.g. through an
        intermediary organisation) and sets it on the mobility."""
        first, second = self._accepted()
        self._destinations(1, 1)
        self.call.action_open_destination_choice()
        with self.assertRaises(UserError):
            first.with_user(self.erasmus_user).action_agree_destination()
        first.with_user(self.erasmus_user).write({'country_id': self.env.ref('base.ie').id, 'city': 'Cork'})
        first.with_user(self.erasmus_user).action_agree_destination()
        self.assertEqual((first.state, first.destination_id, first.application_id.state), ('preparing', self.env['ems.erasmus.destination'], 'accepted'))
        self.assertTrue(second.turn_deadline, "The turn passes to the next one.")

    def test_own_destination_validated_by_the_erasmus_team(self):
        first, second = self._accepted()
        self._destinations(1, 1)
        self.call.action_open_destination_choice()
        proposal = {'proposal_host': 'Test Host GmbH', 'proposal_country_id': self.env.ref('base.at').id,
                    'proposal_city': 'Vienna'}
        with self.assertRaises(UserError):
            first._ems_portal_propose(proposal)
        first._ems_portal_propose(proposal, [('commitment.pdf', PDF)])
        self.assertEqual(first.proposal_state, 'pending')
        self.assertFalse(first.turn_deadline)
        self.assertTrue(second.turn_deadline, "The turn passes to the next one.")
        self.assertIn(self.erasmus_user, first.activity_ids.user_id)
        with self.assertRaises(AccessError):
            first.with_user(self.hos_user).action_validate_proposal()
        with self.assertRaises(UserError):
            first.with_user(self.erasmus_user).action_reject_proposal()
        first.with_user(self.erasmus_user).action_validate_proposal()
        self.assertEqual((first.state, first.country_id.code, first.city), ('preparing', 'AT', 'Vienna'))
        self.assertFalse(first.activity_ids)

    def test_rejected_own_destination_goes_back_to_choosing(self):
        first, _second = self._accepted()
        self._destinations(1, 1)
        first._ems_portal_propose({'proposal_host': 'Test Host', 'proposal_country_id': self.env.ref('base.at').id},
                                  [('commitment.pdf', PDF)])
        first.with_user(self.erasmus_user).decision_note = 'The traineeship plan does not fit the cycle.'
        first.with_user(self.erasmus_user).action_reject_proposal()
        self.assertEqual((first.state, first.proposal_state), ('choosing', 'rejected'))
        self.assertIn(first, first._ems_choosing())

    def test_close_needs_every_return_document_and_step(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self._complete_stage(first, 'preparation')
        self.assertTrue(first.preparation_complete)
        self.assertFalse(first.return_complete)
        with self.assertRaises(UserError):
            first.with_user(self.erasmus_user).action_close()
        self._complete_stage(first, 'return')
        # Audit D-5 and D-8 (test_erasmus_decisions.py): on a project, the EU Survey validated.
        today = self.env['ems.datetime_utils'].get_local_today()
        first.sudo().write({'date_start': today - timedelta(days=30), 'date_end': today - timedelta(days=1),
                            'project_id': self.env['ems.erasmus.project'].create(
                                {'name': 'TEST-CLOSE', 'kind': 'ka121_vet'}).id})
        first._ems_portal_eu_survey()
        first.with_user(self.erasmus_user).action_eu_survey_validate()
        first.with_user(self.erasmus_user).action_close()
        self.assertEqual(first.state, 'done')

    def test_a_new_upload_goes_back_to_review(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self._complete_stage(first, 'preparation')
        line = first.document_ids.filtered(lambda line: line.stage == 'preparation')[:1]
        first._ems_portal_upload({line.call_document_id.id: [('new.pdf', PDF)]})
        self.assertEqual(line.review_state, 'pending')
        self.assertEqual(len(line.attachment_ids), 2, "Every version is kept.")

    def test_documents_due_a_month_after_the_destination_and_reminded_weekly(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        today = self.env['ems.datetime_utils'].get_local_today()
        self.assertEqual(first.destination_date, today)
        lines = {line.name: line for line in first.document_ids}
        self.assertNotIn('Identity document', lines, "EMS already holds it.")
        self.assertEqual(lines['European Health Insurance Card'].deadline, today + timedelta(days=30))
        self.assertNotIn('Commitment letter', lines, "Signed in EMS, not uploaded.")
        self.assertEqual(lines['OLS certificate'].deadline, today + timedelta(days=30))
        self.assertEqual(lines['Insurance policy'].deadline, date(2027, 5, 2), "A month before leaving.")
        self.assertTrue(lines['Inclusion documentation'].confidential)
        self.assertEqual(lines['Grant agreement'].deadline, date(2027, 5, 2), "A month before leaving.")
        self.assertEqual(lines['Certificate of stay'].deadline, date(2027, 7, 30), "A month after returning.")
        self.assertEqual(lines['Certificate of stay'].handled_by, 'team_to_sign', "The host tutor signs the team's.")
        due = first._ems_documents_to_correct()
        self.assertNotIn(lines['Certificate of stay'], due, "Return documents are not asked for before the end.")
        self.assertNotIn(lines['Grant agreement'], due, "Not asked for before the team uploads it filled in.")
        lines['Grant agreement'].prepared_attachment_ids = self.env['ir.attachment'].create(
            {'name': 'grant_filled.pdf', 'raw': PDF})
        self.assertIn(lines['Grant agreement'], first._ems_documents_to_correct())
        sent = len(self._mails(first))
        self.env['ems.erasmus.mobility']._cron_remind_documents()
        self.assertEqual(len(self._mails(first)), sent + 1)
        self._complete_stage(first, 'preparation')
        self.env['ems.erasmus.mobility']._cron_remind_documents()
        self.assertEqual(len(self._mails(first)), sent + 1, "Nothing missing: no reminder.")

    def test_commitment_letter_signed_in_ems(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self.assertTrue(first.commitment_pending)
        with self.assertRaises(UserError):
            first.action_sign_commitment(False)
        first.action_sign_commitment(True, '10.0.0.7')
        self.assertFalse(first.commitment_pending)
        self.assertEqual(first.commitment_signed_ip, '10.0.0.7')
        self.assertIn('OLS', first.commitment_signed_text, "The text accepted is kept.")
        self.call.commitment_text = '<p>Changed later</p>'
        self.assertIn('OLS', first.commitment_signed_text, "A later change does not alter what was signed.")
        with self.assertRaises(UserError):
            first.action_sign_commitment(True)

    def test_the_family_of_a_minor_signs_the_commitment_letter_too(self):
        first, _second = self._accepted()
        family = self._minor_with_family()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self.assertEqual(first.state, 'preparing')
        self.assertTrue(first.commitment_guardian_pending)
        to_family = self._mails(first).filtered(lambda mail: mail.email_to == family.email)
        self.assertEqual(len(to_family), 1, "The family is told when the destination is set.")
        self.assertEqual(family._ems_erasmus_guardian_mobilities(), first)
        self.assertTrue(family._ems_erasmus_portal_visible())
        self._complete_stage(first, 'preparation', guardian=False)
        self.assertFalse(first.preparation_complete, "Not ready to leave without the family's signature.")
        self.env['ems.erasmus.mobility']._cron_remind_documents()
        self.assertEqual(len(self._mails(first).filtered(lambda mail: mail.email_to == family.email)), 2)
        first.action_sign_commitment(True, '10.0.0.8', guardian=True)
        self.assertTrue(first.preparation_complete)
        self.assertEqual(first.commitment_guardian_signed_ip, '10.0.0.8')
        with self.assertRaises(UserError):
            first.action_sign_commitment(True, guardian=True)

    def test_an_adult_signs_alone(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self.assertFalse(first.commitment_guardian_pending)
        with self.assertRaises(UserError):
            first.action_sign_commitment(True, guardian=True)

    def test_the_insurance_policy_is_provided_by_the_team(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        policy = first.document_ids.filtered(lambda line: line.name == 'Insurance policy')
        self.assertEqual(policy.handled_by, 'team')
        self.assertNotIn(policy, first._ems_documents_to_correct(), "The participant is never asked for it.")
        first._ems_portal_upload({policy.call_document_id.id: [('mine.pdf', PDF)]})
        self.assertFalse(policy.attachment_ids, "The participant cannot upload it.")
        self._complete_stage(first, 'preparation')
        self.assertTrue(first.preparation_complete)
        policy.prepared_attachment_ids = False
        self.assertFalse(first.preparation_complete, "Not ready to leave without the policy.")

    def test_project_of_the_modality_kind(self):
        first, _second = self._accepted()
        vet, hed = self.env['ems.erasmus.project'].create([
            {'name': 'TEST-KA121-VET-1', 'kind': 'ka121_vet'}, {'name': 'TEST-KA131-HED-1', 'kind': 'ka131_hed'}])
        with self.assertRaises(ValidationError):
            first.with_user(self.erasmus_user).project_id = hed
        first.with_user(self.erasmus_user).project_id = vet
        self.assertEqual(vet.mobility_ids, first)

    def test_notify_pending_documents(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        sent = len(self._mails(first))
        first.with_user(self.erasmus_user).action_notify_documents()
        self.assertEqual(len(self._mails(first)), sent + 1)

    def test_cancel_needs_a_reason_and_frees_the_place(self):
        first, _second = self._accepted()
        with self.assertRaises(UserError):
            first.with_user(self.erasmus_user).action_cancel()
        first.with_user(self.erasmus_user).cancel_reason = 'Travel documents not handed in on time.'
        first.with_user(self.erasmus_user).action_cancel()
        self.assertEqual((first.state, first.application_id.state), ('cancelled', 'renounced'))
        self.assertEqual(self.modality.free_places, 1)

    def test_participant_renounces(self):
        first, _second = self._accepted()
        first.action_renounce('Personal reasons')
        self.assertEqual((first.state, first.cancel_reason), ('cancelled', 'Personal reasons'))
        with self.assertRaises(UserError):
            first.action_renounce()

    def test_only_the_erasmus_team_changes_a_mobility(self):
        first, _second = self._accepted()
        with self.assertRaises(AccessError):
            first.with_user(self.hos_user).city = 'Berlin'
        first.with_user(self.erasmus_user).city = 'Berlin'

    def test_graduate_keeps_the_portal_until_the_mobility_is_closed(self):
        first, _second = self._accepted()
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.student.name, 'login': 'test_erasmus_graduate', 'partner_id': self.student.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.student.has_graduated = True
        wizard = self.env['ems.course_transition_wizard'].create({
            'target_course_id': self.env['ems.course'].search([], limit=1).id})
        issues = wizard._apply_graduates(self.student)
        self.assertTrue(self.student.active)
        self.assertTrue(self.student._has_active_portal_user())
        self.assertTrue(any(self.student.display_name in issue for issue in issues))
        first.action_renounce()
        self.assertFalse(self.student.active)
        self.assertFalse(self.student._has_active_portal_user())


class ErasmusStaffMobilityCase(ErasmusStaffCase):
    """Two staff selected after the definitive resolution; the first one, who proposed a job
    shadowing, accepts the place. A Director validates the activities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.director_user = create_role_user(cls, 'director', 'test_erasmus_director')
        # The call's Direction validates: the Director and the Head of Studies of FP. Another Head
        # of Studies (ESO) does not, even for an applicant who hangs below them in the chart.
        cls.staff_call.validator_ids = cls.director_user | cls.hos_user
        cls.other_hos_user = create_role_user(cls, 'head_of_studies', 'test_erasmus_other_hos',
                                              name='Test ESO Head Of Studies')
        cls.staff_employees[0].parent_id = create_role_employee(cls, cls.other_hos_user)

    def _accepted_staff(self):
        applications = self._admitted(0), self._admitted(1)
        applications[0].write({'staff_activity': 'job_shadowing', 'host_entity': 'Test VET School',
                               'destination': 'Porto', 'preferred_dates': 'June 2027'})
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        for application, last in zip(applications, ('never', 'older')):
            self._rate(application, '1', '1')
            self._complete(application, last=last, seniority='y2' if last == 'older' else 'y5')
        for kind in ('admission', 'provisional', 'definitive'):
            resolution = self.env['ems.erasmus.resolution'].with_user(self.erasmus_user).create({
                'call_id': self.staff_call.id, 'kind': kind})
            resolution.action_prepare()
            resolution.action_publish()
        applications[0].offer_ids.action_accept()
        return applications[0].mobility_ids

    def _send_proposal(self, mobility, declaration=True, **values):
        mobility._ems_portal_propose({'proposal_activity': mobility.proposal_activity,
                                      'proposal_host': mobility.proposal_host, 'proposal_city': mobility.proposal_city,
                                      'proposal_country_id': self.env.ref('base.pt').id,
                                      'proposal_date_start': '2027-06-14', 'proposal_date_end': '2027-06-18', **values},
                                     declaration=declaration)


@tagged('post_install', '-at_install')
class TestErasmusStaffMobility(ErasmusStaffMobilityCase):

    def test_staff_complete_their_proposal_with_the_dates_for_the_direction(self):
        mobility = self._accepted_staff()
        self.assertEqual((mobility.state, mobility.proposal_state), ('choosing', False))
        self.assertEqual((mobility.proposal_activity, mobility.proposal_host, mobility.proposal_city,
                          mobility.proposal_notes), ('job_shadowing', 'Test VET School', 'Porto', 'June 2027'))
        self.assertFalse(mobility.activity_ids, "Nothing to validate until the proposal is sent.")
        with self.assertRaises(UserError):
            self._send_proposal(mobility, proposal_date_start=False)
        with self.assertRaises(UserError):
            self._send_proposal(mobility, proposal_date_end='2027-06-01')
        self._send_proposal(mobility)
        self.assertEqual(mobility.proposal_state, 'pending')
        self.assertEqual(mobility.activity_ids.user_id, self.director_user | self.hos_user,
                         "Only the call's Direction: not their Head of Studies in the chart, not the administrator.")
        for user in (self.erasmus_user, self.other_hos_user):
            with self.assertRaises(AccessError):
                mobility.with_user(user).action_validate_proposal()
        with self.assertRaises(AccessError):
            mobility.with_user(self.director_user).city = 'Lisbon'
        mobility.with_user(self.hos_user).action_validate_proposal()
        self.assertEqual((mobility.state, mobility.decided_by_id, mobility.date_start, mobility.date_end),
                         ('preparing', self.hos_user, date(2027, 6, 14), date(2027, 6, 18)))
        self.assertTrue(self.env['mail.mail'].search([
            ('subject', 'like', 'your activity has been validated'), ('email_to', '=', mobility.partner_id.email)]))

    def test_direction_rejects_with_a_reason_and_the_teacher_proposes_again(self):
        mobility = self._accepted_staff()
        self._send_proposal(mobility)
        with self.assertRaises(UserError):
            self._send_proposal(mobility)
        mobility.with_user(self.director_user).decision_note = 'The dates leave the second-year groups uncovered.'
        mobility.with_user(self.director_user).action_reject_proposal()
        self.assertEqual(mobility.proposal_state, 'rejected')
        self._send_proposal(mobility, proposal_activity='course', proposal_host='Test Course Provider',
                            proposal_date_start='2027-07-05', proposal_date_end='2027-07-09')
        self.assertEqual((mobility.proposal_state, mobility.proposal_activity), ('pending', 'course'))
        self.assertFalse(mobility.decision_note)
        mobility.with_user(self.director_user).action_validate_proposal()
        self.assertEqual((mobility.state, mobility.date_start), ('preparing', date(2027, 7, 5)))

    def test_a_validated_activity_changes_only_when_the_direction_validates_it_again(self):
        mobility = self._accepted_staff()
        self._send_proposal(mobility)
        mobility.with_user(self.director_user).decision_note = 'Fine, cover the second-year groups.'
        mobility.with_user(self.director_user).action_validate_proposal()
        destination_date = mobility.destination_date
        self.assertEqual(mobility.leave_id.request_date_from, date(2027, 6, 14))
        # The course is not offered in June: another one in July.
        self._send_proposal(mobility, proposal_host='Test July Course', proposal_date_start='2027-07-05',
                            proposal_date_end='2027-07-09')
        self.assertEqual((mobility.state, mobility.proposal_state, mobility.date_start), ('preparing', 'pending',
                                                                                          date(2027, 6, 14)),
                         "It stays as validated until the Direction decides.")
        self.assertEqual(mobility.activity_ids.user_id, self.director_user | self.hos_user)
        mobility.with_user(self.hos_user).decision_note = 'The July dates are not possible.'
        mobility.with_user(self.hos_user).action_reject_proposal()
        self.assertEqual((mobility.state, mobility.proposal_state, mobility.date_start),
                         ('preparing', 'rejected', date(2027, 6, 14)))
        self._send_proposal(mobility, proposal_host='Test July Course', proposal_date_start='2027-07-12',
                            proposal_date_end='2027-07-16')
        mobility.with_user(self.hos_user).action_validate_proposal()
        self.assertEqual((mobility.state, mobility.proposal_state, mobility.date_start, mobility.destination_date),
                         ('preparing', 'validated', date(2027, 7, 12), destination_date))
        self.assertEqual(mobility.leave_id.request_date_from, date(2027, 7, 12), "The absence follows.")
        # The Erasmus team can also change it and ask the Direction again; never once it has started.
        mobility.with_user(self.erasmus_user).proposal_date_end = date(2027, 7, 17)
        mobility.with_user(self.erasmus_user).action_request_revalidation()
        self.assertEqual(mobility.proposal_state, 'pending')
        with self.assertRaises(UserError):
            mobility.with_user(self.erasmus_user).action_request_revalidation()

    def test_the_training_absence_is_requested_when_the_direction_validates(self):
        mobility = self._accepted_staff()
        with self.assertRaises(UserError):
            self._send_proposal(mobility, declaration=False)
        self._send_proposal(mobility)
        self.assertTrue(mobility.leave_declaration)
        self.assertFalse(mobility.leave_id, "Not before the Direction validates the dates.")
        mobility.with_user(self.director_user).action_validate_proposal()
        leave = mobility.leave_id
        self.assertEqual(leave.holiday_status_id, self.env.ref('ems.leave_type_training'))
        self.assertEqual(leave.employee_id, mobility.application_id.employee_id)
        self.assertEqual((leave.request_date_from, leave.request_date_to), (date(2027, 6, 14), date(2027, 6, 18)))
        self.assertIn(leave.state, ('confirm', 'validate1'), "Approved as any other absence.")
        mobility.with_user(self.erasmus_user).date_end = date(2027, 6, 19)
        self.assertEqual(leave.request_date_to, date(2027, 6, 19), "A request not decided yet follows the dates.")
        self.assertEqual(mobility.leave_id, leave, "Only one request.")
        mobility.with_user(self.erasmus_user).cancel_reason = 'Cannot go'
        mobility.with_user(self.erasmus_user).action_cancel()
        self.assertFalse(leave.exists(), "A request not decided yet is withdrawn with the mobility.")

    def test_the_modality_assigned_later_brings_its_documents(self):
        only_june = self.env['ems.erasmus.call.document'].create({
            'call_id': self.staff_call.id, 'stage': 'preparation', 'name': 'June only document',
            'modality_ids': [(6, 0, self.staff_call.modality_ids[1].ids)]})
        mobility = self._accepted_staff()
        self.assertNotIn(only_june, mobility.document_ids.call_document_id)
        mobility.application_id.modality_id = self.staff_call.modality_ids[1]
        self.assertIn(only_june, mobility.document_ids.call_document_id)

    def test_staff_documents_follow_the_project_of_the_modality(self):
        """KA121-VET: learning agreement, Europass document, the certificate only if needed.
        KA131-HED: mobility agreement and the certificate, no Europass document."""
        vet, hed = self.staff_call.modality_ids
        mobility = self._accepted_staff()
        mobility.application_id.modality_id = vet
        names = {line.name: line.is_required for line in mobility.document_ids}
        self.assertTrue(names["Learning agreement"])
        self.assertTrue(names["Europass mobility document"])
        self.assertFalse(names["Certificate of stay or attendance"], "Optional: the Europass document certifies it.")
        self.assertNotIn("Mobility agreement", names)
        mobility.document_ids.unlink()  # sync only adds lines: start again as if HED from the start
        mobility.application_id.modality_id = hed
        names = {line.name: line.is_required for line in mobility.document_ids}
        self.assertTrue(names["Mobility agreement"])
        self.assertTrue(names["Certificate of stay or attendance"])
        self.assertNotIn("Europass mobility document", names)
        self.assertNotIn("Learning agreement", names)
        self.assertFalse(mobility.placement_type, "Staff have no placement type.")

    def test_staff_calls_get_the_staff_mobility_documents(self):
        documents = self.staff_call.preparation_document_ids
        learning = documents.filtered(lambda document: document.name == 'Learning agreement')
        self.assertEqual(learning.signers, "participant, Erasmus coordinator, host entity")
        self.assertIn('Report with evidence', documents.mapped('name'))
        self.assertEqual(len(self.staff_call.document_ids), 2, "The application documents are unchanged.")


@tagged('post_install', '-at_install')
class TestPortalErasmusMobility(HttpCase, ErasmusMobilityCase):
    """Issue #687 - the mobility card on the portal: choose in the turn, upload the documents."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student_user, cls.second_user = cls.env['res.users'].with_context(no_reset_password=True).create([{
            'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
            'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        } for partner, login in ((cls.student, 'test_erasmus_mob_student'), (cls.second, 'test_erasmus_mob_second'))])

    def _post(self, step, files=None, **data):
        return self.url_open(f'/my/erasmus/call/{self.call.id}/mobility/{step}',
                             data={'csrf_token': Request.csrf_token(self), **data}, files=files)

    def test_choose_in_the_turn_and_upload_the_documents(self):
        first, second = self._accepted()
        cyprus, _germany = self._destinations(1, 1)
        self.call.action_open_destination_choice()
        self.authenticate(self.second_user.login, self.second_user.login)
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_waiting_turn', page)
        self.assertIn('error=1', self._post('choose', destination_id=cyprus.id).url)
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertIn('o_ems_erasmus_choose', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self.assertIn('saved=1', self._post('choose', destination_id=cyprus.id).url)
        self.assertEqual(first.destination_id, cyprus)
        line = first.document_ids[:1]
        self._post('upload', files={f'document_{line.call_document_id.id}': ('signed.pdf', PDF, 'application/pdf')})
        self.assertEqual(line.attachment_ids.mapped('name'), ['signed.pdf'])
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_mobility_documents', page)
        self.assertIn('signed.pdf', page)

    def test_the_virtual_component_is_shown_only_when_asked_for(self):
        self.modality.project = 'ka131_hed'
        first, _second = self._accepted()
        cyprus, _germany = self._destinations(1, 1)
        self.call.action_open_destination_choice()
        self.authenticate(self.student_user.login, self.student_user.login)
        self._post('choose', destination_id=cyprus.id)
        self.assertTrue(first.is_short_blended, "The destination's 30 days: short blended.")
        self.assertIn('Virtual component', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        first.date_end = date(2027, 8, 31)
        self.assertNotIn('Virtual component', self.url_open(f'/my/erasmus/call/{self.call.id}').text)

    def test_answer_the_weekly_self_assessment_on_the_portal(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        today = self.env['ems.datetime_utils'].get_local_today()
        first.write({'date_start': today - timedelta(days=2), 'date_end': today + timedelta(days=20)})
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertIn('o_ems_erasmus_self_assessment', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        answers = {f'question_{question.id}': '5' if question.kind == 'rating' else 'Portal answer'
                   for question in self.call.self_assessment_question_ids}
        self.assertIn('error=1', self._post('self_assessment', week='2', **answers).url, "Week 2 not begun yet.")
        self.assertIn('saved=1', self._post('self_assessment', week='1', **answers).url)
        self.assertEqual((first.self_assessment_ids.week, first.self_assessment_ids.rating), (1, 5))
        self.assertIn('o_ems_erasmus_self_assessment_sent', self.url_open(f'/my/erasmus/call/{self.call.id}').text)

    def test_own_proposal_and_renounce(self):
        first, _second = self._accepted()
        self.authenticate(self.student_user.login, self.student_user.login)
        self._post('propose', files={'proposal_files': ('commitment.pdf', PDF, 'application/pdf')},
                   proposal_host='Test Host GmbH', proposal_country_id=self.env.ref('base.at').id)
        self.assertEqual((first.proposal_state, first.proposal_host), ('pending', 'Test Host GmbH'))
        self.assertIn('o_ems_erasmus_proposal_pending', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self._post('renounce', reason='Personal reasons')
        self.assertEqual(first.state, 'cancelled')

    def test_download_the_document_the_team_filled_in(self):
        first, second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        line = first.document_ids.filtered(lambda line: line.name == 'Grant agreement')
        line.prepared_attachment_ids = self.env['ir.attachment'].create({'name': 'grant_filled.pdf', 'raw': PDF})
        url = f'/my/erasmus/call/{self.call.id}/mobility/file/{line.prepared_attachment_ids.id}'
        self.authenticate(self.second_user.login, self.second_user.login)
        self.assertNotEqual(self.url_open(url).content, PDF, "Only the participant downloads it.")
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertIn('o_ems_erasmus_prepared_file', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self.assertEqual(self.url_open(url).content, PDF)

    def test_sign_the_commitment_letter_on_the_portal(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertIn('o_ems_erasmus_commitment', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self.assertIn('error=1', self._post('commitment').url, "Not without ticking the acceptance.")
        self._post('commitment', accepted='on')
        self.assertEqual(first.commitment_signed_by_id, self.student_user)
        self.assertTrue(first.commitment_signed_ip)
        self.assertIn('o_ems_erasmus_commitment_signed', self.url_open(f'/my/erasmus/call/{self.call.id}').text)

    def test_the_family_signs_the_commitment_letter_on_its_portal(self):
        first, _second = self._accepted()
        family = self._minor_with_family()
        family_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': family.name, 'login': 'test_erasmus_mob_family', 'password': 'test_erasmus_mob_family',
            'partner_id': family.id, 'lang': 'en_US', 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self._destinations(2)
        self.call.action_open_destination_choice()
        url = f'/my/erasmus/commitment/{first.id}'

        def sign(**data):
            return self.url_open(url, data={'csrf_token': Request.csrf_token(self), **data})
        self.authenticate(self.student_user.login, self.student_user.login)
        self.assertIn('o_ems_erasmus_guardian_pending', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self.assertIn('error=1', sign(accepted='on').url, "The student does not sign for the family.")
        self.authenticate(family_user.login, family_user.login)
        self.assertIn('o_ems_erasmus_guardian_commitment', self.url_open('/my/erasmus').text)
        self.assertIn('error=1', sign().url, "Not without ticking the acceptance.")
        sign(accepted='on')
        self.assertEqual(first.commitment_guardian_signed_by_id, family_user)
        self.assertIn('o_ems_erasmus_guardian_signed', self.url_open('/my/erasmus').text)

    def test_a_minor_signs_their_own_letter_whether_the_family_signed_or_not(self):
        """The student's form shows while their own signature is missing, before or after the
        family's, and never again once signed."""
        first, _second = self._accepted()
        self._minor_with_family()
        self._destinations(2)
        self.call.action_open_destination_choice()
        self.authenticate(self.student_user.login, self.student_user.login)
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_guardian_pending', page)
        self.assertIn('o_ems_erasmus_commitment_sign', page)
        self._post('commitment', accepted='on')
        self.assertEqual(first.commitment_signed_by_id, self.student_user)
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_commitment_signed', page)
        self.assertNotIn('o_ems_erasmus_commitment_sign"', page)
