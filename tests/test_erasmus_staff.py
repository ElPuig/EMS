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
STAFF_PLAN = {'staff_activity': 'job_shadowing', 'host_entity': 'Test host school', 'destination': 'Test city',
              'preferred_dates': 'June', 'plan_reason': 'Test reason', 'plan_objectives': 'Test objectives',
              'plan_application': 'Test application'}


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
        self.assertTrue(staff._ems_erasmus_portal_visible())
        self.assertNotIn(self.staff_call, self.student._ems_erasmus_calls())
        self.assertFalse(self.panel_teacher.partner_id._ems_erasmus_calls())  # no employee file

    def test_staff_apply_once_without_a_modality(self):
        application = self._apply(0, staff_activity='job_shadowing', host_entity='Test host',
                                  availability='Ignored: a students\' answer')
        self.assertEqual(application.employee_id, self.staff_employees[0])
        self.assertFalse(application.modality_id)
        self.assertFalse(application.is_minor)
        self.assertEqual((application.staff_activity, application.host_entity), ('job_shadowing', 'Test host'))
        self.assertFalse(application.availability)
        with self.assertRaises(UserError):
            application._ems_portal_save({'staff_activity': 'holidays'}, {})
        with self.assertRaises(UserError):
            application._ems_portal_save({'declared_language_level': 'b1'}, {})
        with self.assertRaises(UserError):
            self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, self.student)

    def test_staff_is_admitted_without_the_sanction_check(self):
        application = self._admitted(0)
        self.assertEqual(application.state, 'admitted')
        self.assertEqual(application.sanction_check, 'pending')

    def test_a_call_with_applications_keeps_its_audience(self):
        self._apply(0)
        with self.assertRaises(UserError):
            self.staff_call.audience = 'student'

    def test_a_staff_call_opens_without_places_and_with_the_call_documents(self):
        call = self.env['ems.erasmus.call'].create({
            'name': 'Staff call without places', 'audience': 'staff', 'date_open': self.staff_call.date_open,
            'date_close': self.staff_call.date_close})
        self.assertEqual(len(call.document_ids), 3)
        self.assertEqual(call.modality_ids.mapped('project'), ['ka121_vet', 'ka131_hed'],
                         "One modality per project, without a period.")
        self.assertFalse(call.document_ids.filtered('panel_visible'), "The mobility plan is written in the form.")
        call.action_publish()
        self.assertEqual(call.state, 'published')

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
        self.assertEqual(call.interview_deadline, call.date_close + timedelta(days=14))
        call.date_close += timedelta(days=3)
        self.assertEqual(call.interview_deadline, call.date_close + timedelta(days=14), "It follows the closing date.")
        changed = call.date_close + timedelta(days=20)
        call.interview_deadline = changed
        call.date_close += timedelta(days=1)
        self.assertEqual(call.interview_deadline, changed, "Unless it was changed by hand.")

    def test_staff_declare_their_last_mobility_and_seniority(self):
        application = self._apply(0)
        self.assertEqual((application.declared_last_staff_mobility, application.declared_seniority), ('never', 'y5'))
        start = self.staff_call.course_id.start
        for day, band in ((f'{start}-10-01', 'recent'), (f'{start}-03-01', 'recent'),
                          (f'{start - 2}-11-01', 'two_courses'), (f'{start - 2}-06-01', 'older')):
            application.write({'declared_never_staff_mobility': False, 'declared_last_mobility_date': day})
            self.assertEqual(application.declared_last_staff_mobility, band, day)
        close = self.staff_call.date_close
        application.declared_centre_start_date = fields.Date.subtract(close.date(), months=1)
        self.assertEqual(application.declared_seniority, 'y0')
        application.declared_centre_start_date = fields.Date.subtract(close.date(), years=3)
        self.assertEqual(application.declared_seniority, 'y2')
        self.assertEqual(application.score_seniority, 1.5)
        application.seniority = 'y5'  # the team corrects it
        self.assertEqual(application.score_seniority, 2.0)

    def test_staff_must_declare_last_mobility_and_seniority_to_submit(self):
        partner = self.staff_users[1].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        application._ems_portal_save(STAFF_PLAN, {self.id_document.id: [('id.pdf', PDF)]})
        with self.assertRaises(UserError):
            application.action_submit()

    def test_staff_write_every_section_of_the_mobility_plan_to_submit(self):
        partner = self.staff_users[1].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        application._ems_portal_save({'declared_never_staff_mobility': True, 'declared_centre_start_date': '2015-09-01',
                                      **STAFF_PLAN, 'host_entity': False}, {self.id_document.id: [('id.pdf', PDF)]})
        with self.assertRaises(UserError, msg="Always with a concrete host entity or course."):
            application.action_submit()
        application._ems_portal_save({'host_entity': 'Test course provider', 'plan_objectives': False}, {})
        with self.assertRaises(UserError):
            application.action_submit()
        application._ems_portal_save({'plan_objectives': 'Test objectives'}, {})
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
        rating.abstention_reason = False
        self.assertEqual(rating.evaluator_id, self.panel_teacher)
        self.assertFalse(first.plan_complete)

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
        self.assertEqual((rating.plan_activity, rating.plan_host, rating.plan_destination, rating.plan_dates,
                          rating.plan_reason, rating.plan_objectives, rating.plan_application), tuple(STAFF_PLAN.values()))
        self.assertFalse(rating.plan_attachment_ids)
        self.assertFalse(self.env['ems.erasmus.application.document'].with_user(self.panel_teacher).search([]))
        with self.assertRaises(AccessError):
            first.with_user(self.panel_teacher).read(['partner_id'])
        with self.assertRaises(AccessError):
            rating.write({'abstention_reason': 'Not mine to write'})
        rating.write({'relevance': '1', 'transfer': '1'})
        rating.action_submit()
        rating.action_reopen()

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
    """Issue #686 - a teacher applies to the staff call from /my/erasmus."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)

    def test_teacher_applies_from_the_portal(self):
        user = self.staff_users[0]
        self.authenticate(user.login, user.login)
        page = self.url_open('/my/erasmus')
        self.assertIn(b'Test Erasmus Staff Call', page.content)
        self.assertNotIn(b'<strong>Test Erasmus Call</strong>', page.content)
        url = f'/my/erasmus/call/{self.staff_call.id}'
        self.assertIn(b'o_ems_erasmus_staff_form', self.url_open(url).content)
        response = self.url_open(f'{url}/save', data={
            'csrf_token': Request.csrf_token(self), **STAFF_PLAN, 'staff_activity': 'course', 'host_entity': 'Test course',
            'destination': 'Test city, Test country', 'support_needs': 'Test need', 'declared_language_level': 'c2',
            'declared_last_mobility_date': '2024-03', 'declared_centre_start_date': '2015-09', 'submit': '1',
        }, files=[(f'document_{self.id_document.id}', ('id.pdf', PDF, 'application/pdf'))])
        self.assertTrue(response.url.endswith('/my/erasmus?submitted=1'))
        application = self.env['ems.erasmus.application'].search([('call_id', '=', self.staff_call.id)])
        self.assertEqual(application.state, 'submitted')
        self.assertEqual(application.employee_id, self.staff_employees[0])
        self.assertEqual((application.staff_activity, application.support_needs, application.declared_language_level),
                         ('course', 'Test need', 'c2'))
        self.assertEqual(str(application.declared_last_mobility_date), '2024-03-01')
