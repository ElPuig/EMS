# -*- coding: utf-8 -*-

from odoo import models, fields

class EmsSpaceType(models.Model):
	_name = "ems.space_type"
	_inherit = ["ems.in_use_guard.mixin"]
	_description = "Space type: classroom, laboratory, etc."
	_order = "name"

	active = fields.Boolean(default=True)
	name = fields.Char(string="Name", translate=True, required=True)
	reservable = fields.Boolean(
		string="Reservable", default=True,
		help="Whether the spaces of this type can be reserved. Untick it for the types that are never reserved (WC...): they are not offered when searching for a space either.")
