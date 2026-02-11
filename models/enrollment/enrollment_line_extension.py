# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

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