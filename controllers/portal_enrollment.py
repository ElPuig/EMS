# -*- coding: utf-8 -*-
import base64
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from datetime import datetime
from markupsafe import Markup, escape
import logging
_logger = logging.getLogger(__name__)

class EMSPortalController(CustomerPortal):

    # -------------------------------------------------------------
    # (Gestión de Matrículas - ÚNICA FUNCIÓN PARA ESTA RUTA)
    # -------------------------------------------------------------
    @http.route(['/my/gestion-matriculas'], type='http', auth="user", website=True)
    def portal_my_enrollment(self, **kw):
        """ 
        Muestra el proceso de matrícula (Autorizaciones + Items) 
        al entrar en /my/gestion-matriculas
        """
        # 1. Preparamos valores base y contadores de Odoo
        values = self._prepare_portal_layout_values()
        home_values = self._prepare_home_portal_values(counters=['quotation', 'order', 'invoice'])
        values.update(home_values)

        # 2. Buscamos la matrícula activa del alumno
        current_course = request.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)
        if not current_course:
            current_course = request.env['ems.course'].search([('is_current', '=', True)], limit=1)
        partner = request.env.user.partner_id
        enrollment = request.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['sent', 'sale']),
            ('ems_course_id', '=', current_course.id if current_course else False),
        ], limit=1)     

        # Mensajes relevantes para el portal
        discussions_subtype = request.env.ref('mail.mt_comment')
        enrollment_messages = request.env['mail.message'].sudo().search([
            ('res_id', '=', enrollment.id),
            ('model', '=', 'sale.order'),
            ('message_type', '=', 'comment'),
            ('subtype_id', '=', discussions_subtype.id),
        ], order='date desc') if enrollment else []

        # 3. Actualizamos los valores para la vista
        message_sent = request.session.pop('ems_message_sent', None)
        payment_terms = request.env['account.payment.term'].sudo().search([
            ('ems_portal_visible', '=', True)
        ])
        values.update({
            'enrollment': enrollment,
            'page_name': 'gestion-matriculas', # Mantén este nombre para que el menú naranja funcione
            'message_sent': message_sent,
            'enrollment_messages': enrollment_messages,
            'payment_terms': payment_terms,
        })
        
        # 4. Renderizamos la plantilla en funcion del estado de la matricula
        if enrollment and enrollment.state == 'sale':
            return request.render("ems.portal_enrollment_confirmed", values)
        else:
            return request.render("ems.portal_enrollment_process", values)        

    @http.route(['/my/gestion-matriculas/authorize/<int:auth_id>'], type='http', auth="user", methods=['POST'], website=True)
    def portal_enrollment_authorize(self, auth_id, **post):
        """ Procesa la aceptación o rechazo de una autorización """
        auth = request.env['ems.authorization'].browse(auth_id)
        if not auth.exists() or auth.enrollment_id.partner_id != request.env.user.partner_id:
            _logger.warning(
                "Unauthorized authorization attempt: user %s tried to respond to auth_id %s",
                request.env.user.id, auth_id
            )
            return request.redirect('/my/gestion-matriculas')

        if auth.template_id.acceptance_only and post.get('decision') == 'no':
            _logger.warning(
                "Rejection attempt on acceptance-only authorization: user %s, auth_id %s",
                request.env.user.id, auth_id
            )
            return request.redirect('/my/gestion-matriculas')

        decision = post.get('decision')
        if decision in ('yes', 'no'):
            # Recoger y validar campos de datos de la plantilla
            field_responses = []
            for field in auth.template_id.field_ids:
                value = post.get('field_response_%d' % field.id, '').strip()[:500]
                if decision == 'yes' and field.is_required and not value:
                    _logger.warning(
                        "Missing required field '%s' for auth_id %s by user %s",
                        field.label, auth_id, request.env.user.id
                    )
                    return request.redirect('/my/gestion-matriculas?error=missing_required_fields')
                field_responses.append((field.id, value))

            auth.write({
                'status': decision,
                'response_date': datetime.now(),
                'response_uid': request.env.user.id,
            })

            # Guardar respuestas de campos (reemplaza las anteriores si ya existían)
            ResponseModel = request.env['ems.authorization.response'].sudo()
            auth.sudo().response_field_ids.unlink()
            for field_id, value in field_responses:
                if value:
                    ResponseModel.create({
                        'authorization_id': auth.id,
                        'field_id': field_id,
                        'value': value,
                    })

            # Generar certificado PDF y adjuntarlo como documento de la autorización
            try:
                    pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                        'ems.report_authorization_certificate', [auth.id]
                    )
                    auth.sudo().write({
                        'signed_document': base64.b64encode(pdf_content),
                        'signed_document_name': 'Cert_%s_%s.pdf' % (
                            auth.enrollment_id.name,
                            auth.template_id.name[:30],
                        ),
                    })
            except Exception:
                _logger.exception(
                    "Failed to generate authorization certificate for auth_id %s", auth_id
                )
        else:
            _logger.warning(
                "Invalid decision value '%s' received from user %s for auth_id %s",
                decision, request.env.user.id, auth_id
            )

        return request.redirect('/my/gestion-matriculas')

    @http.route(['/my/gestion-matriculas/confirm'], type='http', auth="user", methods=['POST'], website=True)
    def portal_enrollment_confirm(self, **post):
        """ Procesa la confirmación de la matrícula """

        partner = request.env.user.partner_id

        # 1. Recuperamos la matrícula activa
        current_course = request.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)
        if not current_course:
            current_course = request.env['ems.course'].search([('is_current', '=', True)], limit=1)

        enrollment = request.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['sent']),
            ('ems_course_id', '=', current_course.id if current_course else False),
        ], limit=1)

        if not enrollment:
            _logger.warning("Enrollment confirm: no active enrollment found for user %s", request.env.user.id)
            return request.redirect('/my/gestion-matriculas')

        # 2. Verificamos autorizaciones obligatorias pendientes
        pending_required = enrollment.ems_authorization_ids.filtered(
            lambda a: a.template_id.is_required and a.status == 'pending'
        )
        if pending_required:
            _logger.warning("Enrollment confirm: user %s has pending required authorizations", request.env.user.id)
            return request.redirect('/my/gestion-matriculas?error=pending_authorizations')
        if not enrollment.payment_term_id and not post.get('payment_term_id'):
            _logger.warning("Enrollment confirm: user %s has not selected a payment term", request.env.user.id)
            return request.redirect('/my/gestion-matriculas?error=missing_payment_term')        

        payment_term_id = post.get('payment_term_id')
        if payment_term_id:
            try:
                term = request.env['account.payment.term'].sudo().browse(int(payment_term_id))
                if term.exists() and term.ems_portal_visible:
                    enrollment.sudo().write({'payment_term_id': term.id})
                else:
                    _logger.warning(
                        "Enrollment confirm: payment_term_id %s not found or not portal-visible, user %s",
                        payment_term_id, request.env.user.id
                    )
                    return request.redirect('/my/gestion-matriculas?error=invalid_payment_term')
            except (ValueError, TypeError):
                _logger.warning(
                    "Enrollment confirm: invalid payment_term_id '%s' from user %s",
                    payment_term_id, request.env.user.id
                )
                return request.redirect('/my/gestion-matriculas?error=invalid_payment_term')

        # 3. Recogemos comentarios del POST
        comments = post.get('comments', '').strip()[:2000]
        if comments:
            # 4a. Hay comentarios: publicar en el chatter y mantener estado
            # Recuperamos los nombres de las líneas marcadas
            commented_line_ids = request.httprequest.form.getlist('commented_lines')
            line_names = []
            for line_id in commented_line_ids:
                try:
                    line = request.env['sale.order.line'].browse(int(line_id))
                    if line.exists() and line.order_id == enrollment:
                        line_names.append(line.name)
                except (ValueError, TypeError):
                    pass

            # Construimos el cuerpo del mensaje
            lines_html = Markup('')
            if line_names:
                items = Markup('').join(Markup('<li>%s</li>') % escape(name) for name in line_names)
                lines_html = Markup('<br/><b>Marked items:</b><ul>%s</ul>') % items

            enrollment.sudo().message_post(
                body=Markup('<b>Comments from student/family portal:</b><br/>%s%s') % (
                    escape(comments), lines_html
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            request.session['ems_message_sent'] = comments
        else:
            # 4b. Sin comentarios: confirmar la matrícula
            enrollment.sudo().action_confirm()
            enrollment.sudo().message_post(
                body=Markup('<b>Enrollment confirmed by student/family via portal.</b>'),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            _logger.info("Enrollment confirm: enrollment %s confirmed by user %s", 
                        enrollment.name, request.env.user.id)

        return request.redirect('/my/gestion-matriculas')

    @http.route(['/my/gestion-matriculas/authorization/<int:auth_id>/document'], 
                type='http', auth="user", website=True)
    def portal_authorization_document(self, auth_id, **kw):
        """ Sirve el documento firmado de una autorización """
        auth = request.env['ems.authorization'].sudo().browse(auth_id)
        if not auth.exists() or auth.enrollment_id.partner_id != request.env.user.partner_id:
            return request.redirect('/my/gestion-matriculas')
        if not auth.signed_document:
            return request.redirect('/my/gestion-matriculas')

        file_content = base64.b64decode(auth.signed_document)
        filename = auth.signed_document_name or 'document.pdf'
        return request.make_response(
            file_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'inline; filename="%s"' % filename),
            ]
        )

    # -------------------------------------------------------------
    # (Páginas en Construcción)
    # -------------------------------------------------------------
    @http.route([
        '/my/asistencia', 
        '/my/calificaciones', 
        '/my/documentacion'
    ], type='http', auth='user', website=True)
    def under_construction(self, **kwargs):
        # Le pasamos el nombre de la página para que la franja naranja del menú 
        # siga marcando el botón correcto aunque estemos en esta vista genérica
        values = self._prepare_portal_layout_values()
        
        # Renderizamos nuestra nueva vista de "En desarrollo"
        return request.render('ems.portal_under_construction_page', values)