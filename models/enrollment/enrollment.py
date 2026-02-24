# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
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
        required=True, 
        default=_get_default_course,
        help="Academic year for this enrollment."
    )

    # Campo para seleccionar el estudio en la matrícula
    ems_study_id = fields.Many2one(
        'ems.study',
        string="Studies for enrollment",
        required=True
    )

    # Campo para seleccionar el nivel de estudios en la matrícula
    ems_level_id = fields.Many2one(
        comodel_name="ems.level",
        string="Level",
        related="ems_study_id.level_id", 
        store=True # Recomendado para poder agrupar y filtrar por nivel en la vista lista
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

    # Limpiamos la plantilla si el usuario cambia el estudio para evitar errores
    @api.onchange('ems_study_id')
    def _onchange_ems_study_id(self):
        self.sale_order_template_id = False

    @api.depends('order_line.product_template_id')
    def _compute_existing_products(self):
        for order in self:
            valid_lines = order.order_line.filtered(lambda l: l.product_template_id)
            order.ems_existing_product_ids = valid_lines.mapped('product_template_id')
    
    @api.onchange('ems_level_id', 'ems_study_id')
    def _onchange_ems_level_study_for_authorizations(self):
        """
        Autofills authorizations based on the selected Level and Study.
        """
        for rec in self:
            # 1. Construir la búsqueda (Domain) dinámicamente
            # Por defecto, buscamos las globales (sin nivel Y sin estudio)
            domain = ['&', ('ems_level_ids', '=', False), ('ems_study_ids', '=', False)]
            
            # Si hay nivel, añadimos la condición "O que coincida con este nivel"
            if rec.ems_level_id:
                domain = ['|', ('ems_level_ids', 'in', rec.ems_level_id.id)] + domain
                
            # Si hay estudio, añadimos la condición "O que coincida con este estudio"
            if rec.ems_study_id:
                domain = ['|', ('ems_study_ids', 'in', rec.ems_study_id.id)] + domain

            # Ejecutamos la búsqueda de plantillas que aplican
            templates = rec.env['ems.authorization.template'].search(domain)

            # 2. Preparar las líneas a añadir o eliminar
            new_authorizations = []
            
            # ¡EL TRUCO LIMPIO! Borramos cualquier autorización actual cuya plantilla 
            # no esté en la lista de 'templates' que acabamos de buscar.
            to_remove = rec.ems_authorization_ids.filtered(lambda a: a.template_id not in templates)
            for auth in to_remove:
                new_authorizations.append((2, auth.id, 0))

            # Añadimos las que falten
            for template in templates:
                existing = rec.ems_authorization_ids.filtered(lambda a: a.template_id == template)
                if not existing:
                    new_authorizations.append((0, 0, {
                        'template_id': template.id,
                        'status': 'pending',
                    }))

            # 3. Aplicar cambios
            if new_authorizations:
                rec.ems_authorization_ids = new_authorizations