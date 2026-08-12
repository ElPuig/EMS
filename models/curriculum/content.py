# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class EmsContent(models.Model):
	_name = "ems.content"
	_description = "Content: what the student should work on."
	_order = "code asc"
	_sql_constraints = [
		('unique_code', 'unique (subject_id, code)', 'duplicated code!')
    ]

	code = fields.Char(string="Code", required=True)
	acronym = fields.Char(string="Acronym", required=True)
	name = fields.Char(string="Name", required=True)
	content_ids = fields.One2many(string="Composite", comodel_name="ems.content", inverse_name="content_id")
	content_id = fields.Many2one(string="Parent", comodel_name="ems.content")
	subject_id = fields.Many2one(string='Subject', comodel_name='ems.subject', compute='_compute_subject', store=True, recursive=True)
	notes = fields.Text(string="Notes")

	# Root content items (content_id is empty) get their subject_id from the
	# default_subject_id context when created from a subject's Content tab, not from this
	# compute — only nested composites (added from a content's own Composite tab) derive
	# subject_id/level from their parent here. level shares subject_id's compute method
	# (rather than declaring its own) so reading level alone reliably triggers it too —
	# without this, a nested item's level silently stayed at the default until something
	# else happened to read subject_id first.
	level = fields.Integer(string="Level", default=1, compute='_compute_subject', store=True, recursive=True)

	@api.depends("content_id", "content_id.subject_id", "content_id.level")
	def _compute_subject(self):
		for content in self:
			if content.content_id:
				content.subject_id = content.content_id.subject_id
				content.level = content.content_id.level + 1

	@api.constrains('code')
	def _check_code(self):
		for content in self:
			if content.content_id and not content.code.startswith(content.content_id.code):
				raise ValidationError(_("The code must start as the parent's code."))

	@api.depends('acronym', 'name')
	def _compute_display_name(self):
		for content in self:
			content.display_name = "%s: %s" % (content.acronym, content.name)

	def open_form(self):
		return {
            'name': _("%s Edit") % self._description.split(':')[0],
			'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_id': self.env.ref('ems.view_%s_form' % (self._name.split('.')[1])).id,
            'view_mode': 'form',
			'target': 'new'
        }
