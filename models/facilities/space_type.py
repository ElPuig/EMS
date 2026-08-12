# -*- coding: utf-8 -*-

from odoo import models, fields

class EmsSpaceType(models.Model):
	_name = "ems.space_type"
	_description = "Space type: classroom, laboratory, etc."
	_order = "name"

	name = fields.Char(string="Name", required=True)