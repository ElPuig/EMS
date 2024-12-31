# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_space_type(models.Model):
	_name = "ems.space_type"
	_description = "Space type: classroom, laboratory, etc."
		
	name = fields.Char(string="Name", required=True)

	#TODO: config page in facilities to manage this model