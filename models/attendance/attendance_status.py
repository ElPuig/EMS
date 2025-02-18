# -*- coding: utf-8 -*-

from odoo import models, fields, api

status = [("attended", "Attended"), ("delayed", "Delayed"), ("miss", "Miss"), ("justified", "Justified Miss"), ("issue", "Issue")]

class ims_attendance_status(models.Model):
	_name = "ims.attendance_status"
	_description = "Attendance status: information about session per student."

	status = fields.Selection(string="Status", default="attended", required=True, selection=status)
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
	