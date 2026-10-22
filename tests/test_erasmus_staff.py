import io
from datetime import timedelta

import openpyxl

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import Request
from odoo.tests.common import HttpCase, TransactionCase, tagged

from .common import create_role_employee, create_role_user, mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures, upload


def create_staff_call_fixtures(cls):
    """create_erasmus_fixtures() (a students' call, its team and Head of Studies) plus a
    published staff call: two modalities of one place each, an identity document, a mobility
    plan shown to the panel and an optional certificate; a panel of the Head of Studies and two
    teachers; three teachers with an employee file who can apply, the third one also in the panel."""
    create_erasmus_fixtures(cls)
    now = fields.Datetime.now()
    cls.panel_teacher = create_role_user(cls, 'teacher', 'test_erasmus_panel_teacher')
    cls.staff_users = [create_role_user(cls, 'teacher', f'test_erasmus_staff_{index}', name=f'Erasmus Staff {index}',
                                        email=f'erasmus.staff{index}@example.com') for index in (1, 2, 3)]
    cls.staff_employees = [create_role_employee(cls, user, identification_id=document)
                           for user, document in zip(cls.staff_users, ('11111111H', '22222222J', 'Y2222222E'))]
    cls.staff_call = cls.env['ems.erasmus.call'].create({
        'name': 'Test Erasmus Staff Call',
        'audience': 'staff',
        'min_score': 0.0,
        'date_open': now - timedelta(days=1),
        'date_close': now + timedelta(days=10),
        'acceptance_deadline': now + timedelta(days=20),
        'modality_ids': [(0, 0, {'name': 'TGM April', 'project': 'ka121_vet', 'places': 1, 'sequence': 1}),
                         (0, 0, {'name': 'TGS June', 'project': 'ka131_hed', 'places': 1, 'sequence': 2})],
        'document_ids': [
            (0, 0, {'name': 'Identity document', 'requirement': 'required', 'sequence': 1}),
            (0, 0, {'name': 'Mobility plan', 'requirement': 'required', 'panel_visible': True, 'sequence': 2}),
            (0, 0, {'name': 'Staff language certificate', 'requirement': 'optional', 'sequence': 3}),
        ],
        'panel_ids': [(0, 0, {'user_id': user.id, 'post': post}) for user, post in (
            (cls.hos_user, 'Head of Studies'), (cls.panel_teacher, 'Head of department'),
            (cls.staff_users[2], 'Seminar chief'))],
    })
    cls.staff_call.action_publish()
    cls.id_document, cls.plan_document, cls.staff_certificate = cls.staff_call.document_ids.sorted('sequence')


class ErasmusStaffCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)
        cls.substitute = create_role_user(cls, 'teacher', 'test_erasmus_substitute')

    def _apply(self, index, **answers):
        partner = self.staff_users[index].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        application._ems_portal_save(answers, {self.id_document.id: [('id.pdf', PDF)],
                                               self.plan_document.id: [('plan.pdf', PDF)]})
        application.action_submit()
        return application

    def _admitted(self, index):
        application = self._apply(index)
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        return application

    def _rate(self, application, relevance, transfer):
        """Every rating of `application` scored and submitted (a substitute for the abstentions)."""
        for rating in application.sudo().plan_rating_ids.filtered(lambda rating: rating.state == 'draft'):
            if not rating.evaluator_id:
                rating.write({'evaluator_id': self.substitute.id})
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
                                  accompany_students=True, availability='Ignored: a students\' answer')
        self.assertEqual(application.employee_id, self.staff_employees[0])
        self.assertFalse(application.modality_id)
        self.assertFalse(application.is_minor)
        self.assertEqual((application.staff_activity, application.host_entity), ('job_shadowing', 'Test host'))
        self.assertTrue(application.accompany_students)
        self.assertFalse(application.availability)
        with self.assertRaises(UserError):
            application._ems_portal_save({'staff_activity': 'holidays'}, {})
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
            candidate.evaluator_id = self.staff_users[1]  # another candidate
        candidate.evaluator_id = self.substitute
        self.assertIn(self.env.ref('ems.group_erasmus_evaluator'), self.substitute.groups_id)

    def test_a_substitute_needs_the_abstention_reason(self):
        first = self._sent_to_panel()[0]
        rating = first.sudo().plan_rating_ids.filtered(lambda rating: rating.panel_member_id == self.panel_teacher)
        with self.assertRaises(ValidationError):
            rating.evaluator_id = self.substitute
        rating.write({'evaluator_id': self.substitute.id, 'abstention_reason': 'Relative of the applicant'})

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
        self.assertEqual(first.plan_score, round((1.5 + 2 + 2) / 3, 2))
        self.assertTrue(first.score_complete)

    def test_panel_member_sees_only_their_ratings_and_the_mobility_plan(self):
        first = self._sent_to_panel()[0]
        Rating = self.env['ems.erasmus.plan_rating'].with_user(self.panel_teacher)
        mine = Rating.search([])
        self.assertEqual(mine.evaluator_id, self.panel_teacher)
        self.assertEqual(len(mine), 3)
        rating = mine.filtered(lambda rating: rating.application_id == first)
        self.assertEqual(rating.plan_attachment_ids.mapped('name'), ['plan.pdf'])
        rating.plan_attachment_ids.read(['name', 'datas'])
        lines = self.env['ems.erasmus.application.document'].with_user(self.panel_teacher).search([])
        self.assertEqual(lines.call_document_id, self.plan_document)
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

    def test_one_ranking_for_the_whole_call_with_the_staff_tie_breaks(self):
        first, second, third = self._sent_to_panel()
        for application in (first, second, third):
            self._rate(application, '1', '0.5')
        self._complete(first, last='older')
        self._complete(second, last='never')
        self.assertFalse(first.rank)  # the third is not scored yet
        self._complete(third, last='recent')
        self.assertEqual((second.rank, first.rank, third.rank), (1, 2, 3))
        self.assertEqual([application._ems_ranking_result() for application in (second, first, third)],
                         ['selected', 'selected', 'reserve'])


@tagged('post_install', '-at_install')
class TestErasmusStaffResolution(ErasmusStaffCase):

    def _publish(self, kind):
        resolution = self.env['ems.erasmus.resolution'].with_user(self.erasmus_user).create({
            'call_id': self.staff_call.id, 'kind': kind, 'approval_date': fields.Date.today(),
            'approval_reference': 'Minutes 1'})
        resolution.action_prepare()
        resolution.action_publish()
        return resolution

    def _definitive(self):
        applications = self._admitted(0), self._admitted(1), self._admitted(2)
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        for application, last in zip(applications, ('never', 'older', 'recent')):
            self._rate(application, '1', '1')
            self._complete(application, last=last)
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
            'csrf_token': Request.csrf_token(self), 'staff_activity': 'course', 'host_entity': 'Test course',
            'destination': 'Test city, Test country', 'support_needs': 'Test need', 'submit': '1',
        }, files=[(f'document_{self.id_document.id}', ('id.pdf', PDF, 'application/pdf')),
                  (f'document_{self.plan_document.id}', ('plan.pdf', PDF, 'application/pdf'))])
        self.assertTrue(response.url.endswith('/my/erasmus?submitted=1'))
        application = self.env['ems.erasmus.application'].search([('call_id', '=', self.staff_call.id)])
        self.assertEqual(application.state, 'submitted')
        self.assertEqual(application.employee_id, self.staff_employees[0])
        self.assertEqual((application.staff_activity, application.support_needs), ('course', 'Test need'))
