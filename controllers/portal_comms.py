# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import logging
_logger = logging.getLogger(__name__)

class EMSPortalCommsController(CustomerPortal):

    @http.route(['/my/comunicaciones', '/my/comunicaciones/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_communications(self, page=1, student_id=None, **kw):
        """ Historial de comunicaciones del alumno """
        partner = request.env.user.partner_id
        students = partner.get_portal_students()
        effective_id = int(student_id) if student_id else request.session.get('ems_student_id')
        partner = partner.get_portal_student(student_id=effective_id)
        student_id = partner.id if len(students) > 1 else None
        if len(students) > 1:
            request.session['ems_student_id'] = partner.id

        MESSAGES_PER_PAGE = 10

        # Buscamos los IDs de las matrículas/pedidos del alumno
        sale_order_ids = partner.get_portal_enrollment_ids()

        # Dominio combinado: mensajes dirigidos al partner O mensajes del chatter de sus documentos
        # Excluimos notas internas (mail.mt_note) para que no sean visibles en el portal
        note_subtype = request.env.ref('mail.mt_note')
        domain = [
            '|',
                ('partner_ids', 'in', partner.id),
                '&',
                    ('model', '=', 'sale.order'),
                    ('res_id', 'in', sale_order_ids),
            ('message_type', 'in', ['email', 'comment', 'notification']),
            ('subtype_id', '!=', note_subtype.id),
        ]

        # Total para la paginación
        total = request.env['mail.message'].sudo().search_count(domain)

        # Paginador estándar de Odoo
        pager = portal_pager(
            url='/my/comunicaciones',
            url_args={'student_id': student_id} if student_id else {},
            total=total,
            page=page,
            step=MESSAGES_PER_PAGE,
        )

        # Mensajes de la página actual
        communications = request.env['mail.message'].sudo().search(
            domain,
            order='date desc',
            limit=MESSAGES_PER_PAGE,
            offset=pager['offset'],
        )

        values = self._prepare_portal_layout_values()
        values.update({
            'communications': communications,
            'pager': pager,
            'total_communications': total,
            'page_name': 'comunicaciones',
            'student': partner,
            'students': students,
            'viewing_as_family': partner != request.env.user.partner_id,
            'inner_circle_ids': partner.get_portal_inner_circle_ids(),
        })
        return request.render('ems.portal_communications', values)