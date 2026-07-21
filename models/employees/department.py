# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ems_department(models.Model):
    _inherit = "hr.department"

    seminar_head_id = fields.Many2one(
        string="Seminar Chief", comodel_name="hr.employee",
        help="Every other member of this department (the Department Chief excluded) will have "
             "their Manager set to this employee; the Seminar Chief's own Manager is set to the "
             "Department Chief.")
    is_top_level = fields.Boolean(
        string="Top-level Department",
        help="A top-level department has no parent department and no Seminar Chief. Its Manager is "
             "labelled 'Head of Studies' and automatically holds the role selected below (Head of "
             "Studies or Deputy Head of Studies) instead of Department Chief.")
    top_level_role = fields.Selection(
        string="Role", selection=[('hos', 'Head of studies'), ('dhos', 'Deputy head of studies')],
        help="Only applies when this is a Top-level Department: which of the two Head of Studies "
             "positions its Manager holds.")

    @api.onchange('is_top_level')
    def _onchange_is_top_level(self):
        for department in self:
            if department.is_top_level:
                department.parent_id = False
                department.seminar_head_id = False
            else:
                department.top_level_role = False

    @api.constrains('is_top_level', 'parent_id', 'seminar_head_id', 'top_level_role')
    def _check_top_level_fields(self):
        for department in self:
            if department.is_top_level:
                if department.parent_id:
                    raise ValidationError(_("A top-level department cannot have a parent department."))
                if department.seminar_head_id:
                    raise ValidationError(_("A top-level department cannot have a Seminar Chief."))
            elif department.top_level_role:
                raise ValidationError(_("Only a top-level department can have a Role selected."))

    def _sanitize_top_level_vals(self, vals):
        if vals.get('is_top_level'):
            vals.setdefault('parent_id', False)
            vals.setdefault('seminar_head_id', False)
        elif vals.get('is_top_level') is False:
            vals.setdefault('top_level_role', False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sanitize_top_level_vals(vals)
        departments = super().create(vals_list)
        for department in departments:
            department._cascade_department_heads(self.env['hr.employee'], self.env['hr.employee'])
        return departments

    def write(self, vals):
        self._sanitize_top_level_vals(vals)
        old_heads = {department: (department.manager_id, department.seminar_head_id) for department in self}
        res = super().write(vals)
        if {'manager_id', 'seminar_head_id', 'parent_id', 'is_top_level', 'top_level_role'} & vals.keys():
            for department in self:
                old_manager, old_seminar_head = old_heads[department]
                department._cascade_department_heads(old_manager, old_seminar_head)
        return res

    def _cascade_department_heads(self, old_manager, old_seminar_head):
        self.ensure_one()
        self.member_ids._compute_parent_id()
        self.child_ids.manager_id._compute_parent_id()
        self.manager_id._compute_parent_id()
        (old_manager | self.manager_id).update_department_head_role()
        (old_manager | self.manager_id).update_head_of_studies_role()
        (old_seminar_head | self.seminar_head_id).update_seminar_head_role()
