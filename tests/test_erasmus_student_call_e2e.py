from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .common import create_level_study_group, create_role_user, mock_outgoing_email, next_student_id
from .test_erasmus import PDF
from .test_erasmus_scoring import score_interview

# Per student: (record grade, interview general/english per criterion, language level, fewer
# opportunities, first mobility). Interviews are 0-5 per criterion: 4 general (max 20), 3 English
# (max 15). Totals: A = grade x 4, B = 4g + 3e, C/D/E as in art. 12.
GM = {
    'gm_best': (9.0, 5, 5, 'b2', 'no', 'yes'),       # 36 + 35 + 5 + 0 + 5 = 81
    'gm_second': (8.0, 4, 4, 'b1', 'no', 'yes'),     # 32 + 28 + 2.5 + 5 = 67.5
    'gm_reserve_1': (7.0, 4, 3, 'none', 'no', 'yes'),  # 28 + 25 + 5 = 58
    'gm_reserve_2': (6.0, 4, 3, 'none', 'no', 'yes'),  # 24 + 25 + 5 = 54
    'gm_low': (3.0, 2, 1, 'none', 'no', 'no'),       # 12 + 11 = 23 < 50
}
GS = {
    'gs_tie_1': (8.0, 4, 4, 'b1', 'no', 'yes'),      # 32 + 28 + 2.5 + 5 = 67.5
    'gs_tie_2': (8.0, 4, 4, 'b1', 'no', 'yes'),      # same: drawn
    'gs_claim': (8.0, 4, 4, 'none', 'no', 'yes'),    # 32 + 28 + 5 = 65; B2 after the claim: 70
    'gs_corrected': (6.0, 4, 3, 'none', 'no', 'no'),  # 24 + 25 = 49, + 10 (D accredited below) = 59
    'gs_single': (7.0, 4, 3, 'b1', 'no', 'no'),      # 28 + 25 + 2.5 = 55.5, one interview
}


@tagged('post_install', '-at_install')
class TestErasmusStudentCallEndToEnd(TransactionCase):
    """A students' call with a GM (KA121-VET) and a GS (KA131-HED) modality, 2 places each, run
    from publishing to the definitive list and the place offers, with the roles of the real
    process: the mobility technician runs it, the evaluators score the interviews, the coordinator
    draws the ties and publishes, the Head of Studies only reads."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.strike_escalation_threshold = 3
        cls.gm_level, cls.gm_study, cls.gm_group = create_level_study_group(cls, 'E2EGM', group={'course': 2})
        cls.gs_level, cls.gs_study, cls.gs_group = create_level_study_group(cls, 'E2EGS', group={'course': 2})
        cls.subjects = cls.env['ems.subject'].create([
            {'code': f'E2E{prefix}', 'acronym': f'E{prefix}', 'name': f'E2E module {prefix}', 'internal_hours': 99,
             'study_ids': [(4, study.id)]}
            for prefix, study in (('GM', cls.gm_study), ('GS', cls.gs_study))])
        cls.technician = create_role_user(cls, 'erasmus', 'test_e2e_technician', email='tech@example.com')
        cls.coordinator = create_role_user(cls, 'erasmus_coordinator', 'test_e2e_coordinator',
                                           email='coord@example.com')
        cls.hos = create_role_user(cls, 'head_of_studies', 'test_e2e_hos')
        cls.evaluators = [create_role_user(cls, 'teacher', f'test_e2e_evaluator_{n}') for n in (1, 2, 3)]
        now = fields.Datetime.now()
        cls.call = cls.env['ems.erasmus.call'].with_user(cls.technician).create({
            'name': 'E2E students call',
            'date_open': now - timedelta(days=1),
            'date_close': now + timedelta(days=10),
            'subsanation_deadline': now + timedelta(days=20),
            'interview_deadline': now + timedelta(days=30),
            'claims_deadline': now + timedelta(days=40),
            'acceptance_deadline': now + timedelta(days=50),
            'modality_ids': [
                (0, 0, {'name': 'GM', 'sequence': 1, 'level_ids': [(6, 0, cls.gm_level.ids)],
                        'project': 'ka121_vet', 'places': 2}),
                (0, 0, {'name': 'GS', 'sequence': 2, 'level_ids': [(6, 0, cls.gs_level.ids)],
                        'project': 'ka131_hed', 'places': 2}),
            ],
            'document_ids': [
                (0, 0, {'name': 'CV', 'requirement': 'required', 'sequence': 1}),
                (0, 0, {'name': 'Motivation letter', 'requirement': 'required', 'sequence': 2}),
            ],
        })
        cls.call.with_user(cls.technician).action_publish()
        cls.gm, cls.gs = cls.call.modality_ids.sorted('sequence')
        cls.cv, cls.letter = cls.call.document_ids.sorted('sequence')
        names = [*GM, 'gm_blocked', 'gm_no_fix', 'gm_no_show', *GS]
        cls.students = {}
        for index, name in enumerate(names):
            group = cls.gm_group if name.startswith('gm') else cls.gs_group
            cls.students[name] = cls.env['res.partner'].create({
                'name': f'E2E {name}', 'contact_type': 'student', 'student_id': next_student_id(),
                'main_group_id': group.id, 'birth_date': '2004-01-01', 'email': f'{name}@example.com',
                'document_id': f'{10000000 + index}T'})
        for name, values in {**GM, **GS}.items():
            cls._grade(cls.students[name], values[0])
        for name in ('gm_no_fix', 'gm_no_show'):
            cls._grade(cls.students[name], 7.0)
        for _n in range(3):
            cls.env['ems.strike'].create({
                'student_id': cls.students['gm_blocked'].id, 'date': now - timedelta(hours=1),
                'teacher_id': cls.env['hr.employee'].search([], limit=1).id})

    @classmethod
    def _grade(cls, partner, grade):
        group = partner.main_group_id
        subject = cls.subjects.filtered(lambda subject: group.study_id in subject.study_ids)
        values = {'group_id': group.id, 'subject_id': subject.id, 'round': '1'}
        session = cls.env['ems.grade_session'].search([(key, '=', value) for key, value in values.items()]) \
            or cls.env['ems.grade_session'].create(values)
        line = session.grade_subject_line_ids.filtered(lambda line: line.student_id == partner) \
            or cls.env['ems.grade_subject_line'].create({'grade_session_id': session.id, 'student_id': partner.id})
        line.write({'is_overridden': True, 'internal_score': grade})

    # --- helpers ----------------------------------------------------------------------------

    def _apply(self, name, documents=None):
        """What the portal does: the draft on the first save, the files, then submit."""
        Application = self.env['ems.erasmus.application']
        application = Application._ems_portal_get_or_create(self.call, self.students[name])
        application._ems_portal_save({'availability': 'Any time', 'fewer_opportunities': False},
                                     {document.id: [(f'{document.name}.pdf', PDF)]
                                      for document in (documents if documents is not None else self.cv | self.letter)})
        application.action_submit()
        return application

    def _review(self, application, valid=True):
        team = application.with_user(self.technician)
        team.requirements_check = 'met'
        lines = team.document_ids
        if valid:
            lines.filtered('attachment_ids').action_mark_valid()
        return team

    def _interview(self, application, general, english, evaluators=2):
        for evaluator in self.evaluators[:evaluators]:
            interview = self.env['ems.erasmus.interview'].with_user(self.technician).create({
                'application_id': application.id, 'evaluator_id': evaluator.id})
            score_interview(interview.with_user(evaluator), general, english)

    def _score(self, application, values):
        _grade, general, english, language, fewer, first = values
        self._interview(application, general, english, evaluators=1 if application == self.apps.get('gs_single') else 2)
        application.with_user(self.technician).write({
            'language_level': language, 'fewer_opportunities_check': fewer, 'first_mobility': first})

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

    def _results(self, resolution, modality):
        lines = resolution.line_ids.filtered(lambda line: line.modality_id == modality)
        return [(line.partner_id.name.removeprefix('E2E '), line.result, line.rank) for line in lines]

    def _mails_to(self, name):
        return self.env['mail.mail'].search([('email_to', '=', f'{name}@example.com')])

    # --- the whole process --------------------------------------------------------------------

    def test_gm_and_gs_from_applying_to_selected_and_reserves(self):
        self.apps = {}
        # 1. Applying. Blocked by conduct warnings: no application at all.
        with self.assertRaises(UserError):
            self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.students['gm_blocked'])
        for name in (*GM, 'gm_no_show', *GS):
            self.apps[name] = self._apply(name)
        self.assertEqual(self.apps['gm_best'].modality_id, self.gm)
        self.assertEqual(self.apps['gs_tie_1'].modality_id, self.gs)
        # Missing a required document: cannot submit.
        no_fix = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.students['gm_no_fix'])
        no_fix._ems_portal_save({}, {self.cv.id: [('cv.pdf', PDF)]})
        with self.assertRaises(UserError):
            no_fix.action_submit()
        no_fix._ems_portal_save({}, {self.letter.id: [('letter.pdf', PDF)]})
        no_fix.action_submit()
        self.apps['gm_no_fix'] = no_fix
        self.assertTrue(self._mails_to('gm_best'), "Submitting emails a receipt.")

        # 2. Closing, then the review with corrections.
        self.call.with_user(self.technician).action_close()
        self.assertTrue(self.apps['gm_best'].scoring_frozen_date)
        self.assertAlmostEqual(self.apps['gm_best'].grade_average, 9.0)
        for name in ('gm_no_fix', 'gs_corrected'):
            team = self._review(self.apps[name], valid=False)
            team.document_ids.filtered(lambda line: line.call_document_id == self.letter).action_mark_needs_change()
            team.document_ids.filtered(lambda line: line.call_document_id == self.cv).action_mark_valid()
            team.action_request_subsanation()
            self.assertEqual(self.apps[name].state, 'subsanation')
        corrected = self.apps['gs_corrected']
        with self.assertRaises(UserError, msg="Only the documents asked for can be corrected."):
            corrected._ems_portal_save({}, {self.cv.id: [('cv2.pdf', PDF)]})
        corrected._ems_portal_save({}, {self.letter.id: [('letter2.pdf', PDF)]})
        corrected.action_submit()
        self.assertEqual(corrected.state, 'submitted')
        self.assertTrue(corrected.activity_ids, "A corrected application becomes a task for the team.")
        self._review(corrected).document_ids.action_mark_valid()
        for name, application in self.apps.items():
            if name == 'gm_no_fix':
                continue
            self._review(application)
            application.with_user(self.technician).action_admit()
        self.assertFalse(corrected.activity_ids)
        no_fix_team = self.apps['gm_no_fix'].with_user(self.technician)
        no_fix_team.exclusion_reason = 'Motivation letter not corrected'
        no_fix_team.action_exclude()

        admission = self._publish('admission')
        self.assertEqual(self._results(admission, self.gm).count(('gm_no_fix', 'excluded', 0)), 1)
        self.assertTrue(self._mails_to('gm_no_fix').filtered(lambda mail: 'Motivation letter not corrected'
                                                             in (mail.body_html or '')))

        # 3. Interviews: called 24 hours ahead at least; who does not come is excluded.
        no_show = self.apps['gm_no_show'].with_user(self.technician)
        no_show.interview_date = fields.Datetime.now() + timedelta(hours=2)
        with self.assertRaises(UserError):
            no_show.action_send_interview_call()
        (self.apps['gm_best'] | no_show).with_user(self.technician).write(
            {'interview_date': fields.Datetime.now() + timedelta(days=2)})
        (self.apps['gm_best'] | no_show).with_user(self.technician).action_send_interview_call()
        no_show.exclusion_reason = 'Did not attend the interview'
        no_show.action_exclude()
        single = self.apps['gs_single'].with_user(self.technician)
        single.single_interview_reason = 'Second evaluator ill'
        for name, values in {**GM, **GS}.items():
            self._score(self.apps[name], values)
        # gs_corrected declared fewer opportunities and the team accredited it.
        corrected.with_user(self.technician).fewer_opportunities_check = 'yes'
        for application in self.apps.values():
            if application.state == 'admitted':
                self.assertTrue(application.score_complete, application.partner_id.name)
        with self.assertRaises(AccessError, msg="An evaluator only sees their own interviews."):
            self.apps['gm_best'].interview_ids.filtered(
                lambda interview: interview.evaluator_id == self.evaluators[0]).with_user(
                self.evaluators[1]).read(['general_score'])

        # 4. Ranking per modality: GM never competes with GS; the exact GS tie needs a draw.
        self.assertEqual([self.apps[name].rank for name in GM], [1, 2, 3, 4, 5])
        self.assertTrue(self.apps['gs_tie_1'].needs_draw and self.apps['gs_tie_2'].needs_draw)
        with self.assertRaises(UserError, msg="No provisional resolution with a tie."):
            self._resolution('provisional')
        with self.assertRaises(AccessError, msg="Only the coordinator draws."):
            self.call.with_user(self.technician).action_draw_ties()
        self.call.with_user(self.coordinator).action_draw_ties()
        ties = self.apps['gs_tie_1'] | self.apps['gs_tie_2']
        self.assertFalse(any(ties.mapped('needs_draw')))
        self.assertEqual(sorted(ties.mapped('rank')), [1, 2])
        winner = ties.filtered(lambda application: application.rank == 1)
        loser = ties - winner

        # 5. Provisional list, the Head of Studies reads the total only.
        provisional = self._publish('provisional')
        self.assertEqual(self._results(provisional, self.gm), [
            ('gm_best', 'selected', 1), ('gm_second', 'selected', 2), ('gm_reserve_1', 'reserve', 3),
            ('gm_reserve_2', 'reserve', 4), ('gm_low', 'not_selected', 5),
            ('gm_no_fix', 'excluded', 0), ('gm_no_show', 'excluded', 0)])
        gs_results = dict((name, (result, rank)) for name, result, rank in self._results(provisional, self.gs))
        self.assertEqual(gs_results['gs_claim'], ('reserve', 3))
        self.assertEqual(self.apps['gm_best'].state, 'admitted', "A provisional list changes no application.")
        hos_line = provisional.line_ids[:1].with_user(self.hos)
        self.assertTrue(hos_line.score_total)
        with self.assertRaises(AccessError):
            hos_line.read(['score_a'])
        with self.assertRaises(UserError, msg="Interviews lock once the provisional list is out."):
            self.apps['gm_best'].interview_ids[:1].with_user(self.evaluators[0]).action_reopen()

        # 6. A claim: gs_claim's B2 certificate had been missed. The team corrects C and answers.
        claim = self.env['ems.erasmus.claim'].with_user(self.technician).create({
            'application_id': self.apps['gs_claim'].id, 'resolution_id': provisional.id,
            'description': 'My B2 certificate was not counted'})
        self.apps['gs_claim'].with_user(self.technician).language_level = 'b2'
        claim.response = 'Accepted: B2 certificate counted (criterion C)'
        claim.action_resolve()
        self.assertEqual(self.apps['gs_claim'].rank, 1)

        # 7. Definitive list, once the claims period is over: results set, offers to the selected.
        with self.assertRaises(UserError, msg="Not before the claims deadline."):
            self._resolution('definitive')
        self.call.with_user(self.technician).claims_deadline = fields.Datetime.now() - timedelta(minutes=1)
        definitive = self._publish('definitive')
        self.assertEqual(dict((n, r) for n, r, _rank in self._results(definitive, self.gs)), {
            'gs_claim': 'selected', winner.partner_id.name.removeprefix('E2E '): 'selected',
            loser.partner_id.name.removeprefix('E2E '): 'reserve', 'gs_single': 'reserve',
            'gs_corrected': 'reserve'})
        self.assertEqual(self.apps['gm_reserve_1'].state, 'reserve')
        self.assertEqual(self.apps['gm_low'].state, 'not_selected')
        for modality in (self.gm, self.gs):
            self.assertEqual(self.call._ems_free_places(modality), 0)
        self.assertEqual(self.apps['gm_best'].offer_ids.state, 'pending')
        self.assertFalse(self.apps['gm_reserve_1'].offer_ids)

        # 8. Answers: one accepts, one renounces; the place goes to the reserves in order.
        self.apps['gm_best'].offer_ids.action_accept()
        self.assertEqual(self.apps['gm_best'].state, 'accepted')
        self.assertTrue(self.apps['gm_best'].mobility_ids)
        self.apps['gm_second'].offer_ids.action_renounce('Found a job')
        self.assertEqual(self.call._ems_free_places(self.gm), 1)
        wizard = self.env['ems.erasmus.offer.wizard'].with_user(self.technician).with_context(
            active_id=self.call.id).create({'deadline': fields.Datetime.now() + timedelta(days=3)})
        self.assertEqual((wizard.modality_id, wizard.application_id), (self.gm, self.apps['gm_reserve_1']))
        wizard.action_confirm()
        reserve_offer = self.apps['gm_reserve_1'].offer_ids
        self.assertTrue(reserve_offer.from_reserve)
        # No answer by the deadline: renounced, and the next reserve gets the place.
        reserve_offer.sudo().deadline = fields.Datetime.now() - timedelta(minutes=1)
        self.env['ems.erasmus.offer']._cron_expire_offers()
        self.assertEqual((reserve_offer.state, self.apps['gm_reserve_1'].state), ('expired', 'renounced'))
        wizard = self.env['ems.erasmus.offer.wizard'].with_user(self.technician).with_context(
            active_id=self.call.id).create({'deadline': fields.Datetime.now() + timedelta(days=3)})
        self.assertEqual(wizard.application_id, self.apps['gm_reserve_2'])
        wizard.action_confirm()
        self.apps['gm_reserve_2'].offer_ids.action_accept()
        self.assertEqual(self.call._ems_free_places(self.gm), 0)
        self.assertEqual(self.call.application_ids.filtered(lambda application: application.state == 'accepted'
                                                            and application.modality_id == self.gm).partner_id,
                         self.students['gm_best'] | self.students['gm_reserve_2'])

    def test_who_joins_a_drawn_tie_is_drawn_with_it(self):
        """A claim upheld after the draw ties a third student with the two drawn: the three are
        drawn again, nobody goes first without a draw."""
        self.apps = {name: self._apply(name) for name in ('gs_tie_1', 'gs_tie_2', 'gs_claim')}
        self.call.with_user(self.technician).action_close()
        for name, application in self.apps.items():
            self._review(application).action_admit()
            self._score(application, GS[name])
        self.call.with_user(self.coordinator).action_draw_ties()
        self.assertFalse(self.call.needs_draw)
        self.apps['gs_claim'].with_user(self.technician).language_level = 'b1'
        tied = self.call.application_ids
        self.assertTrue(all(tied.mapped('needs_draw')))
        self.call.with_user(self.coordinator).action_draw_ties()
        self.assertEqual(sorted(tied.mapped('draw_order')), [1, 2, 3])
        self.assertEqual(sorted(tied.mapped('rank')), [1, 2, 3])
        self.assertEqual(len(self.call.draw_ids), 2)
