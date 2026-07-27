# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class EmsCriteria(models.Model):
	_name = "ems.criteria"
	_description = "Criteria: what the teacher should use in order to validate the student's learning outcome."
	_order = "code asc"
	_sql_constraints = [
		('unique_code', 'unique (code)', 'duplicated code!')
    ]

	code = fields.Char(string='Code', required=True)
	acronym = fields.Char(string="Acronym", required=True)
	name = fields.Char(string="Name", required=True)
	outcome_id = fields.Many2one(string='Learning Outcome', comodel_name='ems.outcome', required=True)
	notes = fields.Text(string="Notes")

	# Used to indent/style the treeview when this criteria's outcome is shown alongside it.
	level = fields.Integer(string="Level", default=1)

	@api.constrains('code')
	def _check_code(self):
		for criteria in self:
			if criteria.outcome_id and not criteria.code.startswith(criteria.outcome_id.code):
				raise ValidationError(_("The code must start as the parent's code."))

	@api.depends('acronym', 'name')
	def _compute_display_name(self):
		for criteria in self:
			criteria.display_name = "%s: %s" % (criteria.acronym, criteria.name)

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
