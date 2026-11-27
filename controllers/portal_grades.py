# -*- coding: utf-8 -*-

from odoo import _, http
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EmsPortalGradesController(CustomerPortal):
    """Issue #878 (#271) - the student's published grades on the portal. Always the student
    resolved by get_portal_student() (the student themself, or a family's selected child, view-only
    included): no student id travels in the URL, so nobody can ask for another student's grades.
    The grades are read through sudo() in res.partner._ems_portal_grade_rounds(), scoped to it."""

    @http.route('/my/calificaciones', type='http', auth='user', website=True)
    def portal_grades(self, **kwargs):
        student = request.env.user.partner_id._ems_portal_student_sudo()
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'grades',
            'student': student,
            'rounds': student._ems_portal_grade_rounds() if student else [],
        })
        return request.render('ems.portal_grades', values)

    @http.route('/my/calificaciones/pdf', type='http', auth='user', website=True)
    def portal_grades_pdf(self, **kwargs):
        """Non-official, rendered on request and never stored."""
        student = request.env.user.partner_id._ems_portal_student_sudo()
        if not student:
            return request.redirect('/my/calificaciones')
        content, _content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.report_student_grades', student.ids)
        return request.make_response(content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition(f"{_('Grades')} - {student.name}.pdf")),
        ])
