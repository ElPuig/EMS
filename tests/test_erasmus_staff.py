import io
from datetime import timedelta

import openpyxl
from pytz import UTC

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import Request
from odoo.tests.common import HttpCase, TransactionCase, tagged

from .common import create_role_employee, create_role_user, mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures, upload


# The mobility plan (annex 1), written in the form and required to submit (issue #697).
STAFF_PLAN = {'proposal_a': 'Test proposal A: job shadowing at a VET school in Porto, in June',
              'proposal_b': 'Test proposal B: an English course in Malta, in July',
              'plan_text': 'Test plan: what to learn and how to apply it'}


def create_staff_call_fixtures(cls):
    """create_erasmus_fixtures() (a students' call, its team and Head of Studies) plus a
    published staff call: two modalities of one place each, an identity document and an
    optional certificate, for the teachers of the test level; a
    panel of the Head of Studies and two teachers; three teachers of a group of that level who can
    apply, the third one also in the panel."""
    create_erasmus_fixtures(cls)
    # Any other open staff call of the database (one published on a copy of production) stays out.
    cls.env['ems.erasmus.call'].search([('audience', '=', 'staff'), ('state', '=', 'published')]).state = 'closed'
    now = fields.Datetime.now()
    cls.panel_teacher = create_role_user(cls, 'teacher', 'test_erasmus_panel_teacher')
    cls.staff_users = [create_role_user(cls, 'teacher', f'test_erasmus_staff_{index}', name=f'Erasmus Staff {index}',
                                        email=f'erasmus.staff{index}@example.com') for index in (1, 2, 3)]
    cls.staff_employees = [create_role_employee(cls, user, identification_id=document)
                           for user, document in zip(cls.staff_users, ('11111111H', '22222222J', 'Y2222222E'))]
    cls.subject = cls.env['ems.subject'].create({
        'code': 'TERA001', 'acronym': 'TERA', 'name': 'Test Erasmus Subject', 'study_ids': [(6, 0, cls.study.ids)]})
    cls.env['ems.teaching'].create([{'teacher_id': employee.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id}
                                    for employee in cls.staff_employees])
    cls.staff_call = cls.env['ems.erasmus.call'].create({
        'name': 'Test Erasmus Staff Call',
        'audience': 'staff',
        'min_score': 0.0,
        'staff_level_ids': [(6, 0, cls.level.ids)],
        'validator_ids': [(6, 0, cls.hos_user.ids)],
        'date_open': now - timedelta(days=1),
        'date_close': now + timedelta(days=10),
        'acceptance_deadline': now + timedelta(days=20),
        'modality_ids': [(0, 0, {'name': 'Test VET staff', 'project': 'ka121_vet', 'places': 1, 'sequence': 1}),
                         (0, 0, {'name': 'Test HED staff', 'project': 'ka131_hed', 'places': 1, 'sequence': 2})],
        'document_ids': [
            (0, 0, {'name': 'Identity document', 'requirement': 'required', 'sequence': 1}),
            (0, 0, {'name': 'Staff language certificate', 'requirement': 'optional', 'sequence': 3}),
        ],
        'panel_ids': [(0, 0, {'user_id': user.id, 'post': post}) for user, post in (
            (cls.hos_user, 'Head of Studies'), (cls.panel_teacher, 'Head of department'),
            (cls.staff_users[2], 'Seminar chief'))],
    })
    # Issue #767 fills the deadlines in from the closing date: the tests set the ones they need.
    cls.staff_call.write({'subsanation_deadline': False, 'claims_deadline': False})
    cls.staff_call.action_publish()
    cls.id_document, cls.staff_certificate = cls.staff_call.document_ids.sorted('sequence')


class ErasmusStaffCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)

    def _apply(self, index, **answers):
        partner = self.staff_users[index].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        answers = {'declared_never_staff_mobility': True, 'declared_centre_start_date': '2015-09-01', **STAFF_PLAN,
                   **answers}
        application._ems_portal_save(answers, {self.id_document.id: [('id.pdf', PDF)]})
        application.action_submit()
        return application

    def _admitted(self, index):
        application = self._apply(index)
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        return application

    def _rate(self, application, relevance, transfer):
        """Every rating of `application` scored and submitted, but the abstentions."""
        for rating in application.sudo().plan_rating_ids.filtered(
                lambda rating: rating.state == 'draft' and not rating.abstention_reason):
            rating.write({'relevance': relevance, 'transfer': transfer})
            rating.action_submit()

    def _complete(self, application, last='never', language='none', seniority='y5', merits=()):
        application.write({'last_staff_mobility': last, 'language_level': language, 'seniority': seniority,
                           'merit_ids': [(0, 0, {'kind': kind, 'description': 'Test merit'}) for kind in merits],
                           'merits_checked': True})


@tagged('post_install', '-at_install')
class TestErasmusStaffCall(ErasmusStaffCase):

    def test_staff_calls_are_for_internal_users_with_an_employee_file(self):
        staff = self.staff_users[0].partner_id
        self.assertEqual(staff._ems_erasmus_calls(), self.staff_call)
        self.assertFalse(staff._ems_erasmus_portal_visible(), "Staff apply in the backend, never on the portal.")
        self.assertNotIn(self.staff_call, self.student._ems_erasmus_calls())
        self.assertFalse(self.panel_teacher.partner_id._ems_erasmus_calls())  # no employee file

    def test_staff_apply_once_without_a_modality(self):
        application = self._apply(0, proposal_a='Test host', fewer_opportunities=True)
        self.assertEqual(application.employee_id, self.staff_employees[0])
        self.assertFalse(application.modality_id)
        self.assertFalse(application.is_minor)
        self.assertEqual(application.proposal_a, 'Test host')
        self.assertFalse(application.fewer_opportunities, "A students' answer, ignored.")
        with self.assertRaises(UserError):
            application._ems_portal_save({'declared_language_level': 'b1'}, {})
        with self.assertRaises(UserError):
            self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, self.student)

    def test_staff_conduct_warnings_never_count(self):
        application = self._admitted(0)
        self.assertEqual(application.state, 'admitted')
        self.assertFalse(application.conduct_review)

    def test_a_call_with_applications_keeps_its_audience(self):
        self._apply(0)
        with self.assertRaises(UserError):
            self.staff_call.audience = 'student'

    def test_a_staff_call_opens_without_places_and_with_the_call_documents(self):
        # The validators default to the Director: the test's own, not whoever the database has.
        self.env.company.director_id = create_role_employee(
            self, create_role_user(self, 'director', 'test_erasmus_staff_open_director'))
        call = self.env['ems.erasmus.call'].create({
            'name': 'Staff call without places', 'audience': 'staff', 'date_open': self.staff_call.date_open,
            'date_close': self.staff_call.date_close})
        self.assertEqual(call.document_ids.mapped('requirement'), ['optional'],
                         "Only the language certificates: no CV, and the identity document only of whoever goes.")
        self.assertEqual(call.modality_ids.mapped('project'), ['ka121_vet', 'ka131_hed'],
                         "One modality per project, without a period.")
        self.assertFalse(call.document_ids.filtered('panel_visible'), "The mobility plan is written in the form.")
        result = call.action_publish()
        self.assertEqual(call.state, 'published')
        self.assertEqual(result['params']['type'], 'warning', "Published, but warned that it has no places yet.")
        self.assertIsNone(self.staff_call.copy().action_publish(), "With places, no warning.")

    def test_a_staff_call_is_only_for_fp_teachers_and_their_direction(self):
        """Art. 6: the teachers of its levels and the Direction that validates; not the
        administration staff, a teacher of another level only or another Head of Studies."""
        def employee(login, role='teacher', **values):
            return create_role_employee(self, create_role_user(self, role, login, name=login), **values)

        other_teacher, administration = employee('test_erasmus_eso_teacher'), employee(
            'test_erasmus_administration', employee_type='asp')
        other_study = self.env['ems.study'].search([('level_id', '=', self.other_level.id)], limit=1)
        other_subject = self.env['ems.subject'].create({
            'code': 'TERB001', 'acronym': 'TERB', 'name': 'Test Erasmus Other Subject',
            'study_ids': [(6, 0, other_study.ids)]})
        teaching = {'group_id': self.other_group.id, 'subject_id': other_subject.id}
        self.env['ems.teaching'].create([{**teaching, 'teacher_id': other_teacher.id},
                                         {**teaching, 'teacher_id': administration.id}])
        head_of_studies = create_role_employee(self, self.hos_user)
        other_head = employee('test_erasmus_eso_hos', role='head_of_studies')
        self.staff_employees[0].parent_id = other_head  # the organisation chart does not matter
        director = employee('test_erasmus_staff_director', role='director')
        self.staff_call.validator_ids |= director.user_id
        for person, can_apply in ((self.staff_employees[0], True), (head_of_studies, True), (director, True),
                                  (other_teacher, False), (administration, False), (other_head, False)):
            self.assertEqual(self.staff_call in person.user_id.partner_id._ems_erasmus_calls(), can_apply, person.name)

    def test_a_new_staff_call_is_for_every_fp_level_and_validated_by_the_fp_direction(self):
        """The Director and the Head of Studies above most of the FP teachers."""
        head_of_studies = create_role_employee(self, self.hos_user)
        self.staff_employees[0].parent_id = self.staff_employees[1].parent_id = head_of_studies
        self.staff_employees[2].parent_id = create_role_employee(self, create_role_user(
            self, 'head_of_studies', 'test_erasmus_minority_hos', name='Test Minority Head Of Studies'))
        director = create_role_employee(self, create_role_user(self, 'director', 'test_erasmus_new_director'))
        self.env.company.director_id = director
        Call = self.env['ems.erasmus.call']
        self.assertEqual(Call._ems_staff_validators(self.level), director.user_id | self.hos_user)
        call = Call.create({'name': 'New staff call', 'audience': 'staff', 'date_open': self.staff_call.date_open,
                            'date_close': self.staff_call.date_close})
        fp_levels = ('cfgb', 'cfgm', 'cfgs', 'efps', 'pfi')
        self.assertEqual(call.staff_level_ids, self.env['ems.level'].union(
            *(self.env.ref(f'ems.level_{level}') for level in fp_levels)))
        self.assertIn(director.user_id, call.validator_ids)

    def test_a_staff_call_has_no_minimum_score_and_gives_the_panel_two_weeks(self):
        call = self.env['ems.erasmus.call'].create({
            'name': 'Staff call defaults', 'audience': 'staff', 'date_open': self.staff_call.date_open,
            'date_close': self.staff_call.date_close})
        self.assertEqual(call.min_score, 0.0, "Its criteria add up to 10: a minimum would leave everyone out.")
        # Issue #767: the panel's deadline follows the same rule as a students' call's score correction.
        self.assertEqual(call.interview_deadline, call._ems_deadlines(call.date_close)['interview_deadline'])

    def test_staff_declare_their_last_mobility_and_seniority(self):
        """The 2026-11-03 review: the applicant only ticks that they never had one at the Puig; the
        team sets the last one of everyone else."""
        application = self._apply(0)
        self.assertEqual((application.declared_last_staff_mobility, application.declared_seniority), ('never', 'y5'))
        application.declared_never_staff_mobility = False
        self.assertFalse(application.declared_last_staff_mobility)
        self.assertFalse(application._ems_staff_last_mobility(), "Until the team sets it.")
        application.last_staff_mobility = 'recent'
        self.assertEqual(application._ems_staff_last_mobility(), 'recent')
        close = self.staff_call.date_close
        application.declared_centre_start_date = fields.Date.subtract(close.date(), months=1)
        self.assertEqual(application.declared_seniority, 'y0')
        application.declared_centre_start_date = fields.Date.subtract(close.date(), years=3)
        self.assertEqual(application.declared_seniority, 'y2')
        self.assertEqual(application.score_seniority, 1.5)
        application.seniority = 'y5'  # the team corrects it
        self.assertEqual(application.score_seniority, 2.0)

    def test_staff_must_declare_their_seniority_to_submit(self):
        partner = self.staff_users[1].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        application._ems_portal_save(STAFF_PLAN, {self.id_document.id: [('id.pdf', PDF)]})
        with self.assertRaises(UserError):
            application.action_submit()

    def test_staff_write_every_section_of_the_mobility_plan_to_submit(self):
        partner = self.staff_users[1].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        application._ems_portal_save({'declared_centre_start_date': '2015-09-01', **STAFF_PLAN, 'proposal_b': False},
                                     {self.id_document.id: [('id.pdf', PDF)]})
        with self.assertRaises(UserError, msg="Proposal B, the backup, is required too."):
            application.action_submit()
        application._ems_portal_save({'proposal_b': 'Test course', 'plan_text': False}, {})
        with self.assertRaises(UserError):
            application.action_submit()
        application._ems_portal_save({'plan_text': 'Test plan'}, {})
        application.action_submit()
        self.assertEqual(application.state, 'submitted')

    def test_students_call_modalities_need_levels(self):
        call = self.call.copy()
        call.modality_ids.level_ids = False
        with self.assertRaises(UserError):
            call.action_publish()


@tagged('post_install', '-at_install')
class TestErasmusPlanRating(ErasmusStaffCase):

    def _sent_to_panel(self):
        applications = self._admitted(0), self._admitted(1), self._admitted(2)
        self.staff_call.action_close()
        self.staff_call.with_user(self.erasmus_user).action_send_to_panel()
        return applications

    def test_the_call_opens_its_panel_ratings_and_the_panel_its_own_menu(self):
        """The issue-#682 review: the team opens a call's plan ratings from its form; a panel
        member gets "My plan ratings" only, never the interviewers' "My evaluations"."""
        first, *_rest = self._sent_to_panel()
        action = self.staff_call.with_user(self.erasmus_user).action_view_plan_ratings()
        self.assertEqual(self.env['ems.erasmus.plan_rating'].search(action['domain']),
                         self.staff_call.application_ids.plan_rating_ids)
        self.assertIn(first.plan_rating_ids[:1], self.env['ems.erasmus.plan_rating'].search(action['domain']))
        self.assertTrue(self.panel_teacher.has_group('ems.group_erasmus_panel'))
        self.assertFalse(self.panel_teacher.has_group('ems.group_erasmus_evaluator'))

    def test_every_panel_member_rates_every_plan_and_candidates_abstain(self):
        first, _second, third = self._sent_to_panel()
        ratings = first.sudo().plan_rating_ids
        self.assertEqual(ratings.panel_member_id, self.staff_call.panel_ids.user_id)
        candidate = ratings.filtered(lambda rating: rating.panel_member_id == self.staff_users[2])
        self.assertFalse(candidate.evaluator_id)
        self.assertTrue(candidate.abstention_reason)
        # Their own application is rated by the panel too, never by themselves.
        self.assertNotIn(self.staff_users[2], third.sudo().plan_rating_ids.evaluator_id)
        with self.assertRaises(UserError):
            self.staff_call.action_send_to_panel()  # nothing left to send
        with self.assertRaises(UserError):
            candidate.action_submit()
        with self.assertRaises(ValidationError):
            candidate.evaluator_id = self.staff_users[2]  # a candidate never rates
        with self.assertRaises(ValidationError):
            candidate.evaluator_id = self.panel_teacher  # no substitutes

    def test_the_panel_tasks_are_due_on_the_score_correction_deadline(self):
        first, _second, _third = self._sent_to_panel()
        activities = first.sudo().plan_rating_ids.activity_ids
        self.assertTrue(activities)
        self.assertEqual(set(activities.mapped('date_deadline')), {self._local_day(self.staff_call.interview_deadline)})
        self.staff_call.interview_deadline += timedelta(days=7)
        self.assertEqual(set(activities.mapped('date_deadline')), {self._local_day(self.staff_call.interview_deadline)},
                         "The open tasks follow the deadline.")

    def test_sending_to_the_panel_needs_the_score_correction_deadline(self):
        self._admitted(0)
        self.staff_call.action_close()
        self.staff_call.interview_deadline = False
        with self.assertRaises(UserError):
            self.staff_call.action_send_to_panel()

    def _local_day(self, value):
        return self.env['ems.datetime_utils'].utc_datetime_to_local(UTC.localize(value)).date()

    def test_an_abstention_does_not_count(self):
        first = self._sent_to_panel()[0]
        rating = first.sudo().plan_rating_ids.filtered(lambda rating: rating.panel_member_id == self.panel_teacher)
        rating.abstention_reason = 'Relative of the applicant'
        self.assertFalse(rating.evaluator_id)
        self._rate(first, '1', '0.5')
        self.assertTrue(first.plan_complete)  # only the Head of Studies rates: the other two abstain
        self.assertEqual(first.plan_score, 1.5)
        self.assertEqual(rating.rating_status, 'abstention', "Shown as an abstention, not as a plan to rate.")
        rating.abstention_reason = False
        self.assertEqual(rating.evaluator_id, self.panel_teacher)
        self.assertEqual(rating.rating_status, 'draft')
        self.assertFalse(first.plan_complete)

    def test_submit_and_open_the_next_plan_to_rate(self):
        self._sent_to_panel()
        mine = self.env['ems.erasmus.plan_rating'].with_user(self.panel_teacher).search(
            [('evaluator_id', '=', self.panel_teacher.id)])
        self.assertGreater(len(mine), 1)
        mine[0].write({'relevance': '1', 'transfer': '1'})
        action = mine[0].action_submit_next()
        self.assertEqual(mine[0].state, 'submitted')
        self.assertEqual(action['res_id'], mine[1].id, "The next plan opens.")
        for rating in mine[1:]:
            rating.write({'relevance': '1', 'transfer': '1'})
        mine[1:-1].action_submit()
        action = mine[-1].action_submit_next()
        self.assertEqual(action['res_model'], 'ems.erasmus.plan_rating')
        self.assertFalse(action.get('res_id'), "None left: back to the list.")

    def test_plan_score_is_the_mean_and_a_pending_rating_blocks(self):
        first = self._sent_to_panel()[0]
        self._complete(first)
        ratings = first.sudo().plan_rating_ids
        mine = ratings.filtered(lambda rating: rating.evaluator_id == self.panel_teacher)
        mine.with_user(self.panel_teacher).write({'relevance': '1', 'transfer': '0.5'})
        mine.with_user(self.panel_teacher).action_submit()
        self.assertFalse(first.plan_complete)
        self.assertFalse(first.score_complete)
        self.assertEqual(first.plan_score, 1.5)
        self._rate(first, '1', '1')
        self.assertTrue(first.plan_complete)
        self.assertEqual(first.plan_score, 1.75)  # the candidate in the panel abstains
        self.assertTrue(first.score_complete)

    def test_panel_member_sees_only_their_ratings_and_the_mobility_plan(self):
        first = self._sent_to_panel()[0]
        Rating = self.env['ems.erasmus.plan_rating'].with_user(self.panel_teacher)
        mine = Rating.search([])
        self.assertEqual(mine.evaluator_id, self.panel_teacher)
        self.assertEqual(len(mine), 3)
        rating = mine.filtered(lambda rating: rating.application_id == first)
        # The plan written in the form, and none of the application's documents.
        self.assertEqual((rating.plan_proposal_a, rating.plan_proposal_b, rating.plan_text), tuple(STAFF_PLAN.values()))
        self.assertFalse(rating.plan_attachment_ids)
        self.assertFalse(self.env['ems.erasmus.application.document'].with_user(self.panel_teacher).search([]))
        with self.assertRaises(AccessError):
            first.with_user(self.panel_teacher).read(['partner_id'])
        with self.assertRaises(AccessError):
            rating.write({'abstention_reason': 'Not mine to write'})
        rating.write({'relevance': '1', 'transfer': '1'})
        rating.action_submit()
        rating.action_reopen()

    def test_the_direction_sees_no_points_until_the_panel_has_rated_every_plan(self):
        """Who is not in the Erasmus team (the Head of Studies, the Director), panel member or not,
        reads the staff's points only once every plan of the call is rated: until then a member
        still to rate would see the others' mean (decided with the coordinator 2026-10-30)."""
        applications = self._sent_to_panel()
        for application in applications:
            self._complete(application)
        points = ['plan_score', 'score_plan', 'score_seniority', 'score_total']
        self._rate(applications[0], '1', '1')
        self.assertEqual(applications[0].with_user(self.erasmus_user).read(points)[0]['plan_score'], 2.0)
        hidden = applications[0].with_user(self.hos_user).read(points)[0]
        self.assertEqual([hidden[name] for name in points], [0.0] * 4, "Two plans still to rate.")
        searched = self.env['ems.erasmus.application'].with_user(self.hos_user).search_read(
            [('id', '=', applications[0].id)], points)[0]
        self.assertEqual([searched[name] for name in points], [0.0] * 4)
        for application in applications[1:]:
            self._rate(application, '1', '0.5')
        shown = applications[0].with_user(self.hos_user).read(points)[0]
        self.assertEqual([shown[name] for name in points], [2.0, 2.0, 2.0, 5.5])

    def test_staff_criteria_and_their_maximums(self):
        first = self._sent_to_panel()[0]
        self._rate(first, '1', '1')
        self._complete(first, last='two_courses', language='b1', seniority='y2',
                       merits=('project_coordination', 'project_coordination', 'internationalisation',
                               'internationalisation', 'internationalisation'))
        self.assertEqual((first.score_plan, first.score_last_mobility, first.score_projects,
                          first.score_staff_language, first.score_seniority, first.score_internationalisation),
                         (2.0, 0.5, 1.5, 0.0, 1.5, 1.0))
        self.assertEqual(first.score_total, 6.5)
        first.language_level = 'c1'
        self.assertEqual(first.score_staff_language, 1.5)
        first.merits_checked = False
        self.assertFalse(first.score_complete)

    def test_languages_score_the_declared_certificate_unless_the_team_corrects_it(self):
        first = self._sent_to_panel()[0]
        first.write({'declared_language_level': 'c1'})  # what the applicant declared on the portal
        self.assertEqual(first.score_staff_language, 1.5)
        first.language_level = 'b2'
        self.assertEqual(first.score_staff_language, 1.0)
        first.write({'language_level': False, 'declared_language_level': False})
        self._rate(first, '1', '1')
        first.write({'last_staff_mobility': 'never', 'seniority': 'y5', 'merits_checked': True})
        self.assertTrue(first.score_complete)  # no certificate declared: none, it never blocks
        self.assertEqual(first.score_staff_language, 0.0)

    def test_one_ranking_for_the_whole_call_with_the_staff_tie_breaks(self):
        """All three total 4.5: a tie is broken by the mobility plan, then by seniority."""
        first, second, third = self._sent_to_panel()
        self._rate(first, '1', '1')
        self._rate(second, '1', '1')
        self._rate(third, '1', '0.5')
        self._complete(first, last='two_courses', seniority='y1', language='b2')
        self._complete(second, last='two_courses', seniority='y2', merits=('project_collaboration',))
        self.assertFalse(first.rank)  # the third is not scored yet
        self._complete(third, last='older', seniority='y2')
        self.assertEqual({first.score_total, second.score_total, third.score_total}, {4.5})
        self.assertEqual((second.rank, first.rank, third.rank), (1, 2, 3))
        self.assertEqual([application._ems_ranking_result() for application in (second, first, third)],
                         ['selected', 'selected', 'reserve'])


@tagged('post_install', '-at_install')
class TestErasmusStaffResolution(ErasmusStaffCase):

    def _publish(self, kind):
        resolution = self.env['ems.erasmus.resolution'].with_user(self.erasmus_user).create({
            'call_id': self.staff_call.id, 'kind': kind})
        resolution.action_prepare()
        resolution.action_publish()
        return resolution

    def _definitive(self):
        applications = self._admitted(0), self._admitted(1), self._admitted(2)
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        for application, last, seniority in zip(applications, ('never', 'older', 'recent'), ('y5', 'y2', 'y5')):
            self._rate(application, '1', '1')
            self._complete(application, last=last, seniority=seniority)
        for kind in ('admission', 'provisional', 'definitive'):
            resolution = self._publish(kind)
        return applications, resolution

    def test_one_published_list_identified_by_the_employee_document(self):
        (first, second, third), resolution = self._definitive()
        groups = resolution._ems_list_groups()
        self.assertEqual(len(groups), 1)
        lines = {line.application_id: line for line in groups[0][1]}
        self.assertEqual(lines[first].public_id, '***1111**')
        self.assertEqual(lines[third].public_id, '****2222*')
        self.assertEqual(lines[first].score_last_mobility, 1.5)
        self.assertEqual((first.state, second.state, third.state), ('selected', 'selected', 'reserve'))
        self.assertFalse(first.offer_ids.modality_id)
        html = self.env['ir.actions.report']._render_qweb_html('ems.action_report_erasmus_resolution', resolution.ids)[0]
        self.assertNotIn(b'Erasmus Staff 1', html)

    def test_admitting_a_teacher_without_a_dni_warns_the_team(self):
        """The 2026-11-04 usage test: it was only found when preparing the lists, and only the
        Secretary fills it in."""
        self.staff_employees[0].identification_id = False
        application = self._apply(0)
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        result = application.action_admit()
        self.assertEqual(application.state, 'admitted')
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn('Erasmus Staff 1', result['params']['message'])
        second = self._apply(1)
        second.requirements_check = 'met'
        second.document_ids.filtered('attachment_ids').action_mark_valid()
        self.assertIsNone(second.action_admit(), "With a DNI, no warning.")

    def test_preparing_says_what_is_missing_of_each_score(self):
        """The 2026-11-04 usage test: "Complete the score of: X" did not say what."""
        application = self._admitted(0)
        self.staff_call.action_close()
        self._publish('admission')
        application.write({'merits_checked': False, 'seniority': False, 'declared_centre_start_date': False})
        resolution = self.env['ems.erasmus.resolution'].with_user(self.erasmus_user).create({
            'call_id': self.staff_call.id, 'kind': 'provisional'})
        with self.assertRaises(UserError) as error:
            resolution.action_prepare()
        labels = application.fields_get(['plan_complete', 'merits_checked', 'seniority'], ['string'])
        for name in ('plan_complete', 'merits_checked', 'seniority'):
            self.assertIn(labels[name]['string'], str(error.exception))

    def test_missing_employee_document_blocks_preparing(self):
        self._admitted(0)
        self.staff_call.action_close()
        self.staff_employees[0].identification_id = False
        resolution = self.env['ems.erasmus.resolution'].create({'call_id': self.staff_call.id, 'kind': 'admission'})
        with self.assertRaises(UserError):
            resolution.action_prepare()
        self.staff_employees[0].passport_id = 'PAA123456'
        resolution.action_prepare()

    def test_a_free_place_goes_to_the_next_reserve_of_the_whole_call(self):
        (first, _second, third), _resolution = self._definitive()
        self.assertEqual(self.staff_call.free_places, 0)
        first.offer_ids.action_renounce()
        self.assertEqual(self.staff_call.free_places, 1)
        self.assertEqual(self.staff_call.next_reserve_id, third)
        wizard = self.env['ems.erasmus.offer.wizard'].with_context(active_id=self.staff_call.id).create({
            'deadline': fields.Datetime.now() + timedelta(days=5)})
        self.assertEqual(wizard.application_id, third)
        wizard.action_confirm()
        self.assertEqual(third.offer_ids.state, 'pending')

    def test_export_staff_from_their_employee_file(self):
        (first, _second, _third), _resolution = self._definitive()
        first.offer_ids.action_accept()
        first.modality_id = self.staff_call.modality_ids[0]  # the team assigns the project and period
        self.staff_employees[0].write({'private_email': 'staff.private@example.com', 'birthday': '1980-05-04',
                                       'private_city': 'Test City'})
        sheet = openpyxl.load_workbook(io.BytesIO(
            first.with_user(self.erasmus_user)._ems_participants_xlsx())).active
        row = dict(zip([cell.value for cell in sheet[1]], [cell.value for cell in sheet[2]]))
        self.assertEqual(row['DNI'], '11111111H')
        self.assertEqual(row['Email'], 'staff.private@example.com')
        self.assertEqual(row['Dirección'], 'Test City')
        self.assertEqual(row['Fecha de nacimiento'].date(), fields.Date.to_date('1980-05-04'))
        for header in ('Género', 'Ciclo formativo', 'Curso', 'Tutor legal'):
            self.assertFalse(row[header])


@tagged('post_install', '-at_install')
class TestPortalErasmusStaff(HttpCase):
    """The 2026-11-04 review: the portal is for students and families; staff apply to a staff call
    in the backend (test_erasmus_staff_backend.py), and the portal's Erasmus+ pages send them there."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)

    def test_the_portal_sends_staff_to_the_backend(self):
        user = self.staff_users[0]
        self.authenticate(user.login, user.login)
        backend = '/odoo/action-ems.action_erasmus_staff_calls'
        for url in ('/my/erasmus', f'/my/erasmus/call/{self.staff_call.id}'):
            self.assertTrue(self.url_open(url).url.endswith(backend), url)
        self.url_open(f'/my/erasmus/call/{self.staff_call.id}/save', data={
            'csrf_token': Request.csrf_token(self), **STAFF_PLAN, 'submit': '1'})
        self.assertFalse(self.env['ems.erasmus.application'].search([('call_id', '=', self.staff_call.id)]),
                         "Refused: nothing saved.")

    def test_a_team_member_who_is_not_a_teacher_lands_on_the_calls(self):
        """The 2026-11-04 usage test: the roll call, every new account's home, gave them an access
        error. A home chosen on purpose is kept."""
        roll_call = self.env['ir.actions.actions'].browse(self.env.ref('ems.action_attendance_passlist').id)
        self.erasmus_user.action_id = roll_call
        self.assertFalse(self.erasmus_user.has_group('ems.group_teacher'))
        self.authenticate(self.erasmus_user.login, self.erasmus_user.login)
        home = self.make_jsonrpc_request('/web/session/get_session_info')['home_action_id']
        self.assertEqual(home, self.env.ref('ems.action_erasmus_call').id)
        self.authenticate(self.staff_users[0].login, self.staff_users[0].login)
        self.staff_users[0].action_id = roll_call
        self.assertEqual(self.make_jsonrpc_request('/web/session/get_session_info')['home_action_id'], roll_call.id,
                         "A teacher keeps the roll call.")

    def test_backend_user_menu_offers_the_staff_calls(self):
        """The issue-#682 review: the backend's session says who has a staff call to apply to or an
        application, for the user menu's "Erasmus+"."""
        self.authenticate(self.staff_users[0].login, self.staff_users[0].login)
        self.assertTrue(self.make_jsonrpc_request('/web/session/get_session_info')['ems_erasmus_staff'])
        self.authenticate(self.panel_teacher.login, self.panel_teacher.login)
        self.assertFalse(self.make_jsonrpc_request('/web/session/get_session_info')['ems_erasmus_staff'],
                         "No employee file that can apply, no application.")