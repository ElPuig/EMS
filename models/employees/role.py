# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from . import employee

# The 7 roles whose 'employee_ids' membership is derived entirely from department/company/
# group data (see 'ems_employee_base._ems_role_hierarchy_truth' and
# docs/en/developers/employees/role_hierarchy.md) - never a legitimate manual edit from this
# model's own 'employee_ids' reverse field, which none of the 5 internal update_*_role() sync
# methods ever write through (they always write hr.employee's own 'role_ids' instead).
HIERARCHY_MANAGED_ROLE_XMLIDS = (
	'ems.role_tutor', 'ems.role_dchieff', 'ems.role_seminar', 'ems.role_hos',
	'ems.role_dhos', 'ems.role_secretary', 'ems.role_director',
)


class EmsRole(models.Model):
	_name = "ems.role"
	_description = "Roles: The coordination position held by the employees."
	_inherit = ['ems.hex_color_mixin']
	_order = "name asc"

	name = fields.Char(string="Name", translate=True, required=True)
	color = fields.Char(string="Color", default="#3A8DDE")
	notes = fields.Text(string="Notes")
	unipersonal = fields.Boolean(string="Unipersonal", default=True)

	#The employee_ids field was a Many2one relation, but kanban view does not work within the form. It will be validated on the fly in order to limit to 1 assignation.
	#Note: manual relation is needed, otherwise Odoo creates two tables within the BBDD, one for 'hr.employee.public' and one for 'hr.employee.base'
	employee_type = fields.Selection(string="Employee Type", selection=employee.employee_types)
	employee_ids = fields.Many2many(string="Assigned to", comodel_name="hr.employee.public", relation="hr_employee_public_ems_role_rel", column1="ems_role_id", column2="hr_employee_public_id", domain="[('employee_type', '=', employee_type)]")
	group_id = fields.Many2one(string="Security Group", comodel_name="res.groups", help="If set, employees with this role will be automatically added to this security group.")
	is_hierarchy_managed = fields.Boolean(string="Hierarchy-managed", compute="_compute_hierarchy_managed", help="Assigned automatically from the department, company or group form - cannot be edited from this role's own record.")
	hierarchy_managed_message = fields.Char(string="Hierarchy-managed message", compute="_compute_hierarchy_managed")

	def _compute_hierarchy_managed(self):
		xmlid_by_id = {self.env.ref(xmlid).id: xmlid for xmlid in HIERARCHY_MANAGED_ROLE_XMLIDS}
		# One explanation per xmlid, naming the exact screen/field the change actually has to go
		# through (developer feedback, 2026-08-31: the generic "cannot be edited here" banner
		# didn't say how to make the change, and it differs per role).
		messages_by_xmlid = {
			'ems.role_tutor': _("This role is assigned automatically when a teacher is set as a group's Tutor (the group's own form)."),
			'ems.role_dchieff': _("This role is assigned automatically from the department's own form (Manager field)."),
			'ems.role_seminar': _("This role is assigned automatically from the department's own form (Seminar Chief field)."),
			'ems.role_hos': _("This role is assigned automatically from the top-level department's own form (Area Manager, with Role set to Head of Studies)."),
			'ems.role_dhos': _("This role is assigned automatically from the top-level department's own form (Area Manager, with Role set to Deputy Head of Studies)."),
			'ems.role_secretary': _("This role is assigned automatically from the top-level department's own form (Area Manager, with Role set to Secretary)."),
			'ems.role_director': _("This role is assigned automatically from Settings (EMS Management, Director field)."),
		}
		for role in self:
			xmlid = xmlid_by_id.get(role.id)
			role.is_hierarchy_managed = bool(xmlid)
			role.hierarchy_managed_message = messages_by_xmlid.get(xmlid, '')

	@api.constrains("employee_ids")
	def check_limit(self):
		for role in self:
			if role.unipersonal and len(role.employee_ids) > 1:
				raise ValidationError(_("This role is already assigned to another one."))

	@api.constrains("color")
	def _check_color_format(self):
		self._check_hex_color('color')

	def write(self, vals):
		if 'employee_ids' in vals and not self.env.context.get(employee.EMS_ROLE_SYNC_CONTEXT_KEY):
			if self.filtered(lambda role: role.is_hierarchy_managed):
				raise ValidationError(_(
					"This role's assignment is managed automatically from the department, "
					"company or group form and cannot be edited here."))
		return super().write(vals)
