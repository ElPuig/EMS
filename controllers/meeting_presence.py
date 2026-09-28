# -*- coding: utf-8 -*-

import json

from odoo import http
from odoo.http import request


class EmsMeetingPresenceController(http.Controller):
    """The kiosk of a meeting attendance (issue #521): a public page a laptop at the door keeps
    open, and the route it posts every tag to. The token in the URL is the only credential, the
    same shape as hr_attendance's kiosk; everything runs with sudo() and nothing is ever listed
    beyond the person who just passed the tag."""

    def _get_presence(self, token):
        if not token:
            return request.env['ems.meeting.presence']
        return request.env['ems.meeting.presence'].sudo().search([('access_token', '=', token)], limit=1)

    @http.route('/ems/meetings', type='http', auth='public', methods=['GET'])
    def meetings(self):
        """The meetings page (issue #526): a fixed address the computers with a reader keep open.
        It reads tags as a kiosk does, and each one gets the list of meetings its owner can open
        today, a link to each kiosk. No token: the tag is the credential, which is enough for
        pages that only register attendance."""
        presences = request.env['ems.meeting.presence'].sudo().with_context(
            lang=request.env.company.sudo().partner_id.lang or 'en_US')
        return request.render('ems.meeting_presence_hub', {
            'props': json.dumps({
                'labels': presences._ems_hub_labels(),
                'showCodeBox': presences._ems_show_code_box(),
            }),
        })

    @http.route('/ems/meetings/scan', type='json', auth='public', methods=['POST'])
    def meetings_scan(self, barcode=None):
        return request.env['ems.meeting.presence'].sudo()._ems_hub_scan(barcode)

    @http.route('/ems/presence/<string:token>', type='http', auth='public', methods=['GET'])
    def kiosk(self, token, back=None):
        """The page, whatever the state of the session: it says by itself whether it is open. An
        unknown token is a 404, same as any other. Opened from the meetings page (`back`), it offers
        the way back there."""
        presence = self._get_presence(token)
        if not presence:
            raise request.not_found()
        # Anonymous visitors have no language of their own (the public user is en_US here), so the
        # session says which one the kiosk speaks: its manager's, by default.
        presence = presence.with_context(lang=presence.kiosk_lang)
        return request.render('ems.meeting_presence_kiosk', {
            'props': json.dumps({
                'token': presence.access_token,
                'name': presence.name,
                'status': presence._ems_kiosk_status(),
                'windowLabel': presence._ems_window_label(),
                'showCodeBox': presence._ems_show_code_box(),
                'backUrl': '/ems/meetings' if back else '',
                'labels': presence._ems_kiosk_labels(),
                **presence._ems_kiosk_progress(),
            }),
        })

    @http.route('/ems/presence/<string:token>/status', type='json', auth='public', methods=['POST'])
    def status(self, token):
        """What the page polls: whether the session takes tags now (it can start, end, close or
        reopen while the page is up) and who is in so far."""
        presence = self._get_presence(token)
        if not presence:
            return {'status': 'invalid'}
        return {'status': presence._ems_kiosk_status(), **presence._ems_kiosk_progress()}

    @http.route('/ems/presence/<string:token>/scan', type='json', auth='public', methods=['POST'])
    def scan(self, token, barcode=None):
        presence = self._get_presence(token)
        if not presence:
            return {'status': 'invalid'}
        return presence._ems_register_scan(barcode)
