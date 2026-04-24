# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

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
        res = super(ems_SaleOrder, self).write(vals)
        
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

    # Limpiamos la plantilla si el usuario cambia el estudio para evitar errores
    @api.onchange('ems_study_id')
    def _onchange_ems_study_id(self):
        self.sale_order_template_id = False
        self.with_context(skip_tutoria_check=True).order_line = [(5, 0, 0)]

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
            not self.env.user.has_group('ems.group_admin') and
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
        return super().action_quotation_send()

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
        return super().action_confirm()