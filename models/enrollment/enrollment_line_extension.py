# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
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
                        'message': _(
                            "The item '%(name)s' is already in the list. "
                            "Please select a different one.", name=name,
                        ),
                    }
                }
    def _ems_benefit_frozen_lines(self):
        """Lines of orders no longer editable by the student (confirmed,
        locked or cancelled): their prices and discounts must stay exactly as
        invoiced, so a benefit approved after confirmation never silently
        alters them. The explicit secretary action
        (sale.order.action_ems_reapply_benefits) lifts the freeze via context.
        """
        if self.env.context.get('ems_reapply_benefits'):
            return self.browse()
        return self.filtered(lambda l: l.order_id.state not in ('draft', 'sent'))

    @api.depends('product_id', 'order_id.order_line', 'order_id.partner_id.benefit_status')
    def _compute_price_unit(self):
        lines = self - self._ems_benefit_frozen_lines()
        # Run Odoo's own pricing logic first (price lists, etc.).
        super(SaleOrderLine, lines)._compute_price_unit()
        for line in lines:
            # A fee line's price is calculated, not looked up: only act on those.
            if line.product_template_id.ems_is_enrollment_fee:
                subject_lines = line.order_id.order_line.filtered(
                    lambda l: l.product_template_id and not l.product_template_id.is_generic and not l.product_template_id.ems_is_tutoria
                )
                count = len(subject_lines)

                max_fee = line.product_template_id.list_price
                unit_cost = line.product_template_id.ems_subject_unit_cost

                # Never exceed the product's own list price, however many subjects.
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
        lines = self - self._ems_benefit_frozen_lines()
        super(SaleOrderLine, lines)._compute_discount()
        for line in lines:
            if line.product_template_id.ems_is_enrollment_fee:
                discount = 0.0
                benefit_text = ""
                partner = line.order_id.partner_id
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
                raise ValidationError(_(
                    "Item '%(name)s' is already enrolled in this record.",
                    name=line.product_id.name,
                ))

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