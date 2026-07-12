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

	def apply_schedule_changes(self, cells):
		"""Replace this calendar's weekday (Mon-Fri) attendances with 'cells' (called from the
		'Schedule' tab's grid widget, whose buffer already represents the full weekly state), then
		re-derive the teacher's 'teaching_ids' from the same cells so both stay in sync."""
		self.ensure_one()
		self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4')).unlink()
		self.write({'attendance_ids': [(0, 0, cell) for cell in cells]})

		teacher = self.env['hr.employee'].search([('resource_calendar_id', '=', self.id)])
		if teacher:
			entries = [cell for cell in cells if cell.get('subject_id')]
			self.env['ems.teaching'].sync_from_schedule(teacher, entries)

class ems_working_schedule_assignation(models.Model):
	_inherit = 'resource.calendar.attendance'
	# NOTE: no need to constraint, the main model avoids overlapping. 

	non_teaching_selection=[
		("AC", "Another Coordinations"),
		("CM", "Coordination Meeting"),
		("CT", "Coordination Time"),
        ("G", "Guard"),
		("MM", "Management Meeting"),
        ("MT", "Management Time"),
        ("R", "Reduction"),
		("S", "Staying at the center"),
		("SC", "School Council"),
        ("TT", "Tutorship Time"),
		("WIC", "Workplace Intership Coordination"),
    ]

	non_teaching = fields.Selection(string="Non-teaching", selection=non_teaching_selection)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group")
	# NOTE: the classroom is a property of the group (ems.group.space_id), same simplification already
	# used by 'ems.attendance_template' (first selected group wins when several are assigned).
	space_id = fields.Many2one(string="Classroom", comodel_name="ems.space", compute="_compute_space_id", store=True)

	@api.depends("group_ids", "group_ids.space_id")
	def _compute_space_id(self):
		for attendance in self:
			attendance.space_id = attendance.group_ids[:1].space_id

class ems_working_schedules_import_wizard(models.TransientModel):
	_name = "ems.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."
	_inherit = ['ems.datetime_utils']

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
					entries = [e for e in entries if not e["non_teaching"]]
					self.env['ems.teaching'].sync_from_schedule(teacher, entries)
					self._create_assitance_templates(entries, teacher, course_id)

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
		
		entries = []
		attendance_ids = [[5]]
		for dayNode in xml_node:
			# NOTE: 0: Monday; 1: Tuesday as today.weekday() does.			
			dwe = []
			dayofweek = int(dayNode.attrib['name'].split(' ')[0]) - 1			

			for hourNode in dayNode:	
				acronyms = []						
				start = hourNode.attrib['name'].split(' ')[1]				
				new_entry = {						
					"dayofweek": str(dayofweek),
					"day_period": 'morning' if int(start[:2]) < 15 else 'afternoon',
					"hour_from": self.time_string_to_float(start),
					"hour_to": None,
				}

				for content in hourNode:
					if content.tag == 'NonTeaching':
						id = content.attrib['name'].split(' ')[0]						
						new_entry["name"] = "%s: %s" % (id, non_teaching_items[id])
						new_entry["subject_id"] = False
						new_entry["group_ids"] = [(6, 0, [])]
						new_entry["non_teaching"] = id	
						
					elif content.tag == 'Subject':
						code = content.attrib['name'].split(' ')[0]
						subject = self.env["ems.subject"].search([("code", "=", code)])
						if not subject.id: raise ValidationError("Subject with code '%s' not found." % code)

						new_entry["name"] = "%s: %s" % (subject.acronym, subject.name)
						new_entry["subject_id"] = subject.id
						new_entry["non_teaching"] = False
						
					elif content.tag == 'Students':
						acronyms.append(content.attrib['name'].split(' ')[0])
					
				if len(acronyms) > 0:
					groups = self.env["ems.group"].search([("name", "in", acronyms)])
					for acro in acronyms:
						if acro not in groups.mapped('name'):
							raise ValidationError("Group with acronym '%s' not found." % acro)
					new_entry["group_ids"] = [(6, 0, groups.ids)]
					new_entry["name"] += " (%s)" % (", ".join(g.name for g in groups))
				dwe.append(new_entry)
				
			dwe = sorted(dwe, key=lambda e: e["hour_from"])
			for i in range(len(dwe)-1):
				dwe[i]["hour_to"] = dwe[i+1]["hour_from"]
			dwe[len(dwe)-1]["hour_to"] = self.env.company.schedule_import_last_entry_time

			for e in (x for x in dwe if x.get("name", False)):
				meta = dict(e)
				meta["group_ids"] = e["group_ids"][0][2]
				entries.append(meta)
				attendance_ids.append([0, 0, e])

		schedule.write({ 'attendance_ids': attendance_ids })
		teacher.write({ "resource_calendar_id": schedule })
		return entries
	
	def _create_assitance_templates(self, entries, teacher, course_id):
		# TODO: It's necessary to know if a template has been created automatically or manually? 
		# 		Should we keep the manually created? If so, additional checks are needed in order to create
		#		the entries avoiding duped templates... 
		color = 1		
		now = datetime.now()		

		old_items = dict()
		for t in teacher.attendance_template_ids.filtered('active'):
			# TODO: what happens with the space, if two templates for the same subject and group exists but for diferent space?
			old_items["%s.%s" % (t.subject_id.id, ",".join(str(g) for g in sorted(t.group_ids.ids)))] = t

		templates = dict()
		new_items = dict()
		for e in entries:
			key = "%s.%s" % (e["subject_id"], ",".join(str(g) for g in sorted(e["group_ids"])))

			if not key in new_items:
				new_items[key] = e

			if not key in old_items:
				# Create only if new
				if key in templates:
					t = templates[key]
				else:
					# TODO: define default start and end date for subjects within settings.
					first_group = self.env['ems.group'].browse(e["group_ids"][0])
					t = {
						'start_date': datetime(now.year, 9, 1),
						'end_date': datetime(now.year+1, 7, 1),
						'color': color,
						'teacher_id': teacher.id,
						'subject_id': e["subject_id"],
						'group_ids': [(6, 0, e["group_ids"])],
						'level_id': first_group.level_id.id,
						'study_id': first_group.study_id.id,
						'space_id': first_group.space_id.id,
						'attendance_schedule_ids': [],
						# TODO: add also the current course
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

		for old in old_items:
			if old not in new_items:
				# NOTE: do not remove link because tracking could be lost, just archive it!
				old_items[old].action_archive()				
		
		# NOTE: Templates must be created directly into its table, in order to be able to run its 'fill_students' method.
		new_templates = self.env['ems.attendance_template'].create(list(templates.values()))
		for t in new_templates:
			t.fill_students()		

		# TODO: should existing ones reload its students? All of them or only automatically added? Keep manually modified untouched?
	
