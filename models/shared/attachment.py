# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_attachment(models.Model):
	_inherit = 'ir.attachment'

	def download(self):        
		return {
			'name': self.name,
			'type': 'ir.actions.act_url',
			'url': "web/content/?model=" + self._name +"&id=" + str(self.id) + "&filename_field=name&field=datas&download=true&filename=" + self.name,
			'target': 'self',
		}