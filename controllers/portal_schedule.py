# -*- coding: utf-8 -*-

from odoo import _, http
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EmsPortalScheduleController(CustomerPortal):
    """Issue #453 - the student's weekly schedule on the portal's Attendance card. Always the
    student resolved by get_portal_student() (the student themself, or a family's selected child):
    no student id travels in the URL, so nobody can ask for another student's schedule. sudo because
    portal users have no ACL on resource.calendar* - see docs/en/developers/contacts/student_schedule.md."""

    def _get_portal_schedule_student(self):
        student = request.env.user.partner_id.get_portal_student().sudo()
        return student if student.contact_type == 'student' else student.browse()

    @http.route('/my/asistencia', type='http', auth='user', website=True)
    def portal_schedule(self, **kwargs):
        student = self._get_portal_schedule_student()
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'schedule',
            'student': student,
            'lines': student.get_schedule_report_lines() if student else [],
            'summary': student.get_subject_teachers_summary() if student else [],
        })
        return request.render('ems.portal_schedule', values)

    @http.route('/my/asistencia/pdf', type='http', auth='user', website=True)
    def portal_schedule_pdf(self, **kwargs):
        """Rendered on request, never stored: private, per student and low volume (unlike the
        group's public link, see ems.group._generate_public_schedule)."""
        student = self._get_portal_schedule_student()
        if not student:
            return request.redirect('/my/asistencia')
        content, _content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.report_student_schedule', student.ids)
        return request.make_response(content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition(f"{_('Schedule')} - {student.name}.pdf")),
        ])
