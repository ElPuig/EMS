# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.mail.tools.discuss import Store

class ems_SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_default_course(self):
        """
        Logic to auto-select the academic year:
        1. Look for the course marked as 'Enrollment Default' (e.g., 2026/27).
        2. If not found, fallback to 'Current' (e.g., 2025/26).
        """
        course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)
        if not course:
            course = self.env['ems.course'].search([('is_current', '=', True)], limit=1)
        return course.id if course else False

    ems_enrollment_number = fields.Char(string="Enrollment Number", copy=False, readonly=True)
    # Campo auxiliar para el filtro de la vista
    ems_existing_product_ids = fields.Many2many(
        'product.template',
        compute='_compute_existing_products',
        string="Enrolled Products (Technical)"
    )

    # --- New Field ---
    ems_course_id = fields.Many2one(
        'ems.course', 
        string="Academic Year", 
        #required=True #Lo haremos obligatorio en la vista 
        default=_get_default_course,
        help="Academic year for this enrollment."
    )

    # Campo para seleccionar el estudio en la matrícula
    ems_study_id = fields.Many2one(
        'ems.study',
        string="Studies for enrollment"
        #required=True #Lo haremos obligatorio en la vista
    )

    # Campo para seleccionar el nivel de estudios en la matrícula
    ems_level_id = fields.Many2one(
        comodel_name="ems.level",
        string="Level",
        related="ems_study_id.level_id", 
        store=True # Recomendado para poder agrupar y filtrar por nivel en la vista lista
    )

    # Shift (Turno) ---
    shift = fields.Selection(
        selection=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
        ],
        string="Shift",
        #required=True,
        #default='morning',
        help="Morning or afternoon shift for this enrollment."
    )

    # Destination group: the single source of truth for group placement. Optional
    # (never blocks confirmation); there is no equivalent field on res.partner.
    # The domain only restricts by study (a student may switch shift); a shift/course
    # mismatch is surfaced as a soft warning instead of being blocked.
    ems_group_id = fields.Many2one(
        'ems.group',
        string="Destination group",
        copy=False,
        domain="[('study_id', '=', ems_study_id)]",
        help="Group the student will be placed in: in bulk when the destination "
             "study is transitioned, or individually when a latecomer confirms "
             "after that transition. Left empty until known."
    )

    # Modificamos el campo nativo 'sale_order_template_id' (Plantilla de Presupuesto)
    # Le aplicamos un dominio dinámico: Solo mostrar plantillas del estudio seleccionado arriba
    sale_order_template_id = fields.Many2one(
        comodel_name='sale.order.template', 
        domain="[('ems_study_id', '=', ems_study_id)]"
    )

    ems_authorization_ids = fields.One2many(
        comodel_name='ems.authorization',
        inverse_name='enrollment_id',
        string="Authorizations"
    )

    ems_payment_method = fields.Selection([
        ('transfer',     'Bank Transfer'),
        ('direct_debit', 'Direct Debit'),
    ], string='Payment Method')

    ems_has_fees = fields.Boolean(
        compute='_compute_fee_amounts', store=True,
        string='Has Fee Products',
    )
    ems_fee_amount = fields.Monetary(
        compute='_compute_fee_amounts', store=True,
        string='Fee Amount',
    )
    ems_non_fee_amount = fields.Monetary(
        compute='_compute_fee_amounts', store=True,
        string='Non-fee Amount',
    )
    ems_first_installment = fields.Monetary(
        compute='_compute_installments',
        string='First Installment',
    )
    ems_second_installment = fields.Monetary(
        compute='_compute_installments',
        string='Second Installment',
    )

    @api.depends('order_line.price_subtotal', 'order_line.product_template_id.ems_is_enrollment_fee')
    def _compute_fee_amounts(self):
        for order in self:
            fee = sum(
                l.price_subtotal for l in order.order_line
                if l.product_template_id.ems_is_enrollment_fee
            )
            non_fee = sum(
                l.price_subtotal for l in order.order_line
                if not l.product_template_id.ems_is_enrollment_fee
            )
            order.ems_fee_amount = fee
            order.ems_non_fee_amount = non_fee
            order.ems_has_fees = fee > 0

    @api.depends('ems_fee_amount', 'ems_non_fee_amount')
    def _compute_installments(self):
        for order in self:
            order.ems_first_installment = order.ems_non_fee_amount + order.ems_fee_amount * 0.5
            order.ems_second_installment = order.ems_fee_amount * 0.5

    ems_enrollment_status_label = fields.Char(
        string='Enrollment Status',
        compute='_compute_enrollment_status_label',
        store=False,
    )    

    @api.depends('state')
    def _compute_enrollment_status_label(self):
        labels = {
            'draft': 'Pre-enrollment',
            'sent': 'Sent to student',
            'sale': 'Confirmed',
            'cancel': 'Cancelled',
            'done': 'Locked',
        }
        for rec in self:
            rec.ems_enrollment_status_label = labels.get(rec.state, rec.state)

    def _get_dynamic_enrollment_name(self):
        """Build the enrollment code dynamically using acronyms and shortening the year."""
        self.ensure_one()
        
        # 1. Procesar el año académico para acortarlo ("2025-2026" -> "25-26")
        course_str = 'XXXX'
        if self.ems_course_id and self.ems_course_id.name:
            full_course = self.ems_course_id.name.strip()
            # Comprobamos si tiene el formato exacto de 9 caracteres como "2025-2026" o "2025/2026"
            if len(full_course) == 9 and full_course[4] in ('-', '/'):
                # Cogemos los dígitos de las posiciones 2:4 (el 25) y 7:9 (el 26)
                course_str = f"{full_course[2:4]}-{full_course[7:9]}"
            else:
                # Si tiene otro formato raro (ej. solo "2025"), lo dejamos tal cual por seguridad
                course_str = full_course
        # 2. Obtener acrónimos de Nivel y Estudio
        level_str = self.ems_level_id.acronym if self.ems_level_id and self.ems_level_id.acronym else 'XXX'
        study_str = self.ems_study_id.acronym if self.ems_study_id and self.ems_study_id.acronym else 'XXX'
        # 3. Obtener el número de secuencia
        num_str = self.ems_enrollment_number or 'New'
        # 4. Construir y limpiar la cadena final
        return f"M/{course_str}/{level_str}/{study_str}/{num_str}".replace(' ', '')
    
    
    
    @api.onchange('ems_course_id', 'ems_level_id', 'ems_study_id')
    def _onchange_enrollment_name_preview(self):
        """Update the enrollment code in real time on the screen before saving."""
        for rec in self:
            # Solo actualizamos la vista si está en estado borrador/enviado y es una matrícula
            if rec.state in ['draft', 'sent'] and rec.ems_study_id:
                rec.name = rec._get_dynamic_enrollment_name()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Clear the salesperson so the company appears as fallback in communications.
            vals['user_id'] = False
            # Comprobamos si es una matrícula (es decir, si el usuario ha seleccionado un estudio)
            if vals.get('ems_study_id'):                
                # 1. Le pedimos a nuestra secuencia el número correlativo (ej. 0004)
                vals['ems_enrollment_number'] = self.env['ir.sequence'].next_by_code('ems.enrollment.number') or '0000'                
                # 2. Sobrescribimos el campo 'name'.
                # Al ponerle cualquier texto que no sea 'New' o 'Nuevo', bloqueamos
                # que Odoo le asigne la secuencia 'S0000X' por defecto de las ventas.
                vals['name'] = 'Generando...'
        # 3. Llamamos al método nativo para que guarde en base de datos.
        # Como va con 'name' = 'Generando...', Odoo no usará la S0000X.
        records = super(ems_SaleOrder, self).create(vals_list)
        # 4. Ahora que el registro ya existe y tiene su número de matrícula guardado,
        # forzamos a que construya el nombre definitivo.
        for rec in records:
            if rec.ems_study_id and rec.ems_enrollment_number:
                rec.name = rec._get_dynamic_enrollment_name()
        return records

    def write(self, vals):
        """Actualiza el código si el usuario cambia de idea después de haber guardado."""
        # Detect the draft -> sent transition for enrollments: once the secretary
        # sends the proposal to the students, the tutor's job is done.
        handover_orders = self.env['sale.order']
        if vals.get('state') == 'sent':
            handover_orders = self.filtered(
                lambda o: o.ems_study_id and o.state != 'sent'
            )

        res = super(ems_SaleOrder, self).write(vals)

        if handover_orders:
            handover_orders._ems_unfollow_teachers()

        # Si se ha modificado alguno de los campos que forman el código...
        if any(field in vals for field in ['ems_course_id', 'ems_level_id', 'ems_study_id']):
            for rec in self:
                # Y seguimos en estado modificable...
                if rec.state in ['draft', 'sent'] and rec.ems_enrollment_number:
                    new_name = rec._get_dynamic_enrollment_name()
                    # Actualizamos el código si ha cambiado
                    if rec.name != new_name:
                        rec.name = new_name
        return res

    # ------------------------------------------------------------------
    # Secretary handover (issue #270)
    # ------------------------------------------------------------------
    def _ems_unfollow_teachers(self):
        """Stop notifying teachers once the enrollment has been sent to students.

        Their job is done; from now on the secretary follows up through review
        activities (not as followers — see _ems_schedule_comment_review_activities)."""
        teachers = (
            self.env.ref('ems.group_teacher').users
            - self.env.ref('ems.group_secretary').users
            - self.env.ref('ems.group_academic_admin').users
        )
        teacher_partner_ids = teachers.mapped('partner_id').ids
        if teacher_partner_ids:
            for order in self:
                order.message_unsubscribe(partner_ids=teacher_partner_ids)

    def _ems_schedule_comment_review_activities(self):
        """Schedule a review to-do for each secretary when a student/family
        comments from the portal. The activity shows up in their systray and in
        "view all activities". Skips orders that already have a pending one so
        repeated comments don't pile up tasks.

        No email is sent to the secretaries: the systray task is their only
        notice. We use ``mail_activity_quick_update`` to skip the assignment
        email, and unsubscribe them afterwards because scheduling an activity
        auto-subscribes the assignee (which would forward them the comments)."""
        comment_type = self.env.ref('ems.mail_activity_enrollment_comment')
        secretaries = self.env.ref('ems.group_secretary').users
        secretary_partner_ids = secretaries.mapped('partner_id').ids
        for order in self:
            pending = order.activity_ids.filtered(
                lambda a: a.activity_type_id == comment_type
            )
            if not pending:
                for user in secretaries:
                    order.with_context(mail_activity_quick_update=True).activity_schedule(
                        act_type_xmlid='ems.mail_activity_enrollment_comment',
                        summary='Review enrollment comment: %s' % order.name,
                        user_id=user.id,
                    )
            # Always keep secretaries out of the followers (activity creation
            # auto-subscribes the assignee), so the comment doesn't email them.
            if secretary_partner_ids:
                order.message_unsubscribe(partner_ids=secretary_partner_ids)

    def _thread_to_store(self, store, /, *, fields=None, request_list=None):
        """In the chatter, show each user only their OWN enrollment-comment
        review activity. We create one per secretary (for the systray), but they
        are duplicates of the same task; this only affects activities, messages
        and everything else are served unchanged for everyone."""
        if request_list and "activities" in request_list:
            reduced = [r for r in request_list if r != "activities"]
            super()._thread_to_store(store, fields=fields, request_list=reduced)
            comment_type = self.env.ref(
                'ems.mail_activity_enrollment_comment', raise_if_not_found=False
            )
            for thread in self:
                acts = thread.with_context(active_test=True).activity_ids
                if comment_type:
                    acts = acts.filtered(
                        lambda a: a.activity_type_id != comment_type
                        or a.user_id == self.env.user
                    )
                store.add(thread, {"activities": Store.many(acts)}, as_thread=True)
        else:
            super()._thread_to_store(store, fields=fields, request_list=request_list)

    # Limpiamos la plantilla si el usuario cambia el estudio para evitar errores
    @api.onchange('ems_study_id')
    def _onchange_ems_study_id(self):
        self.sale_order_template_id = False
        self.with_context(skip_tutoria_check=True).order_line = [(5, 0, 0)]
        # Drop a destination group that no longer belongs to the selected study.
        if self.ems_group_id and self.ems_group_id.study_id != self.ems_study_id:
            self.ems_group_id = False

    @api.onchange('ems_group_id')
    def _onchange_ems_group_id(self):
        """Soft warning when the chosen group's shift or course does not match the
        enrollment/template (the domain only enforces the study)."""
        group = self.ems_group_id
        if not group:
            return
        issues = []
        if self.shift and group.shift and group.shift != self.shift:
            issues.append(_("The group shift does not match the enrollment shift."))
        template_year = self.sale_order_template_id.study_year
        if template_year and group.course != template_year:
            issues.append(_(
                "The group course (%(group)s) does not match the enrollment "
                "template course (%(template)s).",
                group=group.course, template=template_year))
        if issues:
            return {'warning': {
                'title': _("Destination group mismatch"),
                'message': "\n".join(issues),
            }}

    @api.depends('order_line.product_template_id')
    def _compute_existing_products(self):
        for order in self:
            valid_lines = order.order_line.filtered(lambda l: l.product_template_id)
            order.ems_existing_product_ids = valid_lines.mapped('product_template_id')
    
    @api.onchange('ems_level_id', 'ems_study_id')
    def _onchange_ems_level_study_for_authorizations(self):
        """Autofills authorizations based on the selected Level and Study."""
        for rec in self:
            rec.ems_authorization_ids = rec._get_authorization_commands()

    def _get_authorization_commands(self):
        """Devuelve los comandos ORM para sincronizar autorizaciones."""
        self.ensure_one()
        domain = ['&', ('ems_level_ids', '=', False), ('ems_study_ids', '=', False)]
        if self.ems_level_id:
            domain = ['|', ('ems_level_ids', 'in', self.ems_level_id.id)] + domain
        if self.ems_study_id:
            domain = ['|', ('ems_study_ids', 'in', self.ems_study_id.id)] + domain

        templates = self.env['ems.authorization.template'].search(domain)
        commands = []
        to_remove = self.ems_authorization_ids.filtered(
            lambda a: a.template_id not in templates
        )
        for auth in to_remove:
            commands.append((2, auth.id, 0))
        for template in templates:
            existing = self.ems_authorization_ids.filtered(
                lambda a: a.template_id == template
            )
            if not existing:
                commands.append((0, 0, {
                    'template_id': template.id,
                    'status': 'pending',
                }))
        return commands

    def apply_authorizations(self):
        """Aplica autorizaciones persistiendo en BD. Llamable desde código."""
        for rec in self:
            commands = rec._get_authorization_commands()
            if commands:
                rec.write({'ems_authorization_ids': commands})

    @api.constrains('partner_id', 'ems_course_id', 'state')
    def _check_unique_enrollment_per_course(self):
        """
        Prevents the same student (partner_id) from having more than one active enrollment
        (that has not been cancelled) in the same academic year (ems_course_id).
        """
        for order in self:
            # Si el registro actual está cancelado o no tiene curso/alumno, lo ignoramos
            if order.state == 'cancel' or not order.partner_id or not order.ems_course_id:
                continue
            
            # Buscamos si existe otra orden para el mismo alumno y curso que NO esté cancelada
            domain = [
                ('id', '!=', order.id), # Excluir el registro actual
                ('partner_id', '=', order.partner_id.id),
                ('ems_course_id', '=', order.ems_course_id.id),
                ('state', '!=', 'cancel')
            ]
            
            existing_enrollment = self.search(domain, limit=1)
            
            if existing_enrollment:
                raise ValidationError(
                    f"The student {order.partner_id.name} already has a pre-enrolment or "
                    f"active enrolment for the academic year {order.ems_course_id.display_name}."
                )

    def _is_blocked_tutor(self):
        return (
            self.env.user.has_group('ems.group_teacher') and
            not self.env.user.has_group('ems.group_tutor') and
            not self.env.user.has_group('ems.group_academic_admin') and
            not self.env.user.has_group('ems.group_secretary')
        )

    def action_cancel(self):
        if self._is_blocked_tutor():
            raise ValidationError(
                "Tutors cannot cancel enrollments. "
                "Please contact the secretary or admin."
            )
        return super().action_cancel()

    def action_quotation_sent(self):
        if self._is_blocked_tutor():
            raise ValidationError(
                "Tutors cannot change the enrollment status. "
                "Please contact the secretary or admin."
            )
        return super().action_quotation_sent()

    def action_quotation_send(self):
        if self._is_blocked_tutor():
            raise ValidationError(
                "Tutors cannot send enrollments to students. "
                "Please contact the secretary or admin."
            )
        if self.ems_study_id:
            template = self.env.ref('ems.email_template_enrollment_send', raise_if_not_found=False)
            if template:
                action = super().action_quotation_send()
                action['context']['default_template_id'] = template.id
                return action
        return super().action_quotation_send()

    def action_send_enrollment_proposal(self):
        """One-click bulk action for the Matricules list: email the enrollment
        proposal (``email_template_enrollment_send``) to the selected
        enrollments and mark the drafts as sent, merging the "Send an email"
        and "Mark Quotation as Sent" steps into a single button."""
        if self._is_blocked_tutor():
            raise ValidationError(_(
                "Tutors cannot send enrollments to students. "
                "Please contact the secretary or admin."))
        template = self.env.ref(
            'ems.email_template_enrollment_send', raise_if_not_found=False)
        if not template:
            raise UserError(_("The enrollment proposal email template is missing."))
        orders = self.filtered(
            lambda order: order.ems_study_id and order.state in ('draft', 'sent'))
        if not orders:
            raise UserError(_("Select draft enrollments to send."))
        for order in orders:
            template.send_mail(order.id, force_send=True)
        orders.filtered(lambda order: order.state == 'draft').action_quotation_sent()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Enrollments sent"),
                'message': _(
                    "%(count)s enrollment(s) emailed and marked as sent.",
                    count=len(orders)),
                'type': 'success',
                'sticky': False,
            },
        }

    def _notify_get_recipients_groups(self, message, model_description, msg_vals=None):
        groups = super()._notify_get_recipients_groups(message, model_description, msg_vals=msg_vals)
        if self.ems_study_id:
            for group in groups:
                group[2]['has_button_access'] = False
        return groups

    def action_confirm(self):
        if self._is_blocked_tutor():
            raise ValidationError(
                "Tutors cannot confirm enrollments. "
                "Please contact the secretary or admin."
            )
        for order in self:
            pending = order.ems_authorization_ids.filtered(
                lambda a: a.status == 'pending' and a.template_id.is_required
            )
            if pending:
                names = '\n'.join('- ' + t for t in pending.mapped('template_id.name'))
                raise ValidationError(
                    "Cannot confirm enrollment '%s'. "
                    "The following required authorizations are still pending:\n%s"
                    % (order.name, names)
                )
        res = super().action_confirm()
        comment_type = self.env.ref('ems.mail_activity_enrollment_comment', raise_if_not_found=False)
        for order in self:
            if order.ems_study_id:
                order._ems_admit_student()
                order._ems_generate_enrollment_invoice()
                # The enrollment is settled: drop any pending comment-review tasks.
                if comment_type:
                    stale = order.activity_ids.filtered(
                        lambda a: a.activity_type_id == comment_type
                    )
                    stale.with_context(ems_activity_cascade=True).unlink()
        return res

    # ------------------------------------------------------------------
    # Admission (applicant -> student) and destination placement
    # ------------------------------------------------------------------
    def _ems_admit_student(self):
        """Formal admission act on enrollment confirmation.

        Always converts an applicant into a student, and consumes the GEDAC assignment
        of an internal continuer once the granted study is the one being confirmed.
        Placement (group + subject enrollments) only runs for latecomers whose
        destination study has already been transitioned; in the normal case (study still
        active) the transition wizard places everyone in bulk later. The
        `transition_state` field lands in the transition phase, so until then this
        branch stays dormant.
        """
        self.ensure_one()
        partner = self.partner_id
        if partner.contact_type == 'applicant':
            partner._ems_convert_to_student()
        # Spent assignment: clearing it keeps the "With GEDAC assignment" filter showing
        # only the continuers still pending enrollment. A different study being confirmed
        # (the manual escape hatch) leaves the assignment standing.
        if partner.preinscription_study_id \
                and partner.preinscription_study_id == self.ems_study_id:
            partner.write({
                'preinscription_study_id': False,
                'preinscription_shift': False,
                'preinscription_course': False,
            })
        if getattr(self.ems_study_id, 'transition_state', False) == 'transitioned':
            self._ems_apply_destination_placement()

    def _ems_suggest_group(self):
        """Suggest a destination group for this enrollment from its own data.

        Continuing student: the same acronym as the student's current group plus
        the enrollment shift, in the destination study/course. Applicant: the
        lowest-letter group of the shift. Empty when there is no single match.
        """
        self.ensure_one()
        study = self.ems_study_id
        course = self.sale_order_template_id.study_year
        if not (study and course):
            return self.env['ems.group']
        Group = self.env['ems.group']
        partner = self.partner_id
        if partner.contact_type == 'applicant':
            domain = [('study_id', '=', study.id), ('course', '=', course)]
            shift = self.shift or partner.preinscription_shift
            if shift:
                domain.append(('shift', '=', shift))
            return Group.search(domain, order='acronym', limit=1)
        current = partner.main_group_id
        if not current:
            return Group
        domain = [('study_id', '=', study.id), ('course', '=', course),
                  ('acronym', '=', current.acronym)]
        shift = self.shift or current.shift
        if shift:
            domain.append(('shift', '=', shift))
        matches = Group.search(domain)
        return matches if len(matches) == 1 else Group

    def _ems_fill_suggested_group(self):
        """Fill ems_group_id with the suggestion on enrollments that have none.
        Returns the number of enrollments updated."""
        filled = 0
        for order in self:
            if order.ems_group_id:
                continue
            group = order._ems_suggest_group()
            if group:
                order.ems_group_id = group
                filled += 1
        return filled

    def _ems_apply_destination_placement(self):
        """Place the student in the destination group and materialize the subject
        enrollments from the order lines.

        Idempotent: an existing (student, group, subject) triple is not
        duplicated. Shared by action_confirm (individual latecomers) and the
        transition wizard (bulk). Runs with sudo because ems.enrollment blocks
        manual creation for non-admins and the secretary may be confirming.
        """
        self.ensure_one()
        group = self.ems_group_id
        if not group:
            return
        student = self.partner_id
        if student.main_group_id != group:
            student.sudo().main_group_id = group
        Enrollment = self.env['ems.enrollment'].sudo()
        subjects = self.env['ems.subject'].sudo().search([
            ('product_id', 'in', self.order_line.product_id.ids)])
        for subject in subjects:
            exists = Enrollment.search_count([
                ('student_id', '=', student.id),
                ('group_id', '=', group.id),
                ('subject_id', '=', subject.id)])
            if not exists:
                Enrollment.create({
                    'student_id': student.id,
                    'group_id': group.id,
                    'subject_id': subject.id,
                })

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------
    def _ems_billing_due_dates(self):
        """(first, second) default collection due dates for this enrollment.

        Default to 15-Jul / 15-Sep of the course start year. They are only a
        marker of the installment and the batch; the real SEPA collection date
        is chosen later, when the bank file is generated.
        """
        self.ensure_one()
        year = self.ems_course_id.start or fields.Date.context_today(self).year
        return date(year, 7, 15), date(year, 9, 15)

    def action_ems_reapply_benefits(self):
        """Apply the student's current benefit status to an already confirmed
        enrollment.

        Confirmed orders are frozen against benefit changes (see
        sale.order.line._ems_benefit_frozen_lines), so a bonification or
        exemption approved after confirmation needs this explicit action:
        cancel the posted (unpaid) invoice, recompute the fee lines with the
        current benefit status and regenerate the invoice, so that order,
        invoice and portal match again.
        """
        for order in self:
            if order.state != 'sale':
                raise ValidationError(_(
                    "Benefits can only be re-applied on a confirmed enrollment."))
            invoices = order.invoice_ids.filtered(
                lambda m: m.move_type == 'out_invoice' and m.state != 'cancel')
            paid = invoices.filtered(
                lambda m: m.amount_total and m.payment_state != 'not_paid')
            if paid:
                raise ValidationError(_(
                    "Invoice %s already has payments registered. "
                    "Issue a credit note manually instead.") % ', '.join(paid.mapped('name')))
            for inv in invoices.sudo():
                if inv.state == 'posted':
                    inv.button_draft()
                inv.button_cancel()
            lines = order.order_line.with_context(ems_reapply_benefits=True)
            lines._compute_price_unit()
            lines._compute_discount()
            order._ems_generate_enrollment_invoice()
            order.message_post(
                body=_("Benefits re-applied by %s: the invoice has been "
                       "regenerated with the student's current benefit status.")
                % self.env.user.name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def _ems_generate_enrollment_invoice(self):
        """Create, date and post the enrollment invoice. Idempotent.

        - Single-payment plan: one invoice due on the first date.
        - Deferred plan (fees split): one invoice with two due dates
          (first installment = non-fee items + 50% fees @ first date;
          second installment = 50% fees @ second date). The split percentage
          is computed PER enrollment from its own amounts.
        - Direct debit: the confirmed student IBAN is stored on the invoice
          (debtor account, ready for SEPA). Transfer: no student IBAN.
        - The enrollment code is referenced via invoice_origin (native) + ref
          + payment_reference, keeping the legal invoice numbering untouched.
        """
        self.ensure_one()
        existing = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state != 'cancel')
        if existing:
            return existing

        order = self.sudo()
        inv = order._create_invoices()[:1]
        if not inv:
            return inv

        today = fields.Date.context_today(self)
        due1, due2 = order._ems_billing_due_dates()
        total = inv.amount_total
        deferred = bool(
            order.payment_term_id
            and len(order.payment_term_id.line_ids) > 1
            and order.ems_second_installment > 0
            and total > 0
        )

        vals = {
            'invoice_date': today,
            'ref': order.name,
            'payment_reference': order.name,
        }
        if deferred:
            pct1 = round(order.ems_first_installment / total * 100.0, 6)
            term = self.env['account.payment.term'].sudo().create({
                'name': 'EMS %s' % order.name,
                'company_id': inv.company_id.id,
                'line_ids': [
                    (0, 0, {'value': 'percent', 'value_amount': pct1,
                            'delay_type': 'days_after', 'nb_days': (due1 - today).days}),
                    (0, 0, {'value': 'percent', 'value_amount': round(100.0 - pct1, 6),
                            'delay_type': 'days_after', 'nb_days': (due2 - today).days}),
                ],
            })
            vals['invoice_payment_term_id'] = term.id
        else:
            vals['invoice_payment_term_id'] = False
            vals['invoice_date_due'] = due1

        if order.ems_payment_method == 'direct_debit':
            bank = order.partner_id.bank_ids[:1]
            if bank:
                vals['partner_bank_id'] = bank.id

        inv.write(vals)
        inv.action_post()
        return inv