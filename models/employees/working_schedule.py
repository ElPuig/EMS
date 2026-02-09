# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
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

	non_teaching_selection=[
		("AC", "Another Coordinations"),
		("CM", "Coordination Meeting"),
		("CT", "Coordination Time"),
        ("G", "Guard"),
        ("MT", "Management Time"),
        ("R", "Reduction"),
		("S", "Staying at the center"),
		("SC", "School Council"),
        ("TT", "Tutorship Time"),
		("WIC", "Workplace Intership Coordination"),
    ]

	non_teaching = fields.Selection(string="Non-teaching", selection=non_teaching_selection)
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
		course_id = self.env.company.current_course_id
		if not course_id.id:
			raise ValidationError("No 'current course' has been setup. Please, select or create the current course within the EMS settings section.")
		
		for item in values:
			if 'file' not in item or not item.get('file'):
				raise ValidationError("No XML file has been loaded. Please, provide an XML file and try again.")
			else:	
				file = item.get('file')
				xml_content = base64.b64decode(file)
				tree = ET.ElementTree(ET.fromstring(xml_content))
				
				root = tree.getroot()
				for node in root:	
					email = node.attrib['name'].split(' ')[0]
					teacher = self.env["hr.employee"].search([("work_email", "=", email)])	
					if not teacher.id: raise ValidationError("Teacher with email '%s' not found." % email)

					entries = self._create_schedule(node, teacher, course_id)
					# TODO: uncomment this once the items being archive instead of deleted on recreation.
					#self._create_teaching(entries, teacher, course_id)
					#self._create_assitance_templates(entries, teacher, course_id)

		return super(models.Model, self).create(values)			

	def _create_schedule(self, xml_node, teacher, course_id):									
		name = "%s (%s)" % (teacher.name, course_id.name)
		schedule = self.env['resource.calendar'].search([('name', '=', name)]) or False
		non_teaching_items = dict(ems_working_schedule_assignation.non_teaching_selection)

		if not schedule:
			# TODO: add a relation to current_course
			schedule = self.env['resource.calendar'].create({
				'name': "%s (%s)" % (teacher.name, course_id.name),
				'full_time_required_hours': 24
			})
		
		entries = [[5]]	#5 means unlink all previus, because the created schedule has default entries attached.	Items will be removed if became orphan.				
		for dayNode in xml_node:
			# NOTE: 0: Monday; 1: Tuesday as today.weekday() does.
			dayofweek = int(dayNode.attrib['name'].split(' ')[0]) - 1						
			start = None
			
			for hourNode in dayNode:
				if start is not None:
					close = hourNode.attrib['name'].split(' ')[1]
					new_entry = {						
						"dayofweek": str(dayofweek),
						"day_period": 'morning' if int(start[:2]) < 15 else 'afternoon',
						"hour_from": self._conv_time_float(start),
						"hour_to": self._conv_time_float(close),						
					}

					if not non_teaching_id:
						new_entry["name"] = "%s: %s (%s)" % (subject.acronym, subject.name, group.name)
						new_entry["subject_id"] = subject.id
						new_entry["group_id"] = group.id
						new_entry["non_teaching"] = False				
					else:
						new_entry["name"] = "%s: %s" % (non_teaching_id, non_teaching_items[non_teaching_id])
						new_entry["subject_id"] = False
						new_entry["group_id"] = False
						new_entry["non_teaching"] = non_teaching_id

					entries.append([0, 0, new_entry])
					start = None

				# NOTE: Ignore empty hours (lack of activities)
				id = None
				non_teaching = False
				for content in hourNode:
					if content.tag == 'Activity':
						id = content.attrib['id'].split(' ')[0]
					elif content.tag == 'NonTeaching':
						non_teaching = True
						id = content.attrib['name'].split(' ')[0]
					elif content.tag == 'Subject':
						subjectCode = content.attrib['name'].split(' ')[0]
					elif content.tag == 'Students':
						groupAcro = content.attrib['name'].split(' ')[0]														
				
				if id is not None:
					start = hourNode.attrib['name'].split(' ')[1]
					if non_teaching:
						if not id in non_teaching_items: raise ValidationError("Non-Teaching with code '%s' not found." % id)
						non_teaching_id = id
						subject = False
						group = False
					else:
						subject = self.env["ems.subject"].search([("code", "=", subjectCode[2:])])
						group = self.env["ems.group"].search([("name", "=", groupAcro)])	
						non_teaching_id = False					
						if not subject.id: raise ValidationError("Subject with code '%s' not found." % subjectCode[2:])
						if not group.id: raise ValidationError("Group with acronym '%s' not found." % groupAcro[2:])
												
		schedule.write({ 'attendance_ids': entries })  		
		teacher.write({ "resource_calendar_id": schedule })
		return [x[2] for x in entries[1:]] #skipping the first (unlink all) and getting only entities.	

	def _create_teaching(self, entries, teacher, course_id):
		teaching = [[5]] #5 means unlink all previus, because the created schedule has default entries attached.	Items will be removed if became orphan.		
		
		for e in entries: #skipping the first (unlink all)
			# TODO: asign also the current_course
			item = [0, 0, {
				'group_id': e["group_id"],
				'subject_id': e["subject_id"]
			}]

			if item not in teaching:
				teaching.append(item)
				
		teacher.write({
			'teaching_ids': teaching
		})	
	
	def _create_assitance_templates(self, entries, teacher, course_id):
		# TODO: It's necessary to know if a template has been created automatically or manually? 
		# 		Should we keep the manually created? If so, additional checks are needed in order to create
		#		the entries avoiding duped templates... 		
		color = 1
		templates = dict()
		now = datetime.now()		

		for e in entries:
			key = "%s.%s" % (e["subject_id"], e["group_id"])
			if key in templates:
				t = templates[key]
			else:
				# TODO: define default start and end date for subjects within settings.			
				#t = self.env['ems.attendance_template'].create({
				group_id = self.env['ems.group'].search([('id', '=', e["group_id"])]) or False
				t = {
					'start_date': datetime(now.year, 9, 1),
					'end_date': datetime(now.year+1, 7, 1),
					'color': color,
					'teacher_id': teacher.id,
					'subject_id': e["subject_id"],
					'group_id': e["group_id"],
					'level_id': group_id.level_id.id,
					'study_id': group_id.study_id.id,
					'space_id': group_id.space_id.id,
					'attendance_schedule_ids': []
				}
				color += 1
				templates[key] = t
			
			t["attendance_schedule_ids"].append(
				[0, 0, {
					'start_time': e["hour_from"],
					'end_time': e["hour_to"],
					'weekday': e["dayofweek"],
					'space_id': t["space_id"]
				}]
			)
		
		self.env['ems.attendance_template'].search([('teacher_id', '=', teacher.id)]).unlink()
		for t in templates:
			self.env['ems.attendance_template'].create(templates[t])		

	def _conv_time_float(self, value):
		# Source: https://www.odoo.com/es_ES/forum/ayuda-1/convert-hours-and-minute-into-float-value-168236
		vals = value.split(':')
		t, hours = divmod(float(vals[0]), 24)
		t, minutes = divmod(float(vals[1]), 60)				
		minutes = (minutes) / 60.0
		return hours + minutes