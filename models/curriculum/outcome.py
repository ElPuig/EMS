# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class EmsOutcome(models.Model):
	_name = 'ems.outcome'
	_description = 'Learning outcome: what the student should learn.'
	_order = 'code asc'
	_sql_constraints = [
		('unique_code', 'unique (subject_id, code)', 'duplicated code!')
    ]

	code = fields.Char(string='Code', required=True)
	acronym = fields.Char(string='Acronym', required=True)
	name = fields.Char(string='Name', required=True)
	subject_id = fields.Many2one(string='Subject', comodel_name='ems.subject', required=True)
	criteria_ids = fields.One2many(string="Learning criteria", comodel_name="ems.criteria", inverse_name="outcome_id")
	notes = fields.Text(string='Notes')

	# Used to indent/style the treeview when this outcome's criteria are shown alongside it.
	level = fields.Integer(string="Level", default=1)

	@api.constrains('code')
	def _check_code(self):
		for outcome in self:
			if outcome.subject_id and not outcome.code.startswith(outcome.subject_id.code):
				raise ValidationError(_("The code must start as the subject's code."))

	@api.depends('acronym', 'name')
	def _compute_display_name(self):
		for outcome in self:
			outcome.display_name = "%s: %s" % (outcome.acronym, outcome.name)

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
