# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_attendance_report_student(models.TransientModel):
	_name = "ims.attendance_report_student"
	_description = "Attendance report: by student."

	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	start_date = fields.Date(string="From", default=fields.Datetime.now, required=True) # TODO: get the first date possible (after student selection)
	end_date = fields.Date(string="To", default=fields.Datetime.now, required=True)		# TODO: get the last date possible (after student selection)
	
	@api.onchange("student_id")
	def _onchange_student_id(self):
		for rec in self:
			if rec.student_id.id != False:
				sessions = self.env["ims.attendance_status"].search([("student_id", "=", rec.student_id.id)]).mapped('attendance_session_id')
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				rec.start_date = first.date
				rec.end_date = last.date

	def print(self):
		# TODO: https://www.cybrosys.com/blog/how-to-create-pdf-report-in-odoo-16
		return false