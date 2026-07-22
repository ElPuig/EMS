# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from . import employee

COLOR_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

class ems_role(models.Model):
	_name = "ems.role"
	_description = "Roles: The coordination position held by the employees."

	name = fields.Char(string="Name", translate=True, required=True)
	color = fields.Char(string="Color", default="#3A8DDE")
	notes = fields.Text(string="Notes")
	unipersonal = fields.Boolean(string="Unipersonal", default=True)
	
	#The employee_ids field was a Many2one relation, but kanban view does not work within the form. It will be validated on the fly in order to limit to 1 assignation.
	#Note: manual relation is needed, otherwise Odoo creates two tables within the BBDD, one for 'hr.employee.public' and one for 'hr.employee.base' 
	employee_type = fields.Selection(string="Employee Type", selection=employee.employee_types)
	employee_ids = fields.Many2many(string="Assigned to", comodel_name="hr.employee.public", relation="hr_employee_public_ems_role_rel", column1="ems_role_id", column2="hr_employee_public_id", domain="[('employee_type', '=', employee_type)]")
	group_id = fields.Many2one(string="Security Group", comodel_name="res.groups", help="If set, employees with this role will be automatically added to this security group.")

	@api.constrains("employee_ids")
	def check_limit(self):
		for rec in self:
			if rec.unipersonal and len(rec.employee_ids) > 1:
				raise ValidationError("This role is already assigned to another one.")

	@api.constrains("color")
	def _check_color_format(self):
		for rec in self:
			if rec.color and not COLOR_HEX_RE.match(rec.color):
				raise ValidationError(_("Color must be a hexadecimal code (e.g. #3A8DDE)."))