# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from .portal_view_only import ems_portal_is_view_only
import logging
_logger = logging.getLogger(__name__)

class EMSPortalCommsController(CustomerPortal):

    @http.route(['/my/comunicaciones', '/my/comunicaciones/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_communications(self, page=1, **kw):
        """ Historial de comunicaciones del alumno """
        partner = request.env.user.partner_id
        students = partner.get_portal_students()
        partner = partner.get_portal_student()

        MESSAGES_PER_PAGE = 10

        # Buscamos los IDs de las matrículas/pedidos del alumno
        sale_order_ids = partner.get_portal_enrollment_ids()

        # IDs de los documentos del alumno
        document_ids = request.env['ems.student.document'].sudo().search([
            ('partner_id', '=', partner.id)
        ]).ids

        # IDs de las solicitudes de convalidación del alumno (issue #276)
        convalidation_ids = request.env['ems.convalidation'].sudo().search([
            ('student_id', '=', partner.id)
        ]).ids

        # Dominio combinado: mensajes dirigidos al partner, del chatter de matrícula, de documentos
        # o de convalidaciones. Excluimos notas internas (mail.mt_note) para que no sean visibles en el portal
        note_subtype = request.env.ref('mail.mt_note')
        # Whoever only consults (a minor on his own account, a family looking at its adult
        # child) only sees what is addressed to the student: the enrollment, document and
        # convalidation threads are the conversation of whoever acts for him with the centre
        # (res.partner._ems_portal_is_view_only).
        if ems_portal_is_view_only():
            origin = [('partner_ids', 'in', [partner.id])]
        else:
            origin = [
                '|', '|', '|',
                    ('partner_ids', 'in', [partner.id]),
                    '&', ('model', '=', 'sale.order'), ('res_id', 'in', sale_order_ids),
                    '&', ('model', '=', 'ems.student.document'), ('res_id', 'in', document_ids),
                    '&', ('model', '=', 'ems.convalidation'), ('res_id', 'in', convalidation_ids),
            ]
        domain = origin + [
            ('message_type', 'in', ['email', 'comment', 'notification']),
            ('subtype_id', '!=', note_subtype.id),
        ]

        # Total para la paginación
        total = request.env['mail.message'].sudo().search_count(domain)

        # Paginador estándar de Odoo
        pager = portal_pager(
            url='/my/comunicaciones',
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