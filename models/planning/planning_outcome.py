# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ems_planning_outcome(models.Model):
	_name = "ems.planning_outcome"
	_description = "Planning's outcome ponderation: self explanatory."

	planning_id = fields.Many2one(string="Planning", comodel_name="ems.planning", required=True, ondelete='cascade')
	outcome_id = fields.Many2one(string="Outcome", comodel_name="ems.outcome", required=True)
	ponderation = fields.Float(string="Ponderation (%)", required=True)
	valid_outcome_ids = fields.One2many('ems.outcome', related='planning_id.subject_id.outcome_ids', store=False) 	

	@api.constrains("ponderation")
	def check_ponderation(self):
		for rec in self:
			if rec.ponderation < 0 or rec.ponderation > 100:
				raise ValidationError("The ponderation value must be within the range [0,100].")