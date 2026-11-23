# -*- coding: utf-8 -*-

import os

from odoo import api, models
from odoo.tools.mimetypes import guess_mimetype

# Files that are never compressed: what the system itself generates or ships (views, reports, the
# email being sent) and what the centre downloads as a template. image.mixin's resized copies
# (res_field 'image_*') are skipped too: Odoo already resizes them, and compressing each one would
# make the others recompute.
COMPRESSION_EXCLUDED_MODELS = ('ir.ui.view', 'ir.actions.report', 'mail.mail', 'mail.compose.message', 'ems.signed.record')
COMPRESSION_EXCLUDED_FIELDS = (('ems.erasmus.call', 'template_file'),)
COMPRESSION_MIN_KB_PARAM = 'ems.compress_min_kb'
COMPRESSION_MIN_KB_DEFAULT = 300


class ems_attachment(models.Model):
	_inherit = 'ir.attachment'

	@api.model_create_multi
	def create(self, vals_list):
		attachments = super().create(vals_list)
		attachments._ems_queue_compression()
		return attachments

	def write(self, vals):
		res = super().write(vals)
		if vals.keys() & {'raw', 'datas'}:
			self._ems_queue_compression()
		return res

	def _ems_compression_candidates(self):
		"""The files of `self` worth compressing: a stored PDF or JPEG/PNG over the size threshold
		that nothing excludes. Cheap checks only, on the row: nothing is read from the filestore."""
		if self.env.context.get('ems_no_compress'):
			return self.browse()
		minimum = int(self.env['ir.config_parameter'].sudo().get_param(
			COMPRESSION_MIN_KB_PARAM, COMPRESSION_MIN_KB_DEFAULT)) * 1024
		compression = self.env['ems.file_compression']
		return self.filtered(lambda attachment:
			attachment.type == 'binary' and attachment.file_size > minimum
			and compression.can_compress(attachment.mimetype)
			and attachment.res_model not in COMPRESSION_EXCLUDED_MODELS
			and (attachment.res_model, attachment.res_field) not in COMPRESSION_EXCLUDED_FIELDS
			and not (attachment.res_field or '').startswith('image_'))

	def _ems_queue_compression(self):
		"""Compressing a scan takes seconds: it never runs inside the user's request, the file is
		stored as uploaded and a background job (queue_job) replaces it when it is done."""
		for attachment in self._ems_compression_candidates():
			attachment.with_delay(identity_key=f"ems_compress_{attachment.id}",
				description=f"Compress file: {attachment.name}")._ems_compress()

	def _ems_compress(self):
		"""Replaces the file by its compressed version when that saves enough (see
		ems.file_compression). The original is not kept."""
		self.ensure_one()
		if not self._ems_compression_candidates():
			return False
		raw = self.raw
		result = self.env['ems.file_compression'].compress(raw, self.mimetype)
		if not result:
			return False
		vals = {'raw': result}
		mimetype = guess_mimetype(result)
		if mimetype != self.mimetype:
			# A PNG stored as JPEG: its name and type follow.
			vals.update(mimetype=mimetype, name=f"{os.path.splitext(self.name)[0]}.jpg")
		self.sudo().with_context(ems_no_compress=True).write(vals)
		return True

	def _ems_link_to(self, record):
		"""Ties the still unlinked attachments (res_id 0, as a form's many2many list or binary
		widget creates them) to `record`, so they follow its access rights: Odoo only lets the
		uploader, or a system admin, read an attachment without a res_id."""
		self.filtered(lambda attachment: not attachment.res_id).sudo().write({
			'res_model': record._name, 'res_id': record.id,
		})


class EmsAttachmentLinkMixin(models.AbstractModel):
	"""For a model whose 'attachment_ids' many2many holds its own files (a many2many_binary widget
	uploads them before the record is saved, with no res_id, and Odoo then only lets the uploader
	read them): ties every file to its record, so it follows the record's access rights. A file
	removed from the record is kept (it may be evidence); ems.attachment_mixin also deletes it."""
	_name = 'ems.attachment_link_mixin'
	_description = 'EMS attachments linked to their record'

	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)
		records._ems_link_attachments()
		return records

	def write(self, vals):
		res = super().write(vals)
		if 'attachment_ids' in vals:
			self._ems_link_attachments()
		return res

	def _ems_link_attachments(self):
		for record in self:
			record.attachment_ids._ems_link_to(record)


class EmsAttachmentMixin(models.AbstractModel):
	"""For a model whose 'attachment_ids' many2many holds its own files, edited with the
	'ems_attachments' widget (upload, preview, download, delete): ties every file to its record,
	so it follows the record's access rights, and deletes a file once it is removed, since that
	widget offers no list of existing files to pick it back from. A file another record of the
	same model still holds (an official curriculum shared by several studies) is kept."""
	_name = 'ems.attachment_mixin'
	_description = 'EMS owned attachments'
	_inherit = ['ems.attachment_link_mixin']

	def write(self, vals):
		if 'attachment_ids' not in vals:
			return super().write(vals)

		previous = {record: record.attachment_ids for record in self}
		res = super().write(vals)

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
