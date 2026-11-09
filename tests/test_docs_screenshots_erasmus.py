# -*- coding: utf-8 -*-
"""Screenshots for the Erasmus+ team's manual (docs/{en,ca,es}/erasmus/, shots in
docs/assets/erasmus/). Same mechanism and same rules as `test_docs_screenshots.py`: tagged
'-standard' (never part of a normal run), every record made up inside the test's own rolled-back
transaction, PNGs written to /tmp/ems_doc_screenshots and copied into docs/assets/ by hand. Run it
with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsErasmus' --stop-after-init -c /etc/odoo/odoo.conf"
"""

from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_user, mock_outgoing_email
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

    def test_capture_host_entity(self):
        """Issue #777: the host entity's address, country, website and OID, for the Erasmus team."""
        self._capture(f'/odoo/res.partner/{self.host.id}', '.o_form_sheet', 'entitat-acollida-dades.png',
                      login=self.TECHNICIAN, wait_for='.o_field_widget[name=erasmus_oid]', max_height=540)

    def test_capture_support_rates(self):
        """Issue #778: the organisational support rates, no limit and any length left empty."""
        self._capture('/odoo/action-ems.action_erasmus_support_rate', '.o_list_renderer',
                      'tarifes-suport-organitzatiu.png', login=self.TECHNICIAN,
                      wait_for='.o_list_renderer .o_data_row', max_height=320)
