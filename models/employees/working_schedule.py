# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
import xml.etree.ElementTree as ET
import base64


class ims_working_schedule(models.Model):
	_inherit = 'resource.calendar'

	def action_import_planner_data(self):
		raise ValidationError("HOLA")

class ims_working_schedules_import_wizard(models.TransientModel):
	_name = "ims.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."

	attachment_id = fields.Many2one(string="Attachment", comodel_name="ir.attachment", domain="[('res_model', '=', 'ims.working_schedules_import_wizard')]")
	file = fields.Binary(string="Planner file (XML)", related="attachment_id.datas")

	def import_planner_data(self):	
		for rec in self:			
			raise ValidationError("HOLA")
		
	@api.model_create_multi
	def create(self, values):
		for item in values:
			if 'file' not in item or not item.get('file'):
				raise ValidationError("No XML file has been loaded. Please, provide an XML file and try again.")
			else:				
				file = item.get('file')
				xml_content = base64.b64decode(file)
				tree = ET.ElementTree(ET.fromstring(xml_content))
				
				root = tree.getroot()
				for teacherNode in root:					
					email = teacherNode.attrib['name'].split(' ')[0]
					teacher = self.env["hr.employee"].search([("work_email", "=", email)])
					schedule = self.env['resource.calendar'].create({
						'name': "%s (%s-%s)" % (teacher.name, datetime.now().year, datetime.now().year+1) # TODO: get the current course data when defined in settings.						
					})
					entries = []
					
					for dayNode in teacherNode:
						# 0: Monday; 1: Tuesday as today.weekday() does.
						dayofweek = int(dayNode.attrib['name'].split(' ')[0]) - 1						
						start = None
						
						for hourNode in dayNode:
							if start is not None:
								close = hourNode.attrib['name'].split(' ')[1]
								day_period = 'morning' if int(start[:2]) < 15 else 'afternoon'

								# TODO: add the subject and group entieies
								entries.append([0, 0, {
                                    "name": "%s: %s (%s)" % (subject.acronym, subject.name, group.name),
                                    "dayofweek": str(dayofweek),
                                    "day_period": day_period,
									"hour_from": self._conv_time_float(start),
									"hour_to": self._conv_time_float(close,1)
                                }])
								start = None

							# Ignore empty hours (lack of activities)
							id = None
							for content in hourNode:
								if content.tag == 'Activity':
									id = content.attrib['id'].split(' ')[0]
								elif content.tag == 'Subject':
									subjectCode = content.attrib['name'].split(' ')[0]
								elif content.tag == 'Students':
									groupAcro = content.attrib['name'].split(' ')[0]														
							
							if id is not None:
								subject = self.env["ims.subject"].search([("code", "=", subjectCode[2:])])
								group = self.env["ims.group"].search([("name", "=", groupAcro)])
								start = hourNode.attrib['name'].split(' ')[1]
					
					schedule.write({
						'attendance_ids': entries
					})  

		return None
				
	def _conv_time_float(self, value, offset=0):
		# Source: https://www.odoo.com/es_ES/forum/ayuda-1/convert-hours-and-minute-into-float-value-168236
		vals = value.split(':')
		t, hours = divmod(float(vals[0]), 24)
		t, minutes = divmod(float(vals[1]), 60)
		
		if offset > 0:
			if minutes == 0:
				minutes = 59
				hours -= 1
			else:
				minutes -= 1
		
		minutes = (minutes) / 60.0
		return hours + minutes