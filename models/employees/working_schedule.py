# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import xml.etree.ElementTree as ET
import base64


class ems_working_schedule(models.Model):
	_inherit = 'resource.calendar'
	_sql_constraints = [
		('unique_name', 'unique (name)', 'duplicated calendar!')
    ]

class ems_working_schedule_assignation(models.Model):
	_inherit = 'resource.calendar.attendance'
	# NOTE: no need to constraint, the main model avoids overlapping. 

	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
	group_id = fields.Many2one(string="Group", comodel_name="ems.group")


class ems_working_schedules_import_wizard(models.TransientModel):
	_name = "ems.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."

	attachment_id = fields.Many2one(string="Attachment", comodel_name="ir.attachment", domain="[('res_model', '=', 'ems.working_schedules_import_wizard')]")
	file = fields.Binary(string="Planner file (XML)", related="attachment_id.datas")	

	def import_planner_data(self):
		return {
			'type': 'ir.actions.client',
			'tag': 'soft_reload',
		}
	
	@api.model_create_multi
	def create(self, values):
		data = []
		course_id =  self.env['ir.config_parameter'].sudo().get_param('ems.course_id')
		current_course = self.env["ems.course"].search([("id", "=", course_id)])
		
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
						'name': "%s (%s)" % (teacher.name, current_course.name),
						'full_time_required_hours': 24
					})
					entries = [[5]]	#5 means unlink all previus, because the created schedule has default entries attached.
					data.append(schedule)						

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
									"hour_to": self._conv_time_float(close),
									"subject_id": subject.id,
									"group_id": group.id
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
								subject = self.env["ems.subject"].search([("code", "=", subjectCode[2:])])
								group = self.env["ems.group"].search([("name", "=", groupAcro)])
								start = hourNode.attrib['name'].split(' ')[1]
					
					schedule.write({
						'attendance_ids': entries
					})  
					
					teacher.write({
						"resource_calendar_id": schedule
					})		
		return super(models.Model, self).create(values)			
				
	def _conv_time_float(self, value):
		# Source: https://www.odoo.com/es_ES/forum/ayuda-1/convert-hours-and-minute-into-float-value-168236
		vals = value.split(':')
		t, hours = divmod(float(vals[0]), 24)
		t, minutes = divmod(float(vals[1]), 60)				
		minutes = (minutes) / 60.0
		return hours + minutes