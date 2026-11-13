# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.osv import expression

AMPA_PRODUCT_XMLID = 'ems.product_generic_ampa'
# Who sees every student's AMPA membership; everyone else only their tutor scope's.
AMPA_CENTRE_WIDE_GROUPS = ('ems.group_secretary', 'ems.group_academic_admin', 'base.group_system')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Stored so the students' filters are a plain domain instead of walking every invoice.
    ems_ampa_paid = fields.Boolean(
        string="AMPA fee paid", compute='_compute_ems_ampa_paid', store=True, compute_sudo=True,
        help="The confirmed enrollment carries the AMPA fee and the first installment of its "
             "invoice, the one the fee is billed in, has been collected.")

    @api.depends('state', 'order_line.product_id', 'order_line.invoice_lines.move_id.state',
                 'order_line.invoice_lines.move_id.line_ids.reconciled',
                 'order_line.invoice_lines.move_id.line_ids.amount_residual')
    def _compute_ems_ampa_paid(self):
        ampa = self.env.ref(AMPA_PRODUCT_XMLID, raise_if_not_found=False)
        for order in self:
            invoice = (order.state == 'sale' and ampa
                       and ampa in order.order_line.product_id.product_tmpl_id
                       and order._ems_enrollment_invoice())
            first = invoice and invoice._ems_installment_lines()[:1]
            order.ems_ampa_paid = bool(first) and first._ems_installment_paid()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Selection rather than Boolean: empty (not "No") for a student outside the reader's scope,
    # so nobody mistakes "not yours to see" for "not a member".
    ems_ampa_member = fields.Selection(
        selection=[('yes', "Yes"), ('no', "No")], string="AMPA",
        compute='_compute_ems_ampa_member', search='_search_ems_ampa_member', compute_sudo=True,
        groups='ems.group_tutor,ems.group_secretary',
        help="AMPA member: the confirmed enrollment of the running course, the student's own or "
             "a sibling's, carries the AMPA fee and its first installment has been collected. "
             "Shown to the student's tutor and the chiefs above them, the secretary's office and "
             "the administration.")

    @api.depends_context('uid')
    def _compute_ems_ampa_member(self):
        students = self._origin.filtered(lambda partner: partner.contact_type == 'student')
        visible = students and students.with_context(active_test=False).search(
            [('id', 'in', students.ids)] + self._ems_ampa_scope_domain())
        members = self._ems_ampa_member_ids() if visible else set()
        for partner in self:
            if partner._origin in visible:
                partner.ems_ampa_member = 'yes' if partner._origin.id in members else 'no'
            else:
                partner.ems_ampa_member = False

    def _search_ems_ampa_member(self, operator, value):
        if operator not in ('=', '!=') or value not in ('yes', 'no'):
            raise NotImplementedError(_("Unsupported search on the AMPA membership"))
        members = list(self._ems_ampa_member_ids())
        member = (value == 'yes') == (operator == '=')
        return expression.AND([
            [('contact_type', '=', 'student')],
            self._ems_ampa_scope_domain(),
            [('id', 'in' if member else 'not in', members)],
        ])

    @api.model
    def _ems_ampa_scope_domain(self):
        """The students whose AMPA membership the current user may see: all of them for the
        secretary's office and the administration, the tutor scope (the tutor and every chief
        above them, see hr.employee.tutor_scope_user_ids) for everybody else."""
        user = self.env.user
        if any(user.has_group(group) for group in AMPA_CENTRE_WIDE_GROUPS):
            return []
        return [('tutor_id.tutor_scope_user_ids', '=', user.id)]

    @api.model
    def _ems_ampa_member_ids(self):
        """Ids of the AMPA members of the running course: the students whose confirmed
        enrollment has the AMPA fee paid, plus their siblings (students sharing a family
        contact), since the fee is paid once per family. Centre-wide on purpose: three
        queries, cheaper than narrowing them to the students on screen."""
        course = self._ems_running_course()
        payers = self.env['sale.order'].sudo().search([
            ('ems_course_id', '=', course.id), ('ems_ampa_paid', '=', True)]).partner_id
        Relation = self.env['res.partner.relation.all'].sudo()
        families = Relation.search([
            ('this_partner_id', 'in', payers.ids),
            ('other_partner_id.contact_type', '=', 'family')]).other_partner_id
        siblings = Relation.search([
            ('this_partner_id', 'in', families.ids),
            ('other_partner_id.contact_type', '=', 'student')]).other_partner_id
        return set((payers | siblings).ids)
