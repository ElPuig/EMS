# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    # Links the enrollment template (Pack) to a specific study.
    ems_study_id = fields.Many2one(
        'ems.study',
        string="Academic Study",
        help="Define which study this enrollment belongs to."
    )
    # Auxiliary field to see the level (CFGS, Grado, etc.) automatically.
    ems_level_id = fields.Many2one(
        related='ems_study_id.level_id',
        store=True,
        string="Level"
    )

    ems_existing_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_existing_products',
        string="Enrolled Products (Technical)"
    )

    study_year = fields.Integer(string="Study Year")

    @api.depends('sale_order_template_line_ids.product_id')
    def _compute_existing_products(self):
        for template in self:
            valid_lines = template.sale_order_template_line_ids.filtered(lambda l: l.product_id)
            template.ems_existing_product_ids = valid_lines.mapped('product_id')
