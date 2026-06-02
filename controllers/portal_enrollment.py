# -*- coding: utf-8 -*-
import base64
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape
import logging
_logger = logging.getLogger(__name__)

class EMSPortalController(CustomerPortal):

    # -------------------------------------------------------------
    # Selección de alumno activo (tutores con varios hijos)
    # -------------------------------------------------------------
    @http.route('/my/select-student/<int:student_id>', type='http', auth='user', methods=['POST'], website=True)
    def select_student(self, student_id, **post):
        partner = request.env.user.partner_id
        students = partner.get_portal_students()
        match = students.filtered(lambda s: s.id == student_id)
        if match:
            partner.sudo().write({'selected_student_id': match[0].id})
        next_url = post.get('next', '/my/home')
        if not next_url.startswith('/my/'):
            next_url = '/my/home'
        return request.redirect(next_url)

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
        students = partner.get_portal_students()
        student = partner.get_portal_student()
        enrollment = student.get_portal_enrollment(current_course)

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
        ]).filtered(
            lambda t: not t.ems_requires_fees or (enrollment and enrollment.ems_has_fees)
        )

        # IBAN del alumno: buscamos el documento aprobado más reciente
        # Umbral de validez: 30/09 del año de inicio del curso (última fecha de cobro)
        course_year = current_course.start if current_course else date.today().year
        iban_threshold = date(course_year, 9, 30)
        iban_doc = request.env['ems.student.document'].sudo().search([
            ('partner_id', '=', student.id),
            ('doc_type', '=', 'iban'),
            ('status', '=', 'approved'),
        ], order='upload_date desc', limit=1)
        iban_valid = bool(iban_doc) and (not iban_doc.expiry_date or iban_doc.expiry_date >= iban_threshold)
        iban_expired = bool(iban_doc) and bool(iban_doc.expiry_date) and iban_doc.expiry_date < iban_threshold

        values.update({
            'enrollment': enrollment,
            'page_name': 'gestion-matriculas',
            'message_sent': message_sent,
            'enrollment_messages': enrollment_messages,
            'payment_terms': payment_terms,
            'viewing_as_family': student != partner,
            'student': student,
            'students': students,
            'inner_circle_ids': student.get_portal_inner_circle_ids() if student else [],
            'iban_doc': iban_doc,
            'iban_valid': iban_valid,
            'iban_expired': iban_expired,
        })
        
        # 4. Renderizamos la plantilla en funcion del estado de la matricula
        if enrollment and enrollment.state == 'sale':
            return request.render("ems.portal_enrollment_confirmed", values)
        else:
            return request.render("ems.portal_enrollment_process", values)        

    @http.route(['/my/gestion-matriculas/authorize/<int:auth_id>'], type='http', auth="user", methods=['POST'], website=True)
    def portal_enrollment_authorize(self, auth_id, **post):
        """ Procesa la aceptación o rechazo de una autorización """
        redirect_base = '/my/gestion-matriculas'
        auth = request.env['ems.authorization'].sudo().browse(auth_id)
        student = request.env.user.partner_id.get_portal_student()
        if not auth.exists() or auth.enrollment_id.partner_id != student:
            _logger.warning(
                "Unauthorized authorization attempt: user %s tried to respond to auth_id %s",
                request.env.user.id, auth_id
            )
            return request.redirect(redirect_base)

        if auth.template_id.acceptance_only and post.get('decision') == 'no':
            _logger.warning(
                "Rejection attempt on acceptance-only authorization: user %s, auth_id %s",
                request.env.user.id, auth_id
            )
            return request.redirect(redirect_base)

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

        return request.redirect(redirect_base)

    @http.route(['/my/gestion-matriculas/confirm'], type='http', auth="user", methods=['POST'], website=True)
    def portal_enrollment_confirm(self, **post):
        """ Procesa la confirmación de la matrícula """
        redirect_base = '/my/gestion-matriculas'
        student = request.env.user.partner_id.get_portal_student()

        # 1. Recuperamos la matrícula activa
        current_course = request.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)
        if not current_course:
            current_course = request.env['ems.course'].search([('is_current', '=', True)], limit=1)

        enrollment = student.get_portal_enrollment(current_course)

        if not enrollment:
            _logger.warning("Enrollment confirm: no active enrollment found for user %s", request.env.user.id)
            return request.redirect(redirect_base)

        # 2. Determinar acción: 'comment' o 'confirm'
        action = post.get('action', 'confirm')
        comments = post.get('comments', '').strip()[:2000]
        if action == 'comment':
            # 3a. Hay comentarios: publicar en el chatter y mantener estado
            # (sin validar auths pendientes ni método de pago)
            commented_line_ids = request.httprequest.form.getlist('commented_lines')
            line_names = []
            for line_id in commented_line_ids:
                try:
                    line = enrollment.order_line.filtered(lambda l: l.id == int(line_id))
                    if line:
                        line_names.append(line[0].name)
                except (ValueError, TypeError):
                    pass

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
            # 3b. Confirmar matrícula: validar auths + plan de pago + método de pago
            pending_required = enrollment.ems_authorization_ids.filtered(
                lambda a: a.template_id.is_required and a.status == 'pending'
            )
            if pending_required:
                _logger.warning("Enrollment confirm: user %s has pending required authorizations", request.env.user.id)
                return request.redirect(redirect_base + '?error=pending_authorizations')

            if not enrollment.payment_term_id and not post.get('payment_term_id'):
                _logger.warning("Enrollment confirm: user %s has not selected a payment term", request.env.user.id)
                return request.redirect(redirect_base + '?error=missing_payment_term')

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
                        return request.redirect(redirect_base + '?error=invalid_payment_term')
                except (ValueError, TypeError):
                    _logger.warning(
                        "Enrollment confirm: invalid payment_term_id '%s' from user %s",
                        payment_term_id, request.env.user.id
                    )
                    return request.redirect(redirect_base + '?error=invalid_payment_term')

            # Validar método de pago
            payment_method = post.get('payment_method', '').strip()
            if payment_method not in ('transfer', 'direct_debit'):
                _logger.warning("Enrollment confirm: user %s has not selected a payment method", request.env.user.id)
                return request.redirect(redirect_base + '?error=missing_payment_method')

            if payment_method == 'direct_debit':
                course_year = current_course.start if current_course else date.today().year
                iban_threshold = date(course_year, 9, 30)
                iban_doc = request.env['ems.student.document'].sudo().search([
                    ('partner_id', '=', student.id),
                    ('doc_type', '=', 'iban'),
                    ('status', '=', 'approved'),
                ], order='upload_date desc', limit=1)
                iban_valid = bool(iban_doc) and (not iban_doc.expiry_date or iban_doc.expiry_date >= iban_threshold)
                iban_expired = bool(iban_doc) and bool(iban_doc.expiry_date) and iban_doc.expiry_date < iban_threshold

                if iban_expired and post.get('confirm_expired_iban'):
                    new_expiry = today.replace(year=today.year + 1, month=5, day=31)
                    iban_doc.sudo().write({'expiry_date': new_expiry})
                    author_name = escape(request.env.user.partner_id.name)
                    iban_doc.sudo().message_post(
                        body=Markup('<b>IBAN renewed by %s via portal.</b> New expiry: %s') % (
                            author_name, new_expiry.strftime('%d/%m/%Y')
                        ),
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                    )
                    _logger.info("Enrollment confirm: IBAN doc %s renewed to %s by user %s", iban_doc.id, new_expiry, request.env.user.id)
                elif not iban_valid:
                    _logger.warning("Enrollment confirm: user %s has no valid IBAN for direct debit", request.env.user.id)
                    return request.redirect(redirect_base + '?error=missing_valid_iban')

            enrollment.sudo().write({'ems_payment_method': payment_method})
            enrollment.sudo().action_confirm()
            enrollment.sudo().message_post(
                body=Markup('<b>Enrollment confirmed by %s via portal.</b>') % escape(request.env.user.partner_id.name),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            _logger.info("Enrollment confirm: enrollment %s confirmed by user %s",
                        enrollment.name, request.env.user.id)

        return request.redirect(redirect_base)

    @http.route(['/my/gestion-matriculas/authorization/<int:auth_id>/document'],
                type='http', auth="user", website=True)
    def portal_authorization_document(self, auth_id, **kw):
        """ Sirve el documento firmado de una autorización """
        auth = request.env['ems.authorization'].sudo().browse(auth_id)
        student = request.env.user.partner_id.get_portal_student()
        if not auth.exists() or auth.enrollment_id.partner_id != student:
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
    @http.route(['/my/asistencia', '/my/calificaciones'], type='http', auth='user', website=True)
    def under_construction(self, **kwargs):
        values = self._prepare_portal_layout_values()
        return request.render('ems.portal_under_construction_page', values)

    # -------------------------------------------------------------
    # Documentació de l'alumne
    # -------------------------------------------------------------
    @http.route('/my/documentacion', type='http', auth='user', website=True)
    def portal_documentation(self, **kwargs):
        partner = request.env.user.partner_id
        students = partner.get_portal_students()
        student = partner.get_portal_student()

        submissions = request.env['ems.student.document'].sudo().search([
            ('partner_id', '=', student.id)
        ])
        benefit_type_selection = request.env['ems.student.benefit'].fields_get(['benefit_type'])['benefit_type']['selection']
        student_benefits = request.env['ems.student.benefit'].sudo().search([
            ('student_id', '=', student.id)
        ])
        bank = student.bank_ids.filtered(lambda b: b.active)[:1]

        values = self._prepare_portal_layout_values()
        values.update({
            'student': student,
            'students': students,
            'viewing_as_family': student != partner,
            'submissions': submissions,
            'current_bank': bank,
            'benefit_types': benefit_type_selection,
            'student_benefits': student_benefits,
            'page_name': 'documentation',
            'error': kwargs.get('error'),
        })
        return request.render('ems.portal_documentation', values)

    @http.route('/my/documentacion/submit', type='http', auth='user', methods=['POST'], website=True)
    def portal_documentation_submit(self, **post):
        partner = request.env.user.partner_id
        student = partner.get_portal_student()
        redirect_base = '/my/documentacion'

        doc_type = post.get('doc_type', '').strip()
        valid_types = {'dni', 'passport', 'medical', 'iban', 'benefit', 'other'}
        if doc_type not in valid_types:
            return request.redirect(redirect_base + '?error=invalid_type')

        vals = {'partner_id': student.id, 'doc_type': doc_type}

        if doc_type == 'iban':
            iban = post.get('doc_value', '').strip().upper()
            if not iban:
                return request.redirect(redirect_base + '?error=missing_iban')
            vals['doc_value']  = iban
            vals['doc_value2'] = post.get('doc_value2', '').strip()
            expiry = post.get('expiry_date', '').strip()
            if expiry:
                vals['expiry_date'] = expiry
            else:
                vals['expiry_date'] = (date.today() + relativedelta(years=1)).isoformat()
        elif doc_type == 'benefit':
            benefit_type_val = post.get('benefit_type', '').strip()
            BenefitModel = request.env['ems.student.benefit']
            valid_benefit_types_selection = BenefitModel.fields_get(['benefit_type'])['benefit_type']['selection']
            valid_benefit_types = [k for k, _ in valid_benefit_types_selection]
            if benefit_type_val not in valid_benefit_types:
                return request.redirect(redirect_base + '?error=invalid_benefit_type')
            uploaded = request.httprequest.files.get('doc_file')
            if not uploaded or not uploaded.filename:
                return request.redirect(redirect_base + '?error=missing_file')
            vals['benefit_type'] = benefit_type_val
            vals['doc_file']     = base64.b64encode(uploaded.read())
            vals['doc_file_name'] = uploaded.filename
        else:
            uploaded = request.httprequest.files.get('doc_file')
            if not uploaded or not uploaded.filename:
                return request.redirect(redirect_base + '?error=missing_file')
            vals['doc_file']      = base64.b64encode(uploaded.read())
            vals['doc_file_name'] = uploaded.filename
            expiry = post.get('expiry_date', '').strip()
            if expiry:
                vals['expiry_date'] = expiry

        try:
            request.env['ems.student.document'].sudo().create(vals)
        except Exception:
            return request.redirect(redirect_base + '?error=duplicate_pending')

        return request.redirect(redirect_base)

    @http.route('/my/documentacion/renew-iban', type='http', auth='user', methods=['POST'], website=True)
    def portal_documentation_renew_iban(self, **post):
        partner = request.env.user.partner_id
        student = partner.get_portal_student()
        new_expiry = date.today() + relativedelta(years=1)

        iban_doc = request.env['ems.student.document'].sudo().search([
            ('partner_id', '=', student.id),
            ('doc_type', '=', 'iban'),
            ('status', '=', 'approved'),
        ], order='upload_date desc', limit=1)

        if iban_doc:
            iban_doc.sudo().write({'expiry_date': new_expiry})
            iban_doc.sudo().message_post(
                body=Markup('<b>IBAN renewed by %s via portal.</b> New expiry: %s') % (
                    escape(request.env.user.partner_id.name),
                    new_expiry.strftime('%d/%m/%Y')
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        else:
            # No document exists yet — create one from billing bank data (imported via CSV)
            bank = student.bank_ids.filtered(lambda b: b.active)[:1]
            if not bank:
                return request.redirect('/my/documentacion')
            request.env['ems.student.document'].sudo().create({
                'partner_id': student.id,
                'doc_type': 'iban',
                'doc_value': bank.acc_number,
                'doc_value2': bank.acc_holder_name or student.name,
                'expiry_date': new_expiry,
                'status': 'approved',
            })

        return request.redirect('/my/documentacion?renewed=1')

    @http.route('/my/documentacion/cancel/<int:doc_id>', type='http', auth='user', methods=['POST'], website=True)
    def portal_documentation_cancel(self, doc_id, **post):
        partner = request.env.user.partner_id
        student = partner.get_portal_student()

        doc = request.env['ems.student.document'].sudo().browse(doc_id)
        if not doc.exists() or doc.partner_id != student or doc.status != 'pending':
            return request.redirect('/my/documentacion')

        doc.action_cancel()
        return request.redirect('/my/documentacion')