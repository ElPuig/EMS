from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class EmsPortal(CustomerPortal):

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        values = self._prepare_portal_layout_values()
        
        user = request.env.user
        
        is_teacher = request.env['hr.employee'].sudo().search_count([
            ('user_id', '=', user.id),
            ('employee_type', '=', 'teacher') 
        ]) > 0

        values.update({
            'is_teacher': is_teacher,
            'partner': user.partner_id
        })
        
        return request.render("ems.portal_home_alumno", values)