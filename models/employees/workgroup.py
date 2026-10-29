# -*- coding: utf-8 -*-

from odoo import api, fields, models

class EmsWorkgroup(models.Model):
	_name = "ems.workgroup"
	_description = "Workgroup: Employees (teachers, providers, and ASP) can define workgroups."
	_inherit = "ems.mine_first_mixin"
	_order = "name asc"

	name = fields.Char(string="Name", required=True)
	notes = fields.Text("Notes")

	#TODO: Many2many field does not display the "remove" button when a kanban card is clicked
	employee_ids = fields.Many2many(string="Members", comodel_name="hr.employee.public", relation="hr_employee_public_ems_workgroup_rel", column1="ems_workgroup_id", column2="hr_employee_public_id", domain="[('employee_type', '=', 'teacher')]")

	def write(self, vals):
		committee = self._ems_quality_committee() & self
		previous_users = committee.employee_ids.user_id if 'employee_ids' in vals else None
		result = super().write(vals)
		if previous_users is not None:
			self._ems_sync_quality_committee(left=previous_users - committee.employee_ids.user_id)
		return result

	def unlink(self):
		committee = self._ems_quality_committee() & self
		left = committee.employee_ids.user_id
		result = super().unlink()
		if committee:
			self._ems_sync_quality_committee(left=left)
		return result

	@api.model
	def _ems_my_ids(self):
		"""The workgroups the user is a member of."""
		return self.sudo().search([('employee_ids.user_id', '=', self.env.uid)]).ids

	@api.model
	def _ems_quality_committee(self):
		"""The quality committee: the catalogue's own 'Quality Comission' (ems.quality), the one
		workgroup whose members get the committee's access."""
		return self.env.ref('ems.quality', raise_if_not_found=False) or self.browse()

	@api.model
	def _ems_sync_quality_committee(self, left=None):
		"""Give the committee's members the committee's access (group_quality, the Quality menu),
		and take it from 'left', the users who just left the committee.

		Only users leaving the committee lose it, the same rule the role sync follows
		(hr.employee._sync_security_groups): someone given the group by hand from the user form
		without being a member is never touched, and quality coordination keeps it on leaving. Without 'left' it only adds, which is what every
		install and upgrade runs (data/main/sync_quality_committee.xml)."""
		group = self.env.ref('ems.group_quality').sudo()
		coordination = self.env.ref('ems.group_quality_admin')
		members = self._ems_quality_committee().sudo().employee_ids.user_id
		commands = [(4, user.id) for user in members - group.users]
		if left:
			leaving = (left - members) & group.users
			commands += [(3, user.id) for user in leaving if coordination not in user.groups_id]
		if commands:
			group.write({'users': commands})
