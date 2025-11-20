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
	is_overriding = fields.Boolean(store=False)
	overrided_teachers = fields.Char(default="")

	@api.onchange("file")
	def _onchange_file(self):
		for rec in self:
			if rec.file:
				xml_content = base64.b64decode(rec.file)
				tree = ET.ElementTree(ET.fromstring(xml_content))
					
				root = tree.getroot()
				for teacherNode in root:					
					email = teacherNode.attrib['name'].split(' ')[0]
					teacher = self.env["hr.employee"].search([("work_email", "=", email)]) or False

					if teacher and teacher.resource_calendar_id.id:
						rec.is_overriding = True
						rec.overrided_teachers = teacher.display_name if not rec.overrided_teachers else "%s, %s" % (rec.overrided_teachers, teacher.display_name)						
	
	def import_planner_data(self):
		return {
			'type': 'ir.actions.client',
			'tag': 'soft_reload',
		}
	
	@api.model_create_multi
	def create(self, values):
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
					entries = self._create_schedule(teacherNode, teacher, current_course)
					teaching = self._create_teaching(entries, teacher, current_course)

		return super(models.Model, self).create(values)			

	def _create_schedule(self, xml_node, teacher, current_course):									
		schedule = teacher.resource_calendar_id
		if not teacher.resource_calendar_id.id:
			# TODO: add a relation to current_course
			schedule = self.env['resource.calendar'].create({
				'name': "%s (%s)" % (teacher.name, current_course.name),
				'full_time_required_hours': 24
			})
		
		entries = [[5]]	#5 means unlink all previus, because the created schedule has default entries attached.					
		for dayNode in xml_node:
			# NOTE: 0: Monday; 1: Tuesday as today.weekday() does.
			dayofweek = int(dayNode.attrib['name'].split(' ')[0]) - 1						
			start = None
			
			for hourNode in dayNode:
				if start is not None:
					close = hourNode.attrib['name'].split(' ')[1]
					entries.append([0, 0, {
						"name": "%s: %s (%s)" % (subject.acronym, subject.name, group.name),
						"dayofweek": str(dayofweek),
						"day_period": 'morning' if int(start[:2]) < 15 else 'afternoon',
						"hour_from": self._conv_time_float(start),
						"hour_to": self._conv_time_float(close),
						"subject_id": subject.id,
						"group_id": group.id
					}])
					start = None

				# NOTE: Ignore empty hours (lack of activities)
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
		
		schedule.write({ 'attendance_ids': entries })  		
		teacher.write({ "resource_calendar_id": schedule })
		return entries	

	def _create_teaching(self, entries, teacher, current_course):
		teaching = []		
		for t in teacher.teaching_ids:
			teaching.append([(2, t.id)]) #remove
				
		for e in entries[1:]: #skipping the first (unlink all)
			# TODO: asign also the current_course
			item = [0, 0, {
				'group_id': e[2]["group_id"],
				'subject_id': e[2]["subject_id"]
			}]

			if item not in teaching:
				teaching.append(item)
				
		teacher.write({
			'teaching_ids': teaching
<<<<<<< HEAD
		})	
		
		return teaching		
=======
		})			
>>>>>>> 89bbd0365850c2eb741ee75e91e3dca4a84cc454

	def _conv_time_float(self, value):
		# Source: https://www.odoo.com/es_ES/forum/ayuda-1/convert-hours-and-minute-into-float-value-168236
		vals = value.split(':')
		t, hours = divmod(float(vals[0]), 24)
		t, minutes = divmod(float(vals[1]), 60)				
		minutes = (minutes) / 60.0
		return hours + minutes