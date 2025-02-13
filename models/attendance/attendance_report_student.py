# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_attendance_report_student_wizard(models.TransientModel):
	_name = "ims.attendance_report_student_wizard"
	_description = "Attendance report wizard: by student."

	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)
	
	@api.onchange("student_id")
	def _onchange_student_id(self):
		for rec in self:
			if rec.student_id.id != False:
				sessions = self.env["ims.attendance_status"].search([("student_id", "=", rec.student_id.id)]).mapped('attendance_session_id')
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				rec.from_date = first.date
				rec.to_date = last.date

	def print(self):
		query = """SELECT status.*, session.*  FROM ims_attendance_status AS status
				LEFT JOIN res_partner AS student on student.id = status.student_id
				LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
				WHERE student.id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)
		
		self.env.cr.execute(query)
		lines = self.env.cr.dictfetchall()
		data = {'student': self.student_id, 'lines': lines}

		return self.env.ref('ims.report_attendance_student').report_action([self.student_id.id], data=data)
	
class ims_attendance_report_student(models.AbstractModel):
	_name = 'report.ims.attendance_report_student'
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):        
		report = self.env['ir.actions.report']._get_report_from_name('ims.attendance_report_student')
		# get the records selected for this rendering of the report
		#docs = self.env[report.model].browse(docids)
		docs = self.env[report.model].browse(docids)
		# docs = self.env[truck.booking].browse(docids)
		# return {
		#     'lines': docids.get_lines()
		# }
		return {
			'doc_ids': docids,
			'doc_model': 'res.partner',
			'docs': docs,
			'data': data,
		}