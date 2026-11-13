# -*- coding: utf-8 -*-
"""Screenshots for the Erasmus+ team's manual (docs/{en,ca,es}/erasmus/, shots in
docs/assets/erasmus/). Same mechanism and same rules as `test_docs_screenshots.py`: tagged
'-standard' (never part of a normal run), every record made up inside the test's own rolled-back
transaction, PNGs written to /tmp/ems_doc_screenshots and copied into docs/assets/ by hand. Run it
with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsErasmus' --stop-after-init -c /etc/odoo/odoo.conf"
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_user, mock_outgoing_email
from .test_erasmus_group_mobility import create_group_mobility_fixtures
from .test_erasmus_staff import STAFF_PLAN, create_staff_call_fixtures
from .test_erasmus import PDF
from .test_portal_erasmus import create_portal_erasmus_fixtures

INFO_CARD = (
    '<div class="card border-primary"><div class="card-body">'
    '<h5 class="card-title">Mobilitats Erasmus+ 2026-2027</h5>'
    '<p class="card-text">Estades de pràctiques de 30 dies a empreses europees, per a l\'alumnat de '
    'segon curs de cicles formatius.</p></div></div>'
)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsErasmus(DocsScreenshotMixin, HttpCase):
    # The shot ends with the editor open, before saving.
    allow_end_on_form = True

    TECHNICIAN = 'doc_shot_erasmus_technician'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)
        cls.call.write({'name': 'Mobilitats de pràctiques 2026-2027', 'description': INFO_CARD})
        technician = create_role_user(cls, 'erasmus', cls.TECHNICIAN, lang='ca_ES', tz='Europe/Madrid', name='Laia Exemple')
        # The team's members are teachers too: the contact form needs it (see erasmus.md).
        technician.groups_id = [(4, cls.env.ref('ems.group_teacher').id)]
        cls.host = cls.env['res.partner'].create({
            'name': 'Musterschule Reutlingen', 'is_company': True, 'is_erasmus_host': True,
            'contact_type': 'provider', 'street': 'Beispielstrasse 1', 'city': 'Reutlingen', 'zip': '72764',
            'country_id': cls.env.ref('base.de').id, 'website': 'https://musterschule.example.com',
            'erasmus_oid': 'E00000000',
        })

    def test_capture_call_information(self):
        """Issue #774: the code view button in the call's Information for applicants."""
        field = '.o_field_widget[name=description]'
        button = f'{field} .o-we-toolbar button[name=codeview]'
        self._capture(f'/odoo/action-ems.action_erasmus_call/{self.call.id}', field,
                      'convocatoria-informacio-codi.png', login=self.TECHNICIAN,
                      wait_for='.o_notebook a.nav-link[name=description]',
                      click=['.o_notebook a.nav-link[name=description]', f'mouse:{field} .note-editable'],
                      wait_after=[f'{field} .note-editable .card', button],
                      marks=[(button, 1, 'left')])

    def test_capture_call_calendar(self):
        """Issue #767: the call's two blocks, Settings and Calendar, with the deadlines unfolded."""
        utils = self.env['ems.datetime_utils']
        close = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(fields.Date.to_date('2026-11-20'), 23.0))
        self.call.write({'date_open': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(
            fields.Date.to_date('2026-11-09'), 9.0)), 'date_close': close, **self.call._ems_deadlines(close)})
        summary = '.o_form_sheet details.o_ems_erasmus_call_deadlines > summary'
        self._capture(f'/odoo/action-ems.action_erasmus_call/{self.call.id}',
                      '.o_form_sheet .o_group:has(details.o_ems_erasmus_call_deadlines)',
                      'convocatoria-calendari.png', login=self.TECHNICIAN, wait_for=summary, click=[summary],
                      wait_after=['.o_form_sheet details.o_ems_erasmus_call_deadlines[open] [name=claims_deadline]'])

    def test_capture_host_entity(self):
        """Issue #777: the host entity's address, country, website and OID, for the Erasmus team."""
        self._capture(f'/odoo/res.partner/{self.host.id}', '.o_form_sheet', 'entitat-acollida-dades.png',
                      login=self.TECHNICIAN, wait_for='.o_field_widget[name=erasmus_oid]', max_height=540)

    def test_capture_support_rates(self):
        """Issue #778: the organisational support rates, no limit and any length left empty."""
        self._capture('/odoo/action-ems.action_erasmus_support_rate', '.o_list_renderer',
                      'tarifes-suport-organitzatiu.png', login=self.TECHNICIAN,
                      wait_for='.o_list_renderer .o_data_row', max_height=320)

    def test_capture_points_over_maximum(self):
        """Issue #779: a criterion's points over their maximum."""
        application = self.env['ems.erasmus.application'].create({
            'call_id': self.call.id, 'partner_id': self.student.id, 'modality_id': self.call.modality_ids.id,
            'fewer_opportunities_check': 'yes', 'first_mobility': 'yes', 'language_level': 'b2', 'state': 'admitted',
            'scoring_frozen_date': fields.Datetime.now()})
        tab = '.o_notebook a.nav-link[name=scoring]'
        self._capture(f'/odoo/action-ems.action_erasmus_application/{application.id}', '.o_notebook .tab-content',
                      'puntuacio-sobre-maxim.png', login=self.TECHNICIAN, wait_for=tab, click=[tab],
                      wait_after=['.o_field_widget[name=score_total]'], max_height=320)

    def test_capture_application_header(self):
        """Issue #784 (3.4, 3.11): what decides an application, on top, and its Application tab."""
        application = self.env['ems.erasmus.application'].create({
            'call_id': self.call.id, 'partner_id': self.student.id, 'modality_id': self.call.modality_ids.id,
            'fewer_opportunities_check': 'yes', 'first_mobility': 'yes', 'language_level': 'b2', 'state': 'admitted',
            'requirements_check': 'met', 'scoring_frozen_date': fields.Datetime.now()})
        self._capture(f'/odoo/action-ems.action_erasmus_application/{application.id}', '.o_form_sheet',
                      'sollicitud-capcalera.png', login=self.TECHNICIAN,
                      wait_for='.o_field_widget[name=requirements_check]', max_height=420)

    def test_capture_mobility_phases(self):
        """Issue #785 (5.5): the mobility's real phases, here during the stay."""
        today = self.env['ems.datetime_utils'].get_local_today()
        application = self.env['ems.erasmus.application'].create({
            'call_id': self.call.id, 'partner_id': self.student.id, 'modality_id': self.call.modality_ids.id,
            'state': 'accepted'})
        mobility = self.env['ems.erasmus.mobility'].create({
            'application_id': application.id, 'state': 'preparing', 'country_id': self.env.ref('base.de').id,
            'city': 'Reutlingen', 'host_partner_id': self.host.id, 'date_start': today - timedelta(days=10),
            'date_end': today + timedelta(days=20)})
        self.assertEqual(mobility.phase, 'stay')
        self._capture(f'/odoo/action-ems.action_erasmus_mobility/{mobility.id}', '.o_form_view .o_form_renderer',
                      'mobilitat-fases.png', login=self.TECHNICIAN,
                      wait_for=".o_statusbar_status button[data-value=stay].o_arrow_button_current", max_height=330)

    def test_capture_ranking_of_a_call(self):
        """Issue #781: a call's ranking, grouped by modality, the row with no colour."""
        self.call.state = 'closed'
        self.env['ems.erasmus.application'].create({
            'call_id': self.call.id, 'partner_id': self.student.id, 'modality_id': self.call.modality_ids.id,
            'fewer_opportunities_check': 'yes', 'first_mobility': 'yes', 'language_level': 'b2', 'state': 'admitted',
            'scoring_frozen_date': fields.Datetime.now()})
        ranking = 'button[name=action_view_ranking]'
        self._capture(f'/odoo/action-ems.action_erasmus_call/{self.call.id}', '.o_list_renderer',
                      'classificacio-convocatoria.png', login=self.TECHNICIAN, wait_for=ranking, click=[ranking],
                      wait_after=['.o_list_renderer .o_data_row'], max_height=220)


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsErasmusStaff(DocsScreenshotMixin, HttpCase):
    """The staff call's shots, on made-up teachers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)
        create_role_user(cls, 'erasmus', TestDocsScreenshotsErasmus.TECHNICIAN, lang='ca_ES', tz='Europe/Madrid',
                         name='Laia Exemple')

    def test_capture_plan_ratings(self):
        """Issue #781: one row per applicant, with how many rated and the mean."""
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.staff_call, self.staff_users[0].partner_id)
        application._ems_portal_save(
            {'declared_never_staff_mobility': True, 'declared_centre_start_date': '2015-09-01', **STAFF_PLAN},
            {self.id_document.id: [('id.pdf', PDF)]})
        application.action_submit()
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        rating = application.plan_rating_ids[:1]
        rating.write({'concreteness': '1', 'relevance': '1'})
        rating.sudo().with_user(rating.panel_member_id).action_submit()
        self._capture('/odoo/action-ems.action_erasmus_plan_rating', '.o_list_renderer',
                      'valoracions-per-sollicitant.png', login=TestDocsScreenshotsErasmus.TECHNICIAN,
                      wait_for='.o_list_renderer .o_group_header', max_height=180)

    def test_capture_staff_application_form(self):
        """Issue #824: the staff form, the mobility plan explained and what to learn inside each proposal."""
        teacher = self.staff_users[0]
        teacher.write({'lang': 'ca_ES', 'tz': 'Europe/Madrid'})
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.staff_call, teacher.partner_id)
        self._capture(f'/odoo/action-ems.action_erasmus_my_applications/{application.id}', '.modal-content',
                      'sollicitud-personal-formulari.png', login=teacher.login,
                      wait_for='.o_form_view button[name=action_staff_edit]',
                      click=['.o_form_view button[name=action_staff_edit]'], wait_after=['.modal .o_field_widget[name=proposal_a]'])

    def test_capture_plan_rubric(self):
        """Issue #824: criterion 1's rubric in the panel member's rating, as annex 2."""
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.staff_call, self.staff_users[0].partner_id)
        application._ems_portal_save(
            {'declared_never_staff_mobility': True, 'declared_centre_start_date': '2015-09-01',
             'proposal_a': "Un curs d'anglès en una acadèmia de Bolonya (Itàlia), al juliol, per millorar la meva "
                           "competència lingüística.",
             'proposal_b': "Job shadowing en un institut d'FP de Porto (Portugal), al juny, per veure com organitzen "
                           "la formació dual."},
            {self.id_document.id: [('id.pdf', PDF)]})
        application.action_submit()
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        rating = application.plan_rating_ids.filtered(lambda line: line.panel_member_id == self.panel_teacher)
        self.panel_teacher.write({'lang': 'ca_ES', 'tz': 'Europe/Madrid'})
        self.panel_teacher.partner_id.name = 'Laia Ferrer Mas'
        self.staff_users[0].partner_id.name = 'Marta Vidal Roig'
        self.staff_call.name = 'Mobilitats de personal 2026-27'
        self._capture(f'/odoo/action-ems.action_erasmus_my_plan_ratings/{rating.id}', '.o_form_sheet',
                      'valoracio-pla-rubrica.png', login=self.panel_teacher.login,
                      wait_for='.o_field_widget[name=concreteness]')

    def test_capture_places_per_project(self):
        """Issue #772: the staff call's places, split among the projects that pay them."""
        self.staff_vet_project.code, self.staff_hed_project.code = '2026-VET', '2026-HED'
        self.staff_call.project_place_ids.filtered(lambda line: line.project_id == self.staff_vet_project).places = 2
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(
            self.staff_call, self.staff_users[0].partner_id)
        application.write({'state': 'accepted'})
        self.env['ems.erasmus.mobility'].create({'application_id': application.id,
                                                 'project_id': self.staff_vet_project.id})
        field = '.o_field_widget[name=project_place_ids]'
        self._capture(f'/odoo/action-ems.action_erasmus_call/{self.staff_call.id}', field,
                      'convocatoria-personal-places-projecte.png', login=TestDocsScreenshotsErasmus.TECHNICIAN,
                      wait_for='.o_notebook a.nav-link[name=project_places]',
                      click=['.o_notebook a.nav-link[name=project_places]'], wait_after=[f'{field} .o_data_row'])



@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsErasmusGroup(DocsScreenshotMixin, HttpCase):
    """The group mobilities' shots, on made-up groups and students."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # Created by a coordinator whose language is English.
        create_group_mobility_fixtures(cls)
        technician = create_role_user(cls, 'erasmus', TestDocsScreenshotsErasmus.TECHNICIAN, lang='ca_ES',
                                      tz='Europe/Madrid', name='Laia Exemple')
        technician.groups_id = [(4, cls.env.ref('ems.group_teacher').id)]

    def test_capture_selection_criteria(self):
        """Issue #780: the default selection criteria, read in Catalan."""
        field = '.o_field_widget[name=tie_break]'
        self._capture(f'/odoo/action-ems.action_erasmus_group_mobility/{self.mobility.id}',
                      '.o_notebook .tab-content', 'mobilitat-grup-criteris.png', login=TestDocsScreenshotsErasmus.TECHNICIAN,
                      wait_for=field, max_height=260)

    def test_capture_selection_score(self):
        """Issue #773: the selection ranked by the score, next to the average."""
        Registration = self.env['ems.erasmus.group.registration']
        first = Registration._ems_portal_enrol(self.mobility, self.students[0], fewer_opportunities=True)
        for student in self.students[1:4]:
            Registration._ems_portal_enrol(self.mobility, student)
        self.env['ems.strike'].create({'student_id': self.students[1].id, 'teacher_id': self.other_teacher.id,
                                       'date': fields.Datetime.now() - timedelta(minutes=5)})
        averages = dict(zip(self.students[:4], (7.0, 8.4, 7.6, 6.9)))
        with patch.object(type(self.env['ems.erasmus.application']), '_ems_partner_grade_values',
                          side_effect=lambda partner, _course: [{'grade': averages[partner], 'hours': 100}]):
            self.mobility.with_user(self.coordinator_user).action_close_enrolment()
        first.fewer_opportunities_check = 'yes'
        field = '.o_field_widget[name=registration_ids]'
        self._capture(f'/odoo/action-ems.action_erasmus_group_mobility/{self.mobility.id}', field,
                      'mobilitat-grup-puntuacio.png', login=TestDocsScreenshotsErasmus.TECHNICIAN,
                      wait_for='.o_notebook a.nav-link[name=selection]',
                      click=['.o_notebook a.nav-link[name=selection]'], wait_after=[f'{field} .o_data_row'])
