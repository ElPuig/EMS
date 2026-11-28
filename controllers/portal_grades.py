# -*- coding: utf-8 -*-

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EmsPortalGradesController(CustomerPortal):
    """Issue #878 (#271) - the student's published grades on the portal; issue #879 - the grade
    claims filed from it. Always the student resolved by get_portal_student() (the student
    themself, or a family's selected child, view-only included): no student id travels in the URL,
    so nobody can ask for another student's grades. The grades are read through sudo() in
    res.partner._ems_portal_grade_rounds(), scoped to it; who may claim follows the convalidations'
    rule (res.partner._ems_can_file_requests_for)."""

    _grades_url = '/my/calificaciones'

    @http.route('/my/calificaciones', type='http', auth='user', website=True)
    def portal_grades(self, **kwargs):
        partner = request.env.user.partner_id
        student = partner._ems_portal_student_sudo()
        Claim = request.env['ems.grade_claim']
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'grades',
            'student': student,
            'rounds': student._ems_portal_grade_rounds() if student else [],
            'claimable': Claim._ems_claimable_items(student, partner) if student else [],
            'can_claim': bool(student) and partner._ems_can_file_requests_for(student),
            'claims': Claim.sudo().search([('student_id', '=', student.id)]) if student else Claim.browse(),
            'today': request.env['ems.datetime_utils'].get_local_today(),
            'claim_done': 'claimed' if kwargs.get('claimed') else ('escalated' if kwargs.get('escalated') else False),
            'claim_error': kwargs.get('error'),
        })
        return request.render('ems.portal_grades', values)

    @http.route('/my/calificaciones/reclamar', type='http', auth='user', methods=['POST'], website=True)
    def portal_grade_claim(self, item=None, reason=None, **post):
        partner = request.env.user.partner_id
        student = partner._ems_portal_student_sudo()
        try:
            request.env['ems.grade_claim'].ems_file_from_portal(student, partner, item, reason)
        except (UserError, AccessError):
            # Only a stale page gets here (the form offers what may be claimed and requires the
            # explanation): a code, not the message, in the URL.
            return request.redirect(f'{self._grades_url}?error=claim#claims')
        return request.redirect(f'{self._grades_url}?claimed=1#claims')

    @http.route('/my/calificaciones/reclamar/<int:claim_id>/tutor', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_grade_claim_escalate(self, claim_id, reason=None, **post):
        partner = request.env.user.partner_id
        student = partner._ems_portal_student_sudo()
        claim = request.env['ems.grade_claim'].sudo().browse(claim_id).exists()
        if not claim or claim.student_id != student:
            return request.redirect(self._grades_url)
        try:
            claim.ems_escalate_from_portal(partner, reason)
        except (UserError, AccessError):
            return request.redirect(f'{self._grades_url}?error=escalate#claims')
        return request.redirect(f'{self._grades_url}?escalated=1#claims')

    @http.route('/my/calificaciones/pdf', type='http', auth='user', website=True)
    def portal_grades_pdf(self, **kwargs):
        """Non-official, rendered on request and never stored."""
        student = request.env.user.partner_id._ems_portal_student_sudo()
        if not student:
            return request.redirect(self._grades_url)
        content, _content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.report_student_grades', student.ids)
        return request.make_response(content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition(f"{_('Grades')} - {student.name}.pdf")),
        ])
