# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    # Campo para vincular la plantilla (Pack) a un Estudio concreto
    ems_study_id = fields.Many2one(
        'ems.study', 
        string="Academic Study",
        help="Define which study this enrollment belongs to."
    )
    # Campo auxiliar para ver el nivel (CFGS, Grado, etc) automáticamente
    ems_level_id = fields.Many2one(
        related='ems_study_id.level_id', 
        store=True, 
        string="Nivel"
    )

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
        return course

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

    # Modificamos el campo nativo 'sale_order_template_id' (Plantilla de Presupuesto)
    # Le aplicamos un dominio dinámico: Solo mostrar plantillas del estudio seleccionado arriba
    sale_order_template_id = fields.Many2one(
        domain="[('ems_study_id', '=', ems_study_id)]"
    )

    # Limpiamos la plantilla si el usuario cambia el estudio para evitar errores
    @api.onchange('ems_study_id')
    def _onchange_ems_study_id(self):
        self.sale_order_template_id = False

    @api.depends('order_line.product_template_id')
    def _compute_existing_products(self):
        for order in self:
            # Extraemos los productos de las líneas actuales
            order.ems_existing_product_ids = order.order_line.mapped('product_template_id')