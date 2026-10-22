from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus import PDF
from .test_erasmus_resolution import ErasmusResolutionCase
from .test_erasmus_staff import ErasmusStaffCase


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

    def _complete_stage(self, mobility, stage):
        lines = mobility.document_ids.filtered(lambda line: line.stage == stage and line.is_required)
        mobility._ems_portal_upload({line.call_document_id.id: [('signed.pdf', PDF)] for line in lines})
        lines.action_mark_valid()
        mobility.task_ids.filtered(lambda task: task.stage == stage).write({'done': True})


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
        self.assertFalse(minors_only.is_required, "The student is an adult.")
        self.assertIn('host entity', first.document_ids.filtered(
            lambda line: line.call_document_id.sign_host)[:1].signers)

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

    def test_no_answer_in_the_turn_loses_the_place(self):
        first, second = self._accepted()
        self._destinations(1, 1)
        self.call.action_open_destination_choice()
        first.with_context(ems_erasmus_state=True).sudo().turn_deadline = fields.Datetime.now() - timedelta(minutes=1)
        self.env['ems.erasmus.mobility']._cron_expire_turns()
        self.assertEqual(first.state, 'cancelled')
        self.assertEqual(first.application_id.state, 'renounced')
        self.assertEqual(first.application_id.offer_ids.state, 'renounced')
        self.assertEqual(self.modality.free_places, 1)
        self.assertTrue(second.turn_deadline)

    def test_rejecting_every_destination_goes_back_to_the_reserve_list(self):
        first, second = self._accepted()
        self._destinations(1, 1)
        self.call.action_open_destination_choice()
        first.action_back_to_reserve()
        self.assertEqual(first.state, 'cancelled')
        self.assertEqual(first.application_id.state, 'reserve')
        self.assertEqual(first.application_id.offer_ids.state, 'returned')
        self.assertEqual(self.modality.free_places, 1)
        self.assertEqual(self.modality.next_reserve_id, first.application_id)
        self.assertTrue(second.turn_deadline)

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


@tagged('post_install', '-at_install')
class TestErasmusStaffMobility(ErasmusStaffMobilityCase):

    def test_staff_activity_waits_for_the_director(self):
        mobility = self._accepted_staff()
        self.assertEqual((mobility.state, mobility.proposal_state), ('choosing', 'pending'))
        self.assertEqual((mobility.proposal_activity, mobility.proposal_host, mobility.proposal_city),
                         ('job_shadowing', 'Test VET School', 'Porto'))
        self.assertIn(self.director_user, mobility.activity_ids.user_id)
        with self.assertRaises(AccessError):
            mobility.with_user(self.erasmus_user).action_validate_proposal()
        with self.assertRaises(AccessError):
            mobility.with_user(self.hos_user).action_validate_proposal()
        with self.assertRaises(AccessError):
            mobility.with_user(self.director_user).city = 'Lisbon'

    def test_director_rejects_with_a_reason_and_the_teacher_proposes_again(self):
        mobility = self._accepted_staff()
        with self.assertRaises(UserError):
            mobility._ems_portal_propose({'proposal_host': 'Other', 'proposal_country_id': self.env.ref('base.pt').id})
        mobility.with_user(self.director_user).decision_note = 'The dates leave the second-year groups uncovered.'
        mobility.with_user(self.director_user).action_reject_proposal()
        self.assertEqual(mobility.proposal_state, 'rejected')
        mobility._ems_portal_propose({'proposal_activity': 'course', 'proposal_host': 'Test Course Provider',
                                      'proposal_country_id': self.env.ref('base.pt').id, 'proposal_dates': 'July 2027'})
        self.assertEqual((mobility.proposal_state, mobility.proposal_activity), ('pending', 'course'))
        self.assertFalse(mobility.decision_note)
        mobility.with_user(self.director_user).action_validate_proposal()
        self.assertEqual((mobility.state, mobility.decided_by_id), ('preparing', self.director_user))

    def test_the_modality_assigned_later_brings_its_documents(self):
        only_june = self.env['ems.erasmus.call.document'].create({
            'call_id': self.staff_call.id, 'stage': 'preparation', 'name': 'June only document',
            'modality_ids': [(6, 0, self.staff_call.modality_ids[1].ids)]})
        mobility = self._accepted_staff()
        self.assertNotIn(only_june, mobility.document_ids.call_document_id)
        mobility.application_id.modality_id = self.staff_call.modality_ids[1]
        self.assertIn(only_june, mobility.document_ids.call_document_id)

    def test_staff_calls_get_the_staff_mobility_documents(self):
        names = self.staff_call.preparation_document_ids.mapped('name')
        self.assertIn('Mobility programme', names)
        self.assertIn('Report with evidence', names)
        self.assertEqual(len(self.staff_call.document_ids), 3, "The application documents are unchanged.")


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

    def test_own_proposal_and_renounce(self):
        first, _second = self._accepted()
        self.authenticate(self.student_user.login, self.student_user.login)
        self._post('propose', files={'proposal_files': ('commitment.pdf', PDF, 'application/pdf')},
                   proposal_host='Test Host GmbH', proposal_country_id=self.env.ref('base.at').id)
        self.assertEqual((first.proposal_state, first.proposal_host), ('pending', 'Test Host GmbH'))
        self.assertIn('o_ems_erasmus_proposal_pending', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        self._post('renounce', reason='Personal reasons')
        self.assertEqual(first.state, 'cancelled')
