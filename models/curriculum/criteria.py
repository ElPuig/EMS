# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ims_criteria(models.Model):
	_name = "ims.criteria"		
	_description = "Criteria: what the teacher should use in order to validate the student's learning outcome."
	_order = "code asc"
	_sql_constraints = [
		('unique_code', 'unique (criteria_id, code)', 'duplicated code!')
    ]

	code = fields.Char(string='Code', required=True)
	acronym = fields.Char(string="Acronym", required=True)
	name = fields.Char(string="Name", required=True)				
	outcome_id = fields.Many2one(string='Learning Outcome', comodel_name='ims.outcome', compute='_compute_outcome', store=True)
	notes = fields.Text(string="Notes")

	# The following fields are computed and used to display the data correctly within the treeview
	#level = fields.Integer(string="Level", default=1, compute="_compute_level", store=True)		
	level = fields.Integer(string="Level", default=1)	
	
	# Recursive criteria should be allowed? I guess it's better to avoid extra complexities...
	# criteria_ids = fields.One2many(string="Composite", comodel_name="ims.criteria", inverse_name="criteria_id")
	# criteria_id = fields.Many2one(string="Parent", comodel_name="ims.criteria")

	# @api.depends("criteria_id")
	# def _compute_level(self):
	# 	for rec in self:
	# 		if rec.criteria_id.id != False: rec.level = rec.criteria_id.level + 1 	
				
	# @api.depends("criteria_id")
	# def _compute_outcome(self):	  		      
	# 	for rec in self:
	# 		if rec.criteria_id.id != False: rec.outcome_id = rec.criteria_id.outcome_id
	# 		if rec.criteria_id.id != False: rec.level = rec.criteria_id.level + 1 
	
	@api.constrains('code')
	def _check_code(self):
		for rec in self:
			if rec.outcome_id.id != False: 
				if not rec.code.startswith(rec.outcome_id.code):
					raise ValidationError("The code must start as the parent's code.")
	
	@api.depends('acronym', 'name')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s: %s" % (rec.acronym, rec.name)

	def open_form(self):
		return {
            'name': '%s Edit' % self._description.split(':')[0],
			'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,						
            'view_id': self.env.ref('ims.view_%s_form' % (self._name.split('.')[1])).id,
            'view_mode': 'form',
			'target': 'new'
        }	