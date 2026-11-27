# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EmsEnrollmentStudyChangeWizard(models.TransientModel):
    """Issue #875: moves a confirmed enrollment, and its student, to another study. Odoo doesn't let
    the enrollment form do it (changing the study clears every line, and a confirmed line can't be
    deleted), and changing the study on the student alone left the enrollment behind."""
    _name = 'ems.enrollment_study_change_wizard'
    _description = "Change of studies of an enrollment"

    order_id = fields.Many2one(string="Enrollment", comodel_name='sale.order', required=True, readonly=True,
                               ondelete='cascade')
    current_study_id = fields.Many2one(string="Current studies", related='order_id.ems_study_id')
    study_id = fields.Many2one(string="New studies", comodel_name='ems.study', required=True,
                               domain="[('id', '!=', current_study_id)]")
    template_id = fields.Many2one(
        string="Enrollment template", comodel_name='sale.order.template', required=True,
        compute='_compute_template_id', store=True, readonly=False, precompute=True, domain="[('ems_study_id', '=', study_id)]",
        help="Its subjects replace the ones of the current studies in the enrollment.")
    group_id = fields.Many2one(
        string="Destination group", comodel_name='ems.group', required=True,
        compute='_compute_group_id', store=True, readonly=False, precompute=True,
        domain="[('study_id', '=', study_id), ('group_type', '=', 'main')]")
    currency_id = fields.Many2one(related='order_id.currency_id')
    adjustment_amount = fields.Monetary(
        string="Adjustment amount", currency_field='currency_id', default=0.0,
        help="0: the invoice stays as it is. Positive: an invoice for this amount is issued. "
             "Negative: a credit note for this amount is issued.")

    @api.depends('study_id')
    def _compute_template_id(self):
        for wizard in self:
            order = wizard.order_id
            year = order.sale_order_template_id.study_year or order.ems_group_id.course
            wizard.template_id = self.env['sale.order.template']._ems_find_for(wizard.study_id, year)

    @api.depends('template_id')
    def _compute_group_id(self):
        Group = self.env['ems.group']
        for wizard in self:
            if not wizard.study_id:
                wizard.group_id = False
                continue
            domain = [('study_id', '=', wizard.study_id.id), ('group_type', '=', 'main'),
                      ('course', '=', wizard.template_id.study_year)]
            # The enrollment's shift first, any shift otherwise.
            wizard.group_id = Group.search(domain + [('shift', '=', wizard.order_id.shift)], order='name', limit=1) \
                or Group.search(domain, order='name', limit=1)

    @api.model
    def action_open(self, order):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Change studies"),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': order.id},
        }

    def action_apply(self):
        self.ensure_one()
        order = self.order_id
        if order.state != 'sale':
            raise UserError(_("Only a confirmed enrollment can change studies."))
        if self.study_id == order.ems_study_id:
            raise UserError(_("Choose studies other than the current ones."))
        old_study = order.ems_study_id
        student = order.partner_id
        products = self.template_id.sale_order_template_line_ids.product_id.filtered(
            lambda product: product.product_tmpl_id.ems_subject_ids)
        order._ems_change_study(self.study_id, self.template_id, self.group_id, products)
        if self.adjustment_amount:
            order._ems_invoice_study_change_adjustment(self.adjustment_amount)
        order.with_context(ems_study_change=True)._ems_apply_destination_placement()
        stale = self.env['ems.enrollment'].sudo().search([
            ('student_id', '=', student.id), ('group_id.study_id', '=', old_study.id)])
        student._ems_remove_enrollments(stale, _(
            "The change of studies to %(study)s removed the subjects of %(old)s, except these ones, "
            "which already have grades:", study=self.study_id.display_name, old=old_study.display_name))
        return {'type': 'ir.actions.act_window_close'}
