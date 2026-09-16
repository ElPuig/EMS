# -*- coding: utf-8 -*-

from odoo import models, fields, api

class EmsSpace(models.Model):
	_name = "ems.space"
	_description = "Space: where each student group are assigned to."
	_inherit = ['mail.thread', 'mail.activity.mixin']
	_order = "name"
	_rec_names_search = ['name', 'code']
	_sql_constraints = [
		('unique_code', 'unique (work_location_id, code)', 'duplicated code!')
    ]

	code = fields.Char(string="Code", required=True)
	name = fields.Char(string="Name", required=True)
	space_type_id = fields.Many2one(
		string="Type", comodel_name="ems.space_type", required=True,
		default=lambda self: self.env.ref("ems.space_type_classroom", raise_if_not_found=False))
	work_location_id = fields.Many2one(
		string="Location", comodel_name="hr.work.location", required=True,
		default=lambda self: self.env.ref("ems.work_location_main", raise_if_not_found=False))

	@api.depends('name', 'code')
	def _compute_display_name(self):
		for space in self:
			space.display_name = f"{space.name} ({space.code})" if space.code else space.name

	def write(self, vals):
		res = super().write(vals)
		if vals.keys() & {'name', 'code'}:
			# Issue #453 - a group's public schedule PDF prints its blocks' rooms and its own reference classroom.
			Group = self.env['ems.group']
			Group._mark_public_schedule_dirty_for_blocks([('space_id', 'in', self.ids)])
			Group.sudo().search([('space_id', 'in', self.ids)])._mark_public_schedule_dirty()
		return res
