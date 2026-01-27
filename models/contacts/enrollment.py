# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class ems_enrollment(models.Model):
	_name = "ems.enrollment"
	_description = "Enrollment: ternary relation between student-group-uf."	
	_inherit = ['ems.base']
	
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", required=True, ondelete='cascade', domain="[('contact_type', '=', 'student')]")	
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", ondelete='cascade', required=True)	
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", ondelete='cascade', required=True)	
	
	#NOTE: this field is used to filter the availabe subjects within the view (avoiding the selection of repeated subject in enrolling form).
	inuse_subject_ids = fields.Many2many('ems.subject', compute='_compute_inuse_subject_ids', store=False) 	
	
	#NOTE: this field is used within ems.base.get_user_is_tutor, which is used to block the opening of the edit form if no permissions.
	#	   BUT, at this moment, only admins are allowed to create manual enrollments. 
	#tutor_id = fields.Many2one(string='Tutor', related="student_id.tutor_id")

	@api.model
	def default_get(self, fields_list):
		# TODO: unable to hide the "NEW" button based for only tutors...		
		res = super().default_get(fields_list)		
		if "user_is_admin" in fields_list:
			# This happens when opening the form, when storing fires again but field per field			
			if not (res["user_is_admin"]):
				# TODO: localize the message
				raise UserError("Only admins can create manual enrollments. If you're a group's tutor, you can enroll students using the student's form.")		
		return res
	
	@api.depends('student_id')
	def _compute_inuse_subject_ids(self):
		for rec in self:
			rec.inuse_subject_ids = False
			if rec.student_id:
				rec.inuse_subject_ids = rec.mapped('student_id.enrollment_ids.subject_id')
                	
	@api.depends('subject_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s" % rec.subject_id.display_name
	