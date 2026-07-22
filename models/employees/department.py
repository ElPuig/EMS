# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ems_department(models.Model):
    _name = "hr.department"
    _inherit = ["hr.department", "ems.hex_color_mixin"]

    custom_color = fields.Char(
        string="Color", default="#3A8DDE",
        help="Free-pick display color for this department (not Odoo's native, fixed-palette "
             "'Color' field, which the kanban view still uses internally).")
    seminar_chief_id = fields.Many2one(
        string="Seminar Chief", comodel_name="hr.employee",
        help="Every other member of this department (the Department Chief excluded) will have "
             "their Manager set to this employee; the Seminar Chief's own Manager is set to the "
             "Department Chief.")
    is_top_level = fields.Boolean(
        string="Top-level Department",
        help="A top-level department has no parent department and no Seminar Chief. Its Manager is "
             "labelled 'Area Manager' and automatically holds the role selected below (Head of "
             "Studies, Deputy Head of Studies or Secretary) instead of Department Chief.")
    top_level_area = fields.Selection(
        string="Area", selection=[('academic', 'Academic'), ('asp', 'ASP')],
        help="Only applies when this is a Top-level Department: which staff population this area "
             "covers - determines which Role is valid below (Academic -> Head of Studies/Deputy; "
             "ASP -> Secretary).")
    top_level_role = fields.Selection(
        string="Role",
        selection=[('hos', 'Head of studies'), ('dhos', 'Deputy head of studies'), ('secretary', 'Secretary')],
        help="Only applies when this is a Top-level Department: which position its Manager holds.")
    shares_manager_with_parent = fields.Boolean(
        string="Shares Manager with Parent",
        help="If set, this department has no Manager of its own - every member (and, if this "
             "department itself has children, their own Chief's Manager too) uses the nearest "
             "ancestor department's Manager instead, walking up the hierarchy until one is found.")

    @api.onchange('is_top_level')
    def _onchange_is_top_level(self):
        for department in self:
            if department.is_top_level:
                department.parent_id = False
                department.seminar_chief_id = False
                department.shares_manager_with_parent = False
            else:
                department.top_level_role = False
                department.top_level_area = False

    @api.onchange('shares_manager_with_parent')
    def _onchange_shares_manager_with_parent(self):
        for department in self:
            if department.shares_manager_with_parent:
                department.manager_id = False
                department.seminar_chief_id = False

    @api.constrains(
        'is_top_level', 'parent_id', 'seminar_chief_id', 'top_level_role', 'top_level_area',
        'shares_manager_with_parent', 'manager_id')
    def _check_top_level_fields(self):
        for department in self:
            if department.is_top_level:
                if department.parent_id:
                    raise ValidationError(_("A top-level department cannot have a parent department."))
                if department.seminar_chief_id:
                    raise ValidationError(_("A top-level department cannot have a Seminar Chief."))
                if department.shares_manager_with_parent:
                    raise ValidationError(_("A top-level department cannot share its Manager with a parent department."))
                if department.top_level_role in ('hos', 'dhos') and department.top_level_area != 'academic':
                    raise ValidationError(_("Head of Studies / Deputy Head of Studies can only be selected for an Academic top-level department."))
                if department.top_level_role == 'secretary' and department.top_level_area != 'asp':
                    raise ValidationError(_("Secretary can only be selected for an ASP top-level department."))
            else:
                if department.top_level_role:
                    raise ValidationError(_("Only a top-level department can have a Role selected."))
                if department.top_level_area:
                    raise ValidationError(_("Only a top-level department can have an Area selected."))
                if department.shares_manager_with_parent:
                    if not department.parent_id:
                        raise ValidationError(_("A department can only share its Manager with a parent department if it has one."))
                    if department.manager_id:
                        raise ValidationError(_("A department cannot have its own Manager and also share its Manager with its parent department."))

    @api.constrains("custom_color")
    def _check_custom_color_format(self):
        self._check_hex_color('custom_color')

    def _sanitize_top_level_vals(self, vals):
        if vals.get('is_top_level'):
            vals.setdefault('parent_id', False)
            vals.setdefault('seminar_chief_id', False)
            vals.setdefault('shares_manager_with_parent', False)
        elif vals.get('is_top_level') is False:
            vals.setdefault('top_level_role', False)
            vals.setdefault('top_level_area', False)
        if vals.get('shares_manager_with_parent'):
            vals.setdefault('manager_id', False)

    def _effective_manager(self):
        """Walks up the parent chain while shares_manager_with_parent is set, to find the actual
        Manager to use: the nearest ancestor's own manager_id, or the company's Director once a
        top-level department (which has no parent by definition) is reached with none of its own.
        Returns an empty recordset if a department along the way has neither its own Manager nor
        shares_manager_with_parent set (nothing to infer - left for an admin to configure).
        The 'seen' guard is defensive only: Odoo's own parent_id recursion constrain already
        prevents a genuine parent_id cycle through normal writes."""
        self.ensure_one()
        department = self
        seen = self.browse()
        while department and department.id not in seen.ids:
            seen |= department
            if department.manager_id:
                return department.manager_id
            if department.is_top_level:
                return department.company_id.director_id
            if not department.shares_manager_with_parent:
                return self.env['hr.employee']
            department = department.parent_id
        return self.env['hr.employee']

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
        old_heads = {department: (department.manager_id, department.seminar_chief_id) for department in self}
        res = super().write(vals)
        if {
            'manager_id', 'seminar_chief_id', 'parent_id', 'is_top_level', 'top_level_role',
            'shares_manager_with_parent',
        } & vals.keys():
            for department in self:
                old_manager, old_seminar_chief = old_heads[department]
                department._cascade_department_heads(old_manager, old_seminar_chief)
        return res

    def _cascade_department_heads(self, old_manager, old_seminar_chief):
        self.ensure_one()
        departments = self.search([('id', 'child_of', self.id)])
        employees = self.env['hr.employee'].search([
            '|', '|',
            ('department_id', 'in', departments.ids),
            ('headed_department_ids', 'in', departments.ids),
            ('seminar_department_ids', 'in', departments.ids),
        ])
        (employees | self.manager_id)._compute_parent_id()
        (old_manager | self.manager_id).update_department_head_role()
        (old_manager | self.manager_id).update_area_manager_role()
        (old_seminar_chief | self.seminar_chief_id).update_seminar_chief_role()
