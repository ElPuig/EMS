# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_teaching(models.Model):
	_name = "ims.teaching"
	_description = "Teaching: ternary relation between teacher-group-uf."	
	_sql_constraints = [
		('ims_teaching_unique', 
		'unique(teacher_id, group_id, subject_id)',
		'The ternary "teacher / group / subject" must be unique!')
	]

	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, domain="[('employee_type', '=', 'teacher')]")	
	group_id = fields.Many2one(string="Group", comodel_name="ims.group", required=True)	
	subject_id = fields.Many2one(string="Subject", comodel_name="ims.subject", required=True)	
	
	# this field is used to filter the availabe groups within the view (avoiding the selection of repeated groups for the same subject in teaching form).
	inuse_group_ids = fields.Many2many('ims.group', compute='_compute_inuse_group_ids', store=False) 
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