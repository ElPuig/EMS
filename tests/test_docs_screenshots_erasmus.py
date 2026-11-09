# -*- coding: utf-8 -*-
"""Screenshots for the Erasmus+ team's manual (docs/{en,ca,es}/erasmus/, shots in
docs/assets/erasmus/). Same mechanism and same rules as `test_docs_screenshots.py`: tagged
'-standard' (never part of a normal run), every record made up inside the test's own rolled-back
transaction, PNGs written to /tmp/ems_doc_screenshots and copied into docs/assets/ by hand. Run it
with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsErasmus' --stop-after-init -c /etc/odoo/odoo.conf"
"""

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_user, mock_outgoing_email
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
        rating.write({'relevance': '1', 'transfer': '1'})
        rating.sudo().with_user(rating.panel_member_id).action_submit()
        self._capture('/odoo/action-ems.action_erasmus_plan_rating', '.o_list_renderer',
                      'valoracions-per-sollicitant.png', login=TestDocsScreenshotsErasmus.TECHNICIAN,
                      wait_for='.o_list_renderer .o_group_header', max_height=180)

