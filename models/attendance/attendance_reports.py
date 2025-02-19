# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import status

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
		# query = """SELECT status.*, session.*  FROM ims_attendance_status AS status
		# 		LEFT JOIN res_partner AS student on student.id = status.student_id
		# 		LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
		# 		WHERE student.id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)

		query = """SELECT status.id FROM ims_attendance_status AS status
				LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
				WHERE status.student_id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)
								
		self.env.cr.execute(query)		
		status_ids = self.env.cr.dictfetchall()
		data = {'student_id': self.read()[0]['student_id'][0],'status_ids': list(map(lambda x:x['id'], status_ids))}

		return self.env.ref('ims.action_attendance_report_student').with_context(landscape=True).report_action(None, data=data)
	
class ims_attendance_report_student(models.AbstractModel):
	_name = 'report.ims.attendance_report_student'
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):        						
		#	Form content:
		#		Group by subject:
		#			Overall:
		#				- Amount of this item
		#				- Total items
		#				- % over total
		#
		# 			- List of the status entries with comments (abstract)
		# 			- List of all the status entries (list status by date)

		docs = self.env["res.partner"].browse(data['student_id'])		
		entries = self.env["ims.attendance_status"].browse(data['status_ids'])

		grp_by_subject = {}
		for s in entries:
			key = s.attendance_session_id.subject_id
			if not key in grp_by_subject: grp_by_subject[key] = []
			values = grp_by_subject[key]			
			values.append(s)					

		lines = {}	
		for subject in grp_by_subject:
			counters = {}
			comments = []
			entries = []
			for item in status:
				counters[item[0]] = 0
			for s in grp_by_subject[subject]:
				counters[s.status] += 1
				
				if s.notes != False: comments.append(s)
				entries.append(s)
			
			breakdown = {}
			total = len(grp_by_subject[subject])
			for entry in counters:
				breakdown[entry] = {
					'count' : counters[entry],
					'total' : total,
					'%'		: (counters[entry] / total) * 100
				}

			# Warning: this form has been designed to allow custom attendance status, BUT some native status (like 'attended') 
			# should be 'cooked' because 'delayed' or 'issue' means also 'attended', and 'missed' means also 'justified miss'. 
			# Overall data will be generated in order to mantain the original breakdown data.		

			# TODO: To improve customizations, everything can be considered as assistance except for miss + justified.
			#		Map the overall: miss + justified from one side, the rest in the other one. 

			attended = 	list(filter(lambda x: x[0] == 'attended', status))[0]
			miss = 	list(filter(lambda x: x[0] == 'miss', status))[0]
			overall = {
				attended : self._compute_overall(breakdown, total, ['attended', 'delayed', 'issue']),
				miss : self._compute_overall(breakdown, total, ['miss', 'justified'])
			}
						
			lines[subject] = {'overall' : overall, 'breakdown' : breakdown, 'comments' : comments, 'entries' : entries}		
		
		return {
			'doc_ids': docids,
			'doc_model': 'res.partner',
			'docs': docs,
			'lines': lines,
			'status': status
		}
	
	def _compute_overall(self, breakdown, total, status):
		overall = {
			'count' : 0,
			'total' : total,
			'%'		: 0
		}

		for s in status:
			overall['count'] += breakdown[s]['count']			
		
		overall['%'] = (overall['count'] / overall['total']) * 100
		return overall
		