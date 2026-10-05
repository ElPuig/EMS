# -*- coding: utf-8 -*-

from odoo import api, models

class ems_attachment(models.Model):
	_inherit = 'ir.attachment'

	def _ems_link_to(self, record):
		"""Ties the still unlinked attachments (res_id 0, as a form's many2many list or binary
		widget creates them) to `record`, so they follow its access rights: Odoo only lets the
		uploader, or a system admin, read an attachment without a res_id."""
		self.filtered(lambda attachment: not attachment.res_id).sudo().write({
			'res_model': record._name, 'res_id': record.id,
		})


class EmsAttachmentMixin(models.AbstractModel):
	"""For a model whose 'attachment_ids' many2many holds its own files, edited with the
	'ems_attachments' widget (upload, preview, download, delete): ties every file to its record,
	so it follows the record's access rights, and deletes a file once it is removed, since that
	widget offers no list of existing files to pick it back from. A file another record of the
	same model still holds (an official curriculum shared by several studies) is kept."""
	_name = 'ems.attachment_mixin'
	_description = 'EMS owned attachments'

	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)
		records._ems_link_attachments()
		return records

	def write(self, vals):
		if 'attachment_ids' not in vals:
			return super().write(vals)

		previous = {record: record.attachment_ids for record in self}
		res = super().write(vals)
		self._ems_link_attachments()

		removed = self.env['ir.attachment']
		for record, attachments in previous.items():
			removed |= (attachments - record.attachment_ids).filtered(
				lambda attachment: attachment.res_model == record._name and attachment.res_id == record.id)
		if removed:
			# sudo/active_test: a holder the user cannot read, or an archived one, still holds it.
			holders = self.sudo().with_context(active_test=False).search([('attachment_ids', 'in', removed.ids)])
			still_used = holders.attachment_ids.sudo(False)
			(removed - still_used).unlink()
		return res

	def _ems_link_attachments(self):
		for record in self:
			record.attachment_ids._ems_link_to(record)
