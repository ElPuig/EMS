# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ems_department(models.Model):
    _inherit = "hr.department"

    seminar_head_id = fields.Many2one(
        string="Seminar Chief", comodel_name="hr.employee",
        help="Every other member of this department (the Department Chief excluded) will have "
             "their Manager set to this employee; the Seminar Chief's own Manager is set to the "
             "Department Chief.")

    @api.model_create_multi
    def create(self, vals_list):
        departments = super().create(vals_list)
        for department in departments:
            department.manager_id.update_department_head_role()
            department.seminar_head_id.update_seminar_head_role()
        return departments

    def write(self, vals):
        old_heads = {department: (department.manager_id, department.seminar_head_id) for department in self}
        res = super().write(vals)
        if 'manager_id' in vals or 'seminar_head_id' in vals:
            for department in self:
                old_manager, old_seminar_head = old_heads[department]
                department._cascade_department_heads(old_manager, old_seminar_head)
        return res

    def _cascade_department_heads(self, old_manager, old_seminar_head):
        self.ensure_one()
        self.member_ids._compute_parent_id()
        (old_manager | self.manager_id).update_department_head_role()
        (old_seminar_head | self.seminar_head_id).update_seminar_head_role()
