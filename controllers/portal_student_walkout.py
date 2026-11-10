# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import UserError
from odoo.http import request

WALKOUTS = '/my/vagues'


class EmsPortalStudentWalkoutController(CustomerPortal):
    """Issue #800: student walkout calls on the portal. The student is always the logged-in user's
    own partner (never a family acting for its child), and no partner id travels in a form. sudo
    because portal users have no ACL on these models; every check is in ems.student_walkout's
    _ems_portal_* methods. See docs/en/developers/attendance/student_walkout.md."""

    @staticmethod
    def _ems_partner():
        partner = request.env.user.partner_id
        return partner if partner._ems_walkout_portal_student() else None

    def _ems_walkout(self, walkout_id):
        """A call the logged-in student is in, or opened."""
        partner = self._ems_partner()
        if not partner:
            return None
        walkout = request.env['ems.student_walkout'].sudo().browse(walkout_id).exists()
        if walkout and (partner in walkout.line_ids.student_id or partner == walkout.opener_id):
            return walkout
        return None

    @staticmethod
    def _ems_error_redirect(page, error):
        request.session['ems_walkout_error'] = error.args[0] if error.args else ''
        return request.redirect(f'{page}?error=1')

    def _ems_render(self, template, values, **kwargs):
        page = self._prepare_portal_layout_values()
        page.update({
            'page_name': 'walkouts',
            'error_message': request.session.pop('ems_walkout_error', None) if kwargs.get('error') else None,
            **values,
        })
        return request.render(template, page)

    @http.route(WALKOUTS, type='http', auth='user', website=True)
    def portal_walkouts(self, **kwargs):
        partner = self._ems_partner()
        if not partner or not partner._ems_walkout_portal_visible():
            return request.redirect('/my/home')
        return self._ems_render('ems.portal_student_walkouts', {
            'partner': partner,
            'walkouts': partner._ems_walkout_calls(),
            'can_open': bool(partner._ems_walkout_opener_group()),
        }, **kwargs)

    @http.route(f'{WALKOUTS}/nova', type='http', auth='user', methods=['GET'], website=True)
    def portal_walkout_new(self, **kwargs):
        partner = self._ems_partner()
        group = partner and partner._ems_walkout_opener_group()
        if not group:
            return request.redirect(WALKOUTS)
        Walkout = request.env['ems.student_walkout'].sudo()
        notice = request.env.company.sudo().walkout_notice_days
        first_day = Walkout.get_local_today() + timedelta(days=notice)
        return self._ems_render('ems.portal_student_walkout_new', {
            'group': group,
            'notice_days': notice,
            'first_day': fields.Date.to_string(first_day),
            'tomorrow': fields.Date.to_string(Walkout.get_local_today() + timedelta(days=1)),
        }, **kwargs)

    @http.route(f'{WALKOUTS}/nova', type='http', auth='user', methods=['POST'], website=True)
    def portal_walkout_open(self, walkout_date=None, close_date=None, notes=None, **post):
        partner = self._ems_partner()
        if not partner:
            return request.redirect('/my/home')
        files = [(upload.filename, upload.read()) for upload in request.httprequest.files.getlist('union_call')
                 if upload.filename]
        Walkout = request.env['ems.student_walkout'].sudo()
        try:
            walkout_day = fields.Date.to_date(walkout_date) if walkout_date else None
            # The latest close day the notice period allows, unless the delegate picks an earlier one.
            if walkout_day and not close_date:
                close_date = walkout_day - timedelta(days=request.env.company.sudo().walkout_notice_days)
            walkout = Walkout._ems_portal_open(partner, {
                'walkout_date': walkout_day, 'close_date': close_date, 'notes': notes}, files)
        except (UserError, ValueError) as error:
            return self._ems_error_redirect(f'{WALKOUTS}/nova', error)
        return request.redirect(f'{WALKOUTS}/{walkout.id}?opened=1')

    @http.route(f'{WALKOUTS}/<int:walkout_id>', type='http', auth='user', website=True)
    def portal_walkout(self, walkout_id, **kwargs):
        walkout = self._ems_walkout(walkout_id)
        if not walkout:
            return request.redirect(WALKOUTS)
        partner = self._ems_partner()
        line = walkout.line_ids.filtered(lambda line: line.student_id == partner)
        return self._ems_render('ems.portal_student_walkout', {
            'walkout': walkout,
            'line': line,
            'can_vote': bool(line.has_portal) and walkout._ems_voting_open(),
            'can_manage': walkout.state == 'voting' and (
                partner == walkout.opener_id or partner in (walkout.group_ids.delegate_id
                                                            | walkout.group_ids.subdelegate_id)),
            'state_labels': dict(walkout._fields['state']._description_selection(request.env)),
            'opened': kwargs.get('opened'),
            'saved': kwargs.get('saved'),
        }, **kwargs)

    @http.route(f'{WALKOUTS}/<int:walkout_id>/<string:step>', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_walkout_step(self, walkout_id, step, **post):
        """Vote, close the vote now or cancel the call."""
        walkout = self._ems_walkout(walkout_id)
        if not walkout:
            return request.redirect(WALKOUTS)
        partner = self._ems_partner()
        page = f'{WALKOUTS}/{walkout.id}'
        try:
            if step == 'vota':
                walkout._ems_portal_vote(partner, post.get('group_vote'), post.get('joins') == 'yes')
            elif step == 'tanca':
                walkout._ems_portal_close(partner)
            elif step == 'anulla':
                walkout._ems_portal_cancel(partner)
                return request.redirect(WALKOUTS)
            else:
                return request.redirect(page)
        except UserError as error:
            return self._ems_error_redirect(page, error)
        return request.redirect(f'{page}?saved=1')

    @http.route(f'{WALKOUTS}/<int:walkout_id>/fitxer/<int:attachment_id>', type='http', auth='user', website=True)
    def portal_walkout_file(self, walkout_id, attachment_id, **kwargs):
        """The union's call, or the minute once the vote is closed."""
        walkout = self._ems_walkout(walkout_id)
        attachment = walkout and (walkout.attachment_ids | walkout.pdf_attachment_id).filtered(
            lambda attachment: attachment.id == attachment_id)
        if not attachment:
            return request.redirect(WALKOUTS)
        return request.env['ir.binary']._get_stream_from(attachment).get_response(as_attachment=True)
