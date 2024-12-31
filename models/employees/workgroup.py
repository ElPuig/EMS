# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_workgroup(models.Model):
	_name = "ems.workgroup"
	_description = "Workgroup: Employees (teachers, providers, and ASP) can define workgroups."
	
	name = fields.Char(string="Name", required=True)
	notes = fields.Text("Notes")

	#TODO: Many2many field does not display the "remove" button when a kanban card is clicked
	employee_ids = fields.Many2many(string="Members", comodel_name="hr.employee.public", relation="hr_employee_public_ems_workgroup_rel", column1="ems_workgroup_id", column2="hr_employee_public_id", domain="[('employee_type', '=', 'teacher')]")  

