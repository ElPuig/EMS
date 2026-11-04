# -*- coding: utf-8 -*-

import threading
import time
from collections import defaultdict, deque

from odoo import http
from odoo.http import request

# Failed checks (unknown or no longer valid codes) an address may make in a window before every
# check from it is refused. Valid checks are never counted: a teacher scanning a whole queue at the
# door must never be stopped, while someone trying codes one after the other is. Kept per worker
# process, which is enough against guessing: a code has 192 random bits.
MAX_FAILED_CHECKS = 20
FAILED_CHECKS_WINDOW = 600


class EmsStudentCardController(http.Controller):
    """The public check page of a student card (issue #524): the QR on the back of the card opens
    it. No login: the code is the only credential, and the page shows the least needed to compare
    it with the card in hand. See docs/en/developers/contacts/student_card.md."""

    _failed_checks = defaultdict(deque)
    _failed_checks_lock = threading.Lock()

    @classmethod
    def _too_many_failed_checks(cls, address, failed=False):
        """Whether `address` already used up its failed checks; `failed` records one more."""
        now = time.monotonic()
        with cls._failed_checks_lock:
            attempts = cls._failed_checks[address]
            while attempts and now - attempts[0] > FAILED_CHECKS_WINDOW:
                attempts.popleft()
            if failed:
                attempts.append(now)
            if not attempts:
                del cls._failed_checks[address]
            return len(attempts) >= MAX_FAILED_CHECKS

    @http.route('/ems/card/<string:token>', type='http', auth='public', methods=['GET'], sitemap=False)
    def check(self, token):
        address = request.httprequest.remote_addr
        # The card's language (Catalan), whoever scans it: an anonymous visitor has none of their own.
        request.update_context(lang=request.env['ems.minute'].sudo()._ems_centre_lang())
        if self._too_many_failed_checks(address):
            response = request.render('ems.student_card_check', {
                'state': 'blocked', 'company': request.env.company.sudo()})
            response.status_code = 429
        else:
            student = request.env['res.partner']._ems_card_from_token(token)
            if not student:
                self._too_many_failed_checks(address, failed=True)
            utils = request.env['ems.datetime_utils'].sudo()
            response = request.render('ems.student_card_check', {
                'state': 'valid' if student else 'invalid',
                'card': student._ems_card_check_values() if student else {},
                'checked_at': utils.get_local_datetime().strftime('%d/%m/%Y %H:%M:%S'),
                'company': request.env.company.sudo(),
            })
        # Neither search engines nor any cache keep it: it is only ever true at the moment it is read.
        response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
