# -*- coding: utf-8 -*-

from odoo import models

class ems_attachment(models.Model):
	_inherit = 'ir.attachment'

	def download(self):        
		return {
			'name': self.name,
			'type': 'ir.actions.act_url',
			'url': "web/content/?model=" + self._name +"&id=" + str(self.id) + "&filename_field=name&field=datas&download=true&filename=" + self.name,
			'target': 'self',
		}

	def _ems_link_to(self, record):
		"""Ties the still unlinked attachments (res_id 0, as a form's many2many list or binary
		widget creates them) to `record`, so they follow its access rights: Odoo only lets the
		uploader, or a system admin, read an attachment without a res_id."""
		self.filtered(lambda attachment: not attachment.res_id).sudo().write({
			'res_model': record._name, 'res_id': record.id,
		})