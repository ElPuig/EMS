# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_teaching(models.Model):
	_name = "ems.teaching"
	_description = "Teaching: ternary relation between teacher-group-subject."	
	_sql_constraints = [
		('ems_teaching_unique', 
		'unique(teacher_id, group_id, subject_id)',
		'The ternary "teacher / group / subject" must be unique!')
	]

	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", ondelete='cascade', required=True, domain="[('employee_type', '=', 'teacher')]")	
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", ondelete='cascade', required=True)	
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", ondelete='cascade', required=True)	
	
	# This field is used to filter the availabe groups within the view (avoiding the selection of repeated groups for the same subject in teaching form).
	# Note: compute_sudo is needed for read-only access.
	inuse_group_ids = fields.Many2many('ems.group', compute='_compute_inuse_group_ids', compute_sudo=True, store=False) 
	# this field is used to change the style of the row in the view
	level = fields.Integer(string="Level", related="subject_id.level", store=False)		
					
	@api.depends('subject_id')
	def _compute_inuse_group_ids(self):				
		for rec in self:
			groups = []		
			for tch in rec.teacher_id.teaching_ids:
				if tch.subject_id == rec.subject_id and tch.group_id.id != False: 
					groups.append(tch.group_id.id)
			rec.write({'inuse_group_ids' : [(6, 0, groups)]})
                	
	@api.depends('subject_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s" % rec.subject_id.display_name