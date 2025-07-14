# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_attachment(models.Model):
	_inherit = 'ir.attachment'
	#_name = "ims.attachment"
	#_description = "Attachment file."
	
	# name = fields.Char(string="Name", required=True)
	# file = fields.Binary(string="File", required=True)
	# domain = fields.Char(string="Domain") # Used to filter the atachment by model, empty means "for all"

	def download(self):        
		return {
			'name': self.name,
			'type': 'ir.actions.act_url',
			'url': "web/content/?model=" + self._name +"&id=" + str(self.id) + "&filename_field=name&field=datas&download=true&filename=" + self.name,
			'target': 'self',
		}