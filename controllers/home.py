from odoo import http
from odoo.http import request

class EmsStudentController(http.Controller):

    @http.route('/ems/get_student_info', type='json', auth='user')
    def get_student_info(self):
        partner = request.env.user.partner_id
        
        return {
            'id': partner.id,
            'name': partner.name,
            'email': partner.email or 'Sin email',
            'phone': partner.phone or partner.mobile or 'Sin teléfono',
            'vat': partner.vat or '', 
            'street': partner.street or '',
            'city': partner.city or '',
            'car_plate': partner.car_plate,
            'level_id': partner.level_id.id,
            'study_id': partner.study_id.id,
            'group_id': partner.main_group_id.id,
        }

    @http.route('/ems/update_student_car_plate', type='json', auth='user')
    def update_student_car_plate(self, car_plate):
        partner = request.env.user.partner_id
        
        partner.write({'car_plate': car_plate})
        
        return True 

    @http.route('/portal/wizard/submit', type='json', auth='user', methods=['POST'])
    def portal_wizard_submit(self, **kwargs):
        partner_id = int(kwargs.get('student_id'))
        level_id = int(kwargs.get('level_id'))
        study_id = int(kwargs.get('study_id'))
        group_id = int(kwargs.get('group_id'))

        wizard = request.env['ems.attendance_report_student_wizard'].sudo().create({
            'student_id': partner_id,
            'level_id': level_id,
            'study_id': study_id,
            'group_id': group_id,
            'from_date': '2025-11-01', # Hardcoded, idea is to send from component too
            'to_date': '2026-11-30'
        })
        
        custom_url = f'/portal/download/attendance_report/{wizard.id}'

        return {
            'status': 'ok', 
            'message': 'Generando PDF...',
            'url': custom_url 
        }

    @http.route('/portal/download/attendance_report/<int:wizard_id>', type='http', auth='user')
    def download_attendance_report(self, wizard_id, **kw):
        wizard = request.env['ems.attendance_report_student_wizard'].sudo().browse(wizard_id)
        
        if not wizard.exists():
            return request.not_found()

        action_data = wizard.print()
        
        datas = action_data.get('data')

        report_xml_id = 'ems.action_attendance_report_student'
        pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            report_xml_id, 
            [], 
            data=datas  
        )

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'attachment; filename="Attendance_Report.pdf"')
        ]
        
        return request.make_response(pdf_content, headers=pdfhttpheaders)


