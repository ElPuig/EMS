# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_attendance_template(models.Model):
	_name = "ims.attendance_template"
	_description = "Attendance template: contains the basic attendance data (who teaches what, where and for whom)"

	# TODO: add a start_date and an end_date. It will be used to select the current data when creating a new session.
	start_date = fields.Date(string="Start date", required=True)
	end_date = fields.Date(string="End date", required=True)
	color = fields.Integer(string="Color", help="Field to store the color that will be used for calendar view")   

	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True, ondelete='cascade')
	level_id = fields.Many2one(string="Level", comodel_name="ims.level", required=True)
	study_id = fields.Many2one(string="Study", comodel_name="ims.study", domain="[('level_id', '=', level_id)]", required=True)
	group_id = fields.Many2one(string="Group", comodel_name="ims.group", domain="[('study_id', '=', study_id)]", required=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ims.subject", domain="[('study_ids', 'in', study_id)]", required=True)
	space_id = fields.Many2one(string="Space", comodel_name="ims.space", required=True)
	
	attendance_schedule_ids = fields.One2many(string="Sessions", comodel_name="ims.attendance_schedule", inverse_name="attendance_template_id")		
	
	student_ids = fields.Many2many(string="Students", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]") # TODO: autofill by group + subject | allow changes

	def _default_teacher_id(self):							
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	@api.depends('subject_id', 'group_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s (%s)" % (rec.subject_id.display_name, rec.group_id.name)

	@api.onchange("group_id")	
	def _onchange_group_id(self):		
		for rec in self:
			rec.space_id = rec.group_id.space_id

	@api.onchange("subject_id", "group_id")	
	def _fill_students(self):		
		for rec in self:						
			students = []
			for student in self.env['ims.enrollment'].search([('group_id', '=', rec.group_id.id), ('subject_id', '=', rec.subject_id.id)]).mapped('student_id'):
				students.append(student.id)

			rec.write({'student_ids' : [(6, 0, students)]})