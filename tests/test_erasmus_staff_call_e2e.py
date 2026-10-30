from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email
from .test_erasmus import PDF

# Per teacher: (panel rating relevance/transfer, last staff mobility, merits, declared language,
# centre start). Every panel member who rates gives the same rating. Totals (art. 11 of the staff
# call): 1. plan + 2. last mobility + 3. projects + 4. languages + 5. seniority + 6. internationalisation.
NEVER, OLDER, TWO_COURSES, RECENT = 'never', 'older', 'two_courses', 'recent'
TEACHERS = {
    'best': (('1', '1'), NEVER, ('project_coordination', 'project_collaboration', 'internationalisation',
                                 'internationalisation'), 'c1', 'y5_old'),   # 2 + 1.5 + 1.5 + 1.5 + 2 + 1 = 9.5
    'chief': (('1', '0.5'), OLDER, ('project_collaboration',), 'b2', 'y2'),  # 1.5 + 1.5 + 0.5 + 1 + 1.5 = 6
    'senior_old': (('1', '0.5'), TWO_COURSES, (), 'none', 'y5_old'),        # 1.5 + 0.5 + 2 = 4, since 2000
    'senior_new': (('1', '0.5'), TWO_COURSES, (), 'none', 'y5_new'),        # the same, 6 years only
    'plan_hi': (('1', '1'), RECENT, (), 'none', 'y2'),                      # 2 + 1.5 = 3.5
    'plan_lo': (('0.5', '0.5'), RECENT, ('project_collaboration',), 'none', 'y5_new'),  # 1 + 0.5 + 2 = 3.5
    'claim': (('0.5', '0'), NEVER, (), 'none', 'y1'),                       # 0.5 + 1.5 + 1 = 3; C1 claimed: 4.5
    'draw_1': (('0.5', '0.5'), RECENT, (), 'none', 'y1'),                   # 1 + 1 = 2
    'draw_2': (('0.5', '0.5'), RECENT, (), 'none', 'y1'),                   # the same: drawn
    'fix': (('0.5', '0.5'), RECENT, (), 'none', 'y0'),                      # 1, after correcting the CV
}
PLAN = {'staff_activity': 'job_shadowing', 'host_entity': 'E2E host school', 'destination': 'E2E city',
        'preferred_dates': 'June', 'plan_reason': 'E2E reason', 'plan_objectives': 'E2E objectives',
        'plan_application': 'E2E application'}


@tagged('post_install', '-at_install')
class TestErasmusStaffCallEndToEnd(TransactionCase):
    """A staff call with a VET (2 places) and a HED (1 place) modality, run from publishing to the
    definitive list, the place offers and a rectification, with the roles of the real process: the
    mobility technician runs it, the panel (Director, Head of Studies of FP, two department chiefs,
    one of them a candidate) rates the mobility plans, the coordinator draws the ties and publishes.
    The places are one pool and everyone is ranked in one list."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.level, cls.study, cls.group = create_level_study_group(cls, 'E2EST', group={'course': 1})
        cls.eso_level, eso_study, cls.eso_group = create_level_study_group(cls, 'E2ESO')
        cls.subject, cls.eso_subject = cls.env['ems.subject'].create([
            {'code': f'E2E{code}', 'acronym': f'E{code}', 'name': f'E2E staff module {code}', 'internal_hours': 99,
             'study_ids': [(4, study.id)]} for code, study in (('ST', cls.study), ('SO', eso_study))])
        cls.technician = create_role_user(cls, 'erasmus', 'test_e2e_staff_technician', email='tech@example.com')
        cls.coordinator = create_role_user(cls, 'erasmus_coordinator', 'test_e2e_staff_coordinator',
                                           email='coord@example.com')
        cls.director = create_role_user(cls, 'director', 'test_e2e_staff_director', email='director@example.com')
        cls.hos = create_role_user(cls, 'head_of_studies', 'test_e2e_staff_hos', email='hos@example.com')
        cls.chief_a = create_role_user(cls, 'department_chief', 'test_e2e_staff_chief_a', email='chief_a@example.com')
        for user in (cls.director, cls.hos, cls.chief_a):
            create_role_employee(cls, user)
        cls.users, cls.employees = {}, {}
        for index, name in enumerate([*TEACHERS, 'no_fix', 'eso', 'administration']):
            role = 'department_chief' if name == 'chief' else 'secretary' if name == 'administration' else 'teacher'
            user = create_role_user(cls, role, f'test_e2e_staff_{name}', name=f'E2E {name}',
                                    email=f'{name}@example.com')
            cls.users[name] = user
            cls.employees[name] = create_role_employee(
                cls, user, employee_type='asp' if name == 'administration' else 'teacher',
                identification_id=f'{20000000 + index}T')
            group, subject = (cls.eso_group, cls.eso_subject) if name in ('eso', 'administration') \
                else (cls.group, cls.subject)
            cls.env['ems.teaching'].create({'teacher_id': cls.employees[name].id, 'group_id': group.id,
                                            'subject_id': subject.id})
        now = fields.Datetime.now()
        cls.call = cls.env['ems.erasmus.call'].with_user(cls.technician).create({
            'name': 'E2E staff call',
            'audience': 'staff',
            'date_open': now - timedelta(days=1),
            'date_close': now + timedelta(days=10),
            'subsanation_deadline': now + timedelta(days=24),
            'claims_deadline': now + timedelta(days=40),
            'acceptance_deadline': now + timedelta(days=50),
            'staff_level_ids': [(6, 0, cls.level.ids)],
            'validator_ids': [(6, 0, (cls.director | cls.hos).ids)],
        })

    # --- helpers ----------------------------------------------------------------------------

    def _start(self, kind):
        close = self.call.date_close.date()
        return {'y5_old': '2000-09-01', 'y5_new': fields.Date.subtract(close, years=6),
                'y2': fields.Date.subtract(close, years=3), 'y1': fields.Date.subtract(close, months=18),
                'y0': fields.Date.subtract(close, months=3)}[kind]

    def _last_mobility(self, band):
        start = self.call.course_id.start
        if band == NEVER:
            return {'declared_never_staff_mobility': True}
        day = {OLDER: f'{start - 3}-11-01', TWO_COURSES: f'{start - 2}-11-01', RECENT: f'{start}-10-01'}[band]
        return {'declared_last_mobility_date': day}

    def _apply(self, name, documents=None):
        """What the portal does: the draft on the first visit, the form and the files, then submit."""
        _rating, last, _merits, language, start = TEACHERS.get(name, (None, RECENT, (), 'none', 'y1'))
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.call, self.users[name].partner_id)
        application._ems_portal_save(
            {**PLAN, **self._last_mobility(last), 'declared_centre_start_date': self._start(start),
             'declared_language_level': language, 'centre_projects': 'E2E projects'},
            {document.id: [(f'{document.name}.pdf', PDF)]
             for document in (documents if documents is not None else self.id_document | self.cv)})
        application.action_submit()
        return application

    def _team(self, application):
        return application.with_user(self.technician)

    def _rate(self, application, relevance, transfer):
        """Each panel member rates from *My plan ratings*, as themselves."""
        ratings = application.sudo().plan_rating_ids.filtered(lambda rating: not rating.abstention_reason)
        for rating in ratings:
            mine = rating.with_user(rating.evaluator_id)
            mine.write({'relevance': relevance, 'transfer': transfer})
            mine.action_submit()

    def _resolution(self, kind, **vals):
        resolution = self.env['ems.erasmus.resolution'].with_user(self.technician).create({
            'call_id': self.call.id, 'kind': kind, **vals})
        resolution.action_prepare()
        return resolution

    def _publish(self, kind, **vals):
        resolution = self._resolution(kind, **vals)
        with self.assertRaises(AccessError, msg="The technician prepares, only the coordinator publishes."):
            resolution.with_user(self.technician).action_publish()
        resolution.with_user(self.coordinator).action_publish()
        return resolution

    def _results(self, resolution):
        return {line.partner_id.name.removeprefix('E2E '): (line.result, line.rank) for line in resolution.line_ids}

    def _mails_to(self, name):
        return self.env['mail.mail'].search([('email_to', '=', f'{name}@example.com')])

    def _offer_next_reserve(self):
        wizard = self.env['ems.erasmus.offer.wizard'].with_user(self.technician).with_context(
            active_id=self.call.id).create({'deadline': fields.Datetime.now() + timedelta(days=3)})
        self.assertFalse(wizard.modality_id, "A staff call offers its places as one pool.")
        application = wizard.application_id
        wizard.action_confirm()
        return application

    # --- the whole process --------------------------------------------------------------------

    def test_staff_call_from_applying_to_selected_and_reserves(self):
        call = self.call
        # 1. The new call: art. 8's documents, two modalities (VET, HED) without places, no minimum
        # score, the panel's two weeks. The team adds the panel and publishes.
        self.assertEqual(call.min_score, 0.0)
        self.assertEqual(call.interview_deadline, call.date_close + timedelta(days=14))
        self.assertEqual(call.modality_ids.mapped('project'), ['ka121_vet', 'ka131_hed'])
        self.id_document, self.cv, self.certificate = call.document_ids.sorted('sequence')
        self.assertEqual((self.id_document.requirement, self.cv.requirement, self.certificate.requirement),
                         ('required', 'required', 'optional'))
        call.with_user(self.technician).write({'panel_ids': [
            (0, 0, {'user_id': user.id, 'post': post}) for user, post in (
                (self.director, 'Director'), (self.hos, 'Head of Studies of FP'),
                (self.chief_a, 'Head of department'), (self.users['chief'], 'Head of department'))]})
        with self.assertRaises(AccessError, msg="The Head of Studies reads the call, never changes it."):
            call.with_user(self.hos).write({'name': 'Changed'})
        call.with_user(self.technician).action_publish()

        # 2. Who can apply (art. 6): FP teachers and the Direction; not ESO teachers nor administration.
        for name, can_apply in (('best', True), ('eso', False), ('administration', False)):
            self.assertEqual(call in self.users[name].partner_id._ems_erasmus_calls(), can_apply, name)
        self.assertIn(call, self.director.partner_id._ems_erasmus_calls())
        with self.assertRaises(UserError):
            self.env['ems.erasmus.application']._ems_portal_get_or_create(call, self.users['eso'].partner_id)

        # 3. Applying: the mobility plan, the last mobility and the seniority are needed to submit.
        apps = {name: self._apply(name) for name in TEACHERS if name != 'fix'}
        incomplete = self.env['ems.erasmus.application']._ems_portal_get_or_create(call, self.users['no_fix'].partner_id)
        incomplete._ems_portal_save({**PLAN, 'plan_objectives': False}, {self.id_document.id: [('id.pdf', PDF)]})
        with self.assertRaises(UserError, msg="No CV, no last mobility, no seniority, no objectives."):
            incomplete.action_submit()
        apps['no_fix'] = self._apply('no_fix')
        apps['fix'] = self._apply('fix')
        self.assertTrue(self._mails_to('best'), "Submitting emails a receipt.")
        self.assertFalse(apps['best'].modality_id, "The team assigns the project after selection.")
        self.assertEqual(apps['best'].employee_id, self.employees['best'])

        # 4. Closing, then the review with corrections (art. 9).
        call.with_user(self.technician).action_close()
        self.assertEqual((apps['senior_old'].declared_seniority, apps['senior_new'].declared_seniority), ('y5', 'y5'))
        for name in ('no_fix', 'fix'):
            team = self._team(apps[name])
            team.requirements_check = 'met'
            team.document_ids.filtered(lambda line: line.call_document_id == self.cv).action_mark_needs_change()
            team.document_ids.filtered(lambda line: line.call_document_id == self.id_document).action_mark_valid()
            team.action_request_subsanation()
            self.assertEqual(apps[name].state, 'subsanation')
        self.assertTrue(self._mails_to('fix').filtered(lambda mail: 'Europass' in (mail.body_html or '')))
        apps['fix']._ems_portal_save({}, {self.cv.id: [('cv2.pdf', PDF)]})
        apps['fix'].action_submit()
        self.assertTrue(apps['fix'].activity_ids, "A corrected application becomes a task for the team.")
        for name, application in apps.items():
            if name == 'no_fix':
                continue
            team = self._team(application)
            team.requirements_check = 'met'
            team.document_ids.filtered('attachment_ids').action_mark_valid()
            team.action_admit()
        no_fix = self._team(apps['no_fix'])
        no_fix.exclusion_reason = 'Europass CV not corrected'
        no_fix.action_exclude()
        admission = self._publish('admission')
        self.assertEqual(self._results(admission)['no_fix'], ('excluded', 0))
        self.assertEqual(len(admission._ems_list_groups()), 1, "One list for the whole call.")

        # 5. The panel. The candidate in the panel abstains on every plan, their own included.
        with self.assertRaises(AccessError, msg="Only the Erasmus team sends the plans to the panel."):
            call.with_user(self.hos).action_send_to_panel()
        call.with_user(self.technician).action_send_to_panel()
        ratings = self.env['ems.erasmus.plan_rating'].sudo().search([('application_id.call_id', '=', call.id)])
        self.assertEqual(len(ratings), 4 * 10)
        self.assertEqual(set(ratings.filtered('abstention_reason').panel_member_id.ids), {self.users['chief'].id})
        self.assertNotIn(self.users['chief'], ratings.evaluator_id)
        mine = self.env['ems.erasmus.plan_rating'].with_user(self.chief_a).search([])
        self.assertEqual(len(mine), 10, "A panel member sees their own ratings only.")
        self.assertEqual(mine[:1].plan_objectives, 'E2E objectives')
        with self.assertRaises(AccessError, msg="A panel member never opens the application."):
            apps['best'].with_user(self.chief_a).read(['partner_id'])
        with self.assertRaises(AccessError, msg="Nor scores someone else's rating."):
            ratings.filtered(lambda rating: rating.evaluator_id == self.hos)[:1].with_user(self.chief_a).write(
                {'relevance': '1'})
        self.assertTrue(self.chief_a.has_group('ems.group_erasmus_evaluator'))
        for name, (rating, *_rest) in TEACHERS.items():
            self._rate(apps[name], *rating)
        self.assertEqual(apps['best'].plan_score, 2.0)
        self.assertTrue(apps['chief'].plan_complete, "Rated by the other three.")

        # 6. The team's criteria: merits (3, 6) reviewed for everyone; criteria 2, 4, 5 as declared.
        for name, (_rating, _last, merits, *_rest) in TEACHERS.items():
            self._team(apps[name]).write({
                'merit_ids': [(0, 0, {'kind': kind, 'description': 'E2E merit'}) for kind in merits],
                'merits_checked': True})
        expected = {'best': 9.5, 'chief': 6.0, 'senior_old': 4.0, 'senior_new': 4.0, 'plan_hi': 3.5, 'plan_lo': 3.5,
                    'claim': 3.0, 'draw_1': 2.0, 'draw_2': 2.0, 'fix': 1.0}
        self.assertEqual({name: apps[name].score_total for name in expected}, expected)
        self.assertEqual((apps['best'].score_projects, apps['best'].score_internationalisation), (1.5, 1.0))

        # 7. One ranking: the plan breaks a tie, then the seniority (since 2000 before 6 years), then a draw.
        self.assertEqual([apps[name].rank for name in ('best', 'chief', 'senior_old', 'senior_new', 'plan_hi',
                                                       'plan_lo', 'claim')], [1, 2, 3, 4, 5, 6, 7])
        draws = apps['draw_1'] | apps['draw_2']
        self.assertTrue(all(draws.mapped('needs_draw')))
        self.assertEqual(call.needs_draw, True)
        with self.assertRaises(UserError, msg="No provisional resolution with a tie."):
            self._resolution('provisional')
        with self.assertRaises(AccessError, msg="Only the coordinator draws."):
            call.with_user(self.technician).action_draw_ties()
        call.with_user(self.coordinator).action_draw_ties()
        self.assertEqual(sorted(draws.mapped('rank')), [8, 9])
        self.assertEqual(apps['fix'].rank, 10)

        # 8. The places, one pool: 2 VET + 1 HED. The provisional list needs them.
        with self.assertRaises(UserError, msg="No places, no provisional resolution."):
            self._resolution('provisional')
        vet, hed = call.modality_ids.sorted('sequence')
        call.with_user(self.technician).write({'modality_ids': [(1, vet.id, {'places': 2}), (1, hed.id, {'places': 1})]})
        provisional = self._publish('provisional')
        results = self._results(provisional)
        self.assertEqual({name: result for name, (result, _rank) in results.items() if result == 'selected'},
                         dict.fromkeys(('best', 'chief', 'senior_old'), 'selected'))
        self.assertEqual(results['claim'], ('reserve', 7))
        self.assertEqual(apps['best'].state, 'admitted', "A provisional list changes no application.")
        self.assertTrue(self._mails_to('claim').filtered(lambda mail: 'Provisional' in (mail.subject or '')
                                                        or 'provisional' in (mail.body_html or '')))
        with self.assertRaises(UserError, msg="The ratings lock once the provisional list is out."):
            apps['best'].sudo().plan_rating_ids.filtered('evaluator_id')[:1].with_user(self.hos).action_reopen()
        # The Head of Studies follows the process: reads the applications, the lists and the ranking.
        self.assertTrue(provisional.with_user(self.hos).line_ids.mapped('score_total'))
        with self.assertRaises(AccessError):
            apps['best'].with_user(self.hos).write({'merits_checked': False})

        # 9. A claim (art. 13): claim's C1 certificate had been missed. The team records it and answers.
        claim = self.env['ems.erasmus.claim'].with_user(self.technician).create({
            'application_id': apps['claim'].id, 'resolution_id': provisional.id,
            'description': 'My C1 certificate was not counted'})
        with self.assertRaises(AccessError, msg="The Head of Studies does not answer claims."):
            claim.with_user(self.hos).action_resolve()
        self._team(apps['claim']).language_level = 'c1'
        claim.response = 'Accepted: C1 certificate counted (criterion 4)'
        claim.action_resolve()
        self.assertEqual((apps['claim'].score_total, apps['claim'].rank), (4.5, 3))

        # 10. Definitive list, once the claims period is over: results set, offers to the selected.
        with self.assertRaises(UserError, msg="Not before the claims deadline."):
            self._resolution('definitive')
        call.with_user(self.technician).claims_deadline = fields.Datetime.now() - timedelta(minutes=1)
        definitive = self._publish('definitive')
        results = self._results(definitive)
        self.assertEqual(sorted(name for name, (result, _rank) in results.items() if result == 'selected'),
                         ['best', 'chief', 'claim'])
        self.assertEqual(results['senior_old'], ('reserve', 4))
        self.assertEqual(apps['senior_old'].state, 'reserve')
        self.assertEqual(call.free_places, 0)
        self.assertEqual(apps['best'].offer_ids.state, 'pending')
        self.assertFalse(apps['best'].offer_ids.modality_id)

        # 11. Answers: two accept, one renounces; the free place goes to the next reserve of the call.
        apps['best'].offer_ids.action_accept()
        apps['claim'].offer_ids.action_accept()
        self.assertEqual(apps['best'].state, 'accepted')
        self.assertTrue(apps['best'].mobility_ids, "Accepting starts the mobility.")
        apps['chief'].offer_ids.action_renounce('Family reasons')
        self.assertEqual(call.free_places, 1)
        self.assertTrue(call.activity_ids.filtered(lambda activity: activity.user_id == self.technician),
                        "A free place a reserve can take is a task for the team.")
        self.assertEqual(self._offer_next_reserve(), apps['senior_old'])
        # No answer by the deadline: renounced, and the next reserve gets the place.
        apps['senior_old'].offer_ids.sudo().deadline = fields.Datetime.now() - timedelta(minutes=1)
        self.env['ems.erasmus.offer']._cron_expire_offers()
        self.assertEqual(apps['senior_old'].state, 'renounced')
        self.assertEqual(self._offer_next_reserve(), apps['senior_new'])
        apps['senior_new'].offer_ids.action_accept()
        self.assertEqual(call.free_places, 0)
        self.assertFalse(call.activity_ids.filtered(lambda activity: activity.user_id == self.technician))
        # The team assigns each accepted person their project.
        self._team(apps['best']).modality_id = vet
        self._team(apps['claim']).modality_id = hed
        self.assertTrue(apps['claim'].mobility_ids.document_ids.filtered(
            lambda line: line.call_document_id.project == 'ka131_hed'), "The HED documents arrive with the project.")

        # 12. Rectification: plan_hi's project coordination had been missed (+1: 4.5, ahead of claim
        # by the plan). Three people already accepted: selecting plan_hi too would leave four people
        # for three places, so it cannot be published until the team adds a place.
        self._team(apps['plan_hi']).write({'merit_ids': [(0, 0, {'kind': 'project_coordination',
                                                                 'description': 'E2E missed merit'})]})
        self.assertEqual((apps['plan_hi'].score_total, apps['plan_hi'].rank, apps['claim'].rank), (4.5, 3, 4))
        rectification = self._resolution('rectification', notes='Project coordination of plan_hi counted')
        self.assertTrue(rectification.places_warning)
        with self.assertRaises(UserError):
            rectification.with_user(self.coordinator).action_publish()
        call.with_user(self.technician).write({'modality_ids': [(1, vet.id, {'places': 3})]})
        rectification.action_prepare()
        self.assertFalse(rectification.places_warning)
        rectification.with_user(self.coordinator).action_publish()
        self.assertEqual(apps['plan_hi'].offer_ids.state, 'pending')
        self.assertEqual((apps['claim'].state, apps['senior_new'].state), ('accepted', 'accepted'),
                         "Who accepted keeps the place.")
        self.assertEqual(call.free_places, 0)
        # Nothing went to a real address.
        self.assertFalse(self.env['mail.mail'].search([('id', 'in', self._mails_to('best').ids)]).filtered(
            lambda mail: not mail.email_to.endswith('@example.com')))

    def test_a_panel_member_who_applies_never_rates(self):
        """Art. 10: a panel member who is a candidate does not rate any plan; the plan score is the
        mean of the others."""
        call = self.call
        call.with_user(self.technician).write({'panel_ids': [
            (0, 0, {'user_id': user.id}) for user in (self.hos, self.users['chief'])]})
        call.with_user(self.technician).action_publish()
        self.id_document, self.cv, self.certificate = call.document_ids.sorted('sequence')
        apps = {name: self._apply(name) for name in ('best', 'chief')}
        call.with_user(self.technician).action_close()
        for application in apps.values():
            team = self._team(application)
            team.requirements_check = 'met'
            team.document_ids.filtered('attachment_ids').action_mark_valid()
            team.action_admit()
        call.with_user(self.technician).action_send_to_panel()
        self.assertFalse(self.users['chief'].has_group('ems.group_erasmus_evaluator'), "Nothing to rate.")
        self._rate(apps['best'], '1', '0.5')
        self.assertEqual((apps['best'].plan_score, apps['best'].plan_complete), (1.5, True))
