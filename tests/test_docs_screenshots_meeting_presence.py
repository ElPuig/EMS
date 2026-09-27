# -*- coding: utf-8 -*-
"""Screenshots of the meeting attendance screens (issue #521) for the secretariat and Head of
Studies manual (docs/{en,ca,es}/secretary/meeting-attendance.md). Same mechanism and same rules as
`test_docs_screenshots.py`: tagged '-standard' (never part of a normal run), fixtures made up inside
the test's own rolled-back transaction so no real person can appear, PNGs written to
/tmp/ems_doc_screenshots and copied into docs/assets/secretary/ by hand. Run it with:

    sudo -u odoo bash -c "odoo -d ems -u ems --test-enable --test-tags='*/ems:TestDocsScreenshotsMeetingPresence' --stop-after-init -c /etc/odoo/odoo.conf"
"""

import json

from odoo.tests.common import HttpCase, tagged

from .common import DocsScreenshotMixin, create_role_employee, create_role_user, mock_outgoing_email


@tagged('-standard', 'ems_screenshots', 'post_install', '-at_install')
class TestDocsScreenshotsMeetingPresence(DocsScreenshotMixin, HttpCase):
    BROWSER_TIMEZONE = 'Europe/Madrid'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # The manual describes the real kiosk, which has no box to type a code in.
        cls.env['ir.config_parameter'].sudo().set_param('ems.environment_type', 'production')
        # Catalan: the manuals are read at this centre in Catalan first.
        cls.secretary = create_role_user(cls, 'secretary', 'doc_shot_presence_secretary', lang='ca_ES',
                                         tz='Europe/Madrid', name='Secretaria', email='secretaria@example.com')
        create_role_employee(cls, cls.secretary, employee_type='asp', name='0000 Secretaria')

        # Invented people, on an invented meeting: these end up in a published manual.
        Employee = cls.env['hr.employee']
        cls.teachers = Employee
        names = ('Marina Exemple', 'Pau Mostra', 'Nerea Prova', 'Jordi Exemple', 'Laia Mostra', 'Arnau Prova',
                 'Berta Exemple', 'Oriol Mostra', 'Carla Prova', 'Biel Exemple', 'Núria Exemple', 'Àlex Prova')
        for index, name in enumerate(names, 1):
            cls.teachers |= Employee.create({
                'name': name, 'employee_type': 'teacher', 'barcode': f'DOCSHOT{index:03d}',
            })
        Presence = cls.env['ems.meeting.presence']

        def _session(name, **vals):
            return Presence.create({
                'name': name, 'scope': 'manual', 'kiosk_lang': 'ca_ES',
                'line_ids': [(0, 0, {'employee_id': teacher.id}) for teacher in cls.teachers], **vals,
            })

        cls.presence = _session('Claustre de professorat')
        cls.presence.action_open()
        for barcode in ('DOCSHOT001', 'DOCSHOT005', 'DOCSHOT006', 'DOCSHOT007'):
            cls.presence._ems_register_scan(barcode)
        cls.presence.line_ids.filtered(lambda line: line.employee_id.name == 'Pau Mostra').write({
            'state': 'justified', 'notes': 'Visita mèdica',
        })
        cls.closed = _session('Reunió de departament d\'Informàtica')
        cls.closed.action_open()
        cls.closed._ems_register_scan('DOCSHOT001')
        cls.closed._ems_register_scan('DOCSHOT002')
        cls.closed.action_close()
        cls.draft = _session('Sessió de formació')

        # An action of its own, scoped to these fixtures: it is what guarantees no real record can
        # appear in the shot, rather than trusting a crop.
        cls.list_action = cls.env['ir.actions.act_window'].create({
            'name': 'Assistència',
            'res_model': 'ems.meeting.presence',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (cls.presence | cls.closed | cls.draft).ids)],
        })

    # The kiosk fills the screen it runs on; in a manual it is only the card that matters.
    COMPACT_KIOSK_JS = ("(function () { document.querySelector('.o_ems_presence_kiosk').style.height = '440px';"
                        " document.querySelector('.o_ems_presence_window').textContent = '17:00 - 19:00';"
                        " window.dispatchEvent(new Event('resize')); })();")

    # Shown in the manual instead of this server's own address.
    LINK_PLACEHOLDER = 'https://ems.example.org/ems/presence/Xk3f9...'

    def test_capture_meeting_presence_screens(self):
        action = self.list_action.id
        login = 'doc_shot_presence_secretary'
        self._capture(f'/odoo/action-{action}', '.o_list_view', 'meeting-presence-list.png', login=login)
        # Draft: what the secretariat fills in before the meeting.
        self._capture(f'/odoo/action-{action}/{self.draft.id}', '.o_form_view', 'meeting-presence-new.png',
                      login=login, wait_for='.o_field_widget[name=line_ids] .o_data_row',
                      run="document.querySelector('.o-mail-Form-chatter').style.display = 'none'",
                      wait_after='.o_form_view',
                      marks=[('label[for^=name]', 1, 'left'), ('.o_field_widget[name=duration]', 2, 'right'),
                             ('label[for^=scope]', 3, 'left'), ('label[for^=kiosk_lang]', 4, 'left'),
                             ('.o_field_widget[name=line_ids] .o_data_row:first-child .o_data_cell:first-child', 5, 'left')])
        # Open: the day of the meeting.
        self._capture(f'/odoo/action-{action}/{self.presence.id}', '.o_form_view', 'meeting-presence-form.png',
                      login=login, wait_for='.o_field_widget[name=line_ids] .o_data_row',
                      run="(function () { document.querySelector('.o-mail-Form-chatter').style.display = 'none';"
                          " document.querySelector('.o_field_widget[name=kiosk_url] a').textContent = %s; })()"
                          % json.dumps(self.LINK_PLACEHOLDER),
                      wait_after='.o_form_view',
                      marks=[('.o_field_widget[name=kiosk_url]', 1, 'top'),
                             ('.o_field_widget[name=line_ids] .o_data_row:first-child .o_data_cell:first-child', 2, 'left')])
        # The kiosk after passing a convened person's tag. The times shown are made up to sit inside
        # the window shown, whatever the moment the screenshot is taken at.
        self._capture(f'/ems/presence/{self.presence.access_token}', '.o_ems_presence_kiosk',
                      'meeting-presence-kiosk-ok.png', wait_for='.o_ems_presence_prompt',
                      run=[self.COMPACT_KIOSK_JS + "(function () { 'DOCSHOT003'.split('').concat('Enter').forEach(function (key) {"
                           " document.body.dispatchEvent(new KeyboardEvent('keydown', {key: key, bubbles: true})); }); })()",
                           "(function () { var times = ['17:12', '17:10', '17:09', '17:08', '17:06'];"
                           " document.querySelectorAll('.o_ems_presence_time').forEach(function (el, i) {"
                           " el.textContent = times[i]; }); })()"],
                      wait_after=['.o_ems_presence_card_success', '.o_ems_presence_time'])
