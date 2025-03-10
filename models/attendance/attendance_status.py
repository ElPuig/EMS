# -*- coding: utf-8 -*-

from odoo import models, fields, api

# NOTE: In order to allow customization (like adding new status types), status starting with 'a_' will be 
#		computed as an 'attendance' snd starting with 'm_' as a 'm_miss' when reporting summary data.
attendance_status = [("a_attended", "Attended"), ("a_delayed", "Delayed"), ("m_miss", "Miss"), ("m_justified", "Justified Miss"), ("a_issue", "Issue")]

class ims_attendance_status(models.Model):
	_name = "ims.attendance_status"
	_description = "Attendance status: information about session per student."

	status = fields.Selection(string="Status", default="a_attended", required=True, selection=attendance_status)
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	image_1920 = fields.Binary(string="Image", related='student_id.image_1920')
	attendance_session_id = fields.Many2one(string="Session", comodel_name="ims.attendance_session")
	notes = fields.Text("Notes")

	# this field is used to filter the availabe students within the view (avoiding the selection of repeated students on attendance session form).
	inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 

	@api.depends('attendance_session_id')
	def _compute_inuse_student_ids(self):
		for rec in self:
			rec.inuse_student_ids = False
			if rec.attendance_session_id:
				rec.inuse_student_ids = rec.mapped('attendance_session_id.attendance_status_ids.student_id')
	
	def report_eval(self, field):
		# Note: this is used within the 'details_table' template in order to render custom fields.		
		return eval(field)