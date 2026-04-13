# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ems_SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    ems_is_tutoria = fields.Boolean(
        related='product_template_id.ems_is_tutoria',
        string='Is Tutoria',
        readonly=True,
        store=False,
    )

    @api.onchange('product_id')
    def _onchange_product_id_check_duplicate(self):
        """Immediate warning if the subject is already in the list."""
        if self.product_id and self.order_id:
            # Check lines currently loaded in the interface
            duplicates = self.order_id.order_line.filtered(lambda l: l.product_id == self.product_id)
            if len(duplicates) > 1:
                name = self.product_id.display_name
                self.product_id = False  # Clear the field
                return {
                    'warning': {
                        'title': _("Duplicate Item"),
                        'message': _("The item '%s' is already in the list. Please select a different one.") % name,
                    }
                }
    @api.depends('product_id', 'order_id.order_line', 'order_id.partner_id.benefit_status')
    def _compute_price_unit(self):
        # Primero ejecutamos la lógica original de Odoo (tarifas, etc.)
        super()._compute_price_unit()
        for line in self:
            # Solo actuamos si el producto de esta línea está marcado como Tasa
            if line.product_template_id.ems_is_enrollment_fee:
                # 1. Contamos asignaturas (no genéricos) en el pedido padre
                subject_lines = line.order_id.order_line.filtered(
                    lambda l: l.product_template_id and not l.product_template_id.is_generic and not l.product_template_id.ems_is_tutoria
                )
                count = len(subject_lines)
                
                # 2. Obtenemos configuración
                max_fee = line.product_template_id.list_price 
                unit_cost = line.product_template_id.ems_subject_unit_cost
                
                # 3. Aplicamos el menor valor entre el cálculo y el precio de lista
                line.price_unit = min(count * unit_cost, max_fee)
                
                base_name = f"{line.product_template_id.name} ({count} Subjects)"
                benefit_suffix = ""
                partner = line.order_id.partner_id
                if partner and partner.benefit_status:
                    if partner.benefit_status == 'bonification':
                        benefit_suffix = " - Bonification 50%"
                    elif partner.benefit_status == 'exemption':
                        benefit_suffix = " - Exemption 100%"
                
                line.name = f"{base_name}{benefit_suffix}"

    @api.depends('product_id', 'order_id.partner_id.benefit_status')
    def _compute_discount(self):
        # Primero ejecutamos la lógica original
        super()._compute_discount()
        for line in self:
            if line.product_template_id.ems_is_enrollment_fee:
                discount = 0.0
                benefit_text = ""
                partner = line.order_id.partner_id
                # Aplicamos bonificación o exención según el estado del partner
                if partner and partner.benefit_status:
                    if partner.benefit_status == 'bonification':
                        discount = 50.0
                        benefit_text = " - Bonification 50%"
                    elif partner.benefit_status == 'exemption':
                        discount = 100.0
                        benefit_text = " - Exemption 100%"
                line.discount = discount
                if benefit_text and benefit_text not in line.name:
                    line.name = f"{line.name}{benefit_text}"
                    
    @api.constrains('product_id', 'order_id')
    def _check_unique_enrollment_item(self):
        """Database security validation on save."""
        for line in self:
            if not line.product_id:
                continue
            domain = [
                ('order_id', '=', line.order_id.id),
                ('product_id', '=', line.product_id.id),
                ('id', '!=', line.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_("Item '%s' is already enrolled in this record.") % line.product_id.name)

    @api.onchange('product_id', 'product_uom_qty')
    def _force_quantity_one(self):
        """
        Force quantity to 1.0 when selecting a product or 
        whenever the user tries to change the quantity manually.
        """
        if self.product_id and self.product_uom_qty != 1.0:
            self.product_uom_qty = 1.0
            return {
                'warning': {
                    'title': _("Invalid Quantity"),
                    'message': _("The quantity for an enrollment item must always be 1."),
                }
            }