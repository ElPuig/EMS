# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_space_type(models.Model):
	_name = "ims.space_type"
	_description = "Space type: classroom, laboratory, etc."
		
	name = fields.Char(string="Name", required="true")

	#TODO: config page in facilities to manage this model