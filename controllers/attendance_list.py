from odoo import http, fields
from odoo.http import request

class EmsTeacherController(http.Controller):

    @http.route('/teacher/attendance', type='http', auth='user', website=True)
    def teacher_attendance_home(self, **kw):
        user = request.env.user
        is_teacher = request.env['hr.employee'].search_count([('user_id', '=', user.id), ('employee_type', '=', 'teacher')]) > 0
        
        return request.render('ems.teacher_attendance_root', {
            'is_teacher': is_teacher,
            'user_name': user.name
        })

    
    @http.route('/ems/get_my_sessions', type='json', auth='user')
    def get_my_sessions(self):
        user = request.env.user
        employee = request.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

        domain = [
            ('session_teacher_id', '=', employee.id),
            ('date', '=', fields.Date.today()) 
        ]
        sessions = request.env['ems.attendance_session_header'].search(domain)

        return [{
            'id': s.id,
            'subject': s.subject_id.name,
            'group': s.group_id.name,
            'start_time': f"{int(s.start_time)}:00", # Formato simple
            'date': s.date
        } for s in sessions]
    
    @http.route('/ems/get_past_sessions', type='json', auth='user')
    def get_past_sessions(self):
        user = request.env.user
        employee = request.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        
        if not employee:
            return []

        domain = [
            ('session_teacher_id', '=', employee.id),
            ('date', '<', fields.Date.today())  
        ]
        
        sessions = request.env['ems.attendance_session_header'].search(domain, order='date desc', limit=20)
        
        return [{
            'id': s.id,
            'subject': s.subject_id.name,
            'group': s.group_id.name,
            'start_time': f"{int(s.start_time)}:00",
            'date': s.date 
        } for s in sessions]

    @http.route('/ems/get_session_students', type='json', auth='user')
    def get_session_students(self, session_id):
        session = request.env['ems.attendance_session_header'].browse(session_id)
        
        students_data = []
        for line in session.attendance_session_line_ids:
            students_data.append({
                'line_id': line.id,
                'student_id': line.student_id.id,
                'name': line.student_id.name,
                'status': line.status, 
            })
        
        return {
            'session_name': f"{session.subject_id.name} ({session.group_id.name})",
            'students': students_data,
            'date': session.date,
            'start_time': f"{int(session.start_time)}:00",
        }

    @http.route('/ems/submit_attendance_batch', type='json', auth='user')
    def submit_attendance_batch(self, changes):
        
        for change in changes:
            line = request.env['ems.attendance_session_line'].browse(change['line_id'])
            if line.status != change['status']:
                line.write({'status': change['status']})
        
        return True
        