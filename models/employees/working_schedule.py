# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import xml.etree.ElementTree as ET
import base64
import math

class ems_working_schedule(models.Model):
	_inherit = 'resource.calendar'
	_sql_constraints = [
		('unique_name', 'unique (name)', 'duplicated calendar!')
    ]

	is_framework = fields.Boolean(string="Schedule framework", help="A reusable blank period template for a level of studies, instead of a real teacher's schedule.")
	level_id = fields.Many2one(string="Level", comodel_name="ems.level")
	# NOTE: the calendar this teacher's schedule was originally built from. Unassigned periods are
	# never stored as real attendance rows (see apply_schedule_changes) — this reference is what lets
	# the 'Schedule' tab's grid widget keep showing the framework's blank slots (and its own patio/
	# meeting periods) as editable/inherited on every future "Edit", without persisting them.
	source_framework_id = fields.Many2one(string="Source framework", comodel_name="resource.calendar", domain="[('is_framework', '=', True)]")

	def seed_from_framework(self, framework):
		"""Point this calendar at 'framework' as its reference bell schedule and clear any existing
		weekday (Mon-Fri) attendances. The framework's own periods (including patio/meeting slots)
		only become real rows the first time the 'Schedule' tab actually saves them — nothing is
		written here, matching the rule that unassigned slots are never stored."""
		self.ensure_one()
		self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4')).unlink()
		self.source_framework_id = framework.id

	def apply_schedule_changes(self, cells, source_framework_id=None):
		"""Replace this calendar's weekday (Mon-Fri) attendances with 'cells' (called from the
		'Schedule' tab's grid widget, whose buffer already represents the full weekly state — unassigned
		slots are never included, only real subject/non-teaching entries), then re-derive the teacher's
		'teaching_ids' from the same cells so both stay in sync. 'source_framework_id' is only passed
		when "New" picked a different reference framework (directly, or inherited by copying a
		colleague), so future edits keep showing the right blank slots."""
		self.ensure_one()
		self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4')).unlink()
		self.write({'attendance_ids': [(0, 0, cell) for cell in cells]})
		if source_framework_id:
			self.source_framework_id = source_framework_id

		teacher = self.env['hr.employee'].search([('resource_calendar_id', '=', self.id)])
		if teacher:
			entries = [cell for cell in cells if cell.get('subject_id')]
			self.env['ems.teaching'].sync_from_schedule(teacher, entries)
			self.env['ems.attendance_template'].sync_from_schedule(teacher, entries, start_date=fields.Date.today())

	# NOTE: assigned in first-seen (day, then hour) order to the distinct items on a calendar, so two
	# unrelated items only ever share a color once the palette itself runs out — see
	# 'get_schedule_report_lines'/'_report_color_key'.
	REPORT_COLOR_PALETTE = [
		'#5b8def', '#f4a261', '#2a9d8f', '#e76f51', '#8ecae6', '#ffb703',
		'#c77dff', '#06d6a0', '#ef476f', '#118ab2', '#bc6c25', '#9d4edd',
	]

	def get_schedule_report_lines(self):
		"""Weekly schedule rows (one per distinct Mon-Fri period, one column per weekday) for the
		working schedule PDF report. Unassigned slots are never stored (see apply_schedule_changes),
		so every attendance row here is a real subject or non-teaching commitment. Each cell carries
		the matching attendance record (or False) plus a 'color': the same subject/non-teaching reason
		always gets the same color, even across different days, to make the printed grid easier to
		scan at a glance."""
		self.ensure_one()
		weekday_entries = self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4'))
		periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in weekday_entries})

		color_by_key = {}
		for attendance in weekday_entries.sorted(key=lambda attendance: (attendance.dayofweek, attendance.hour_from)):
			key = self._report_color_key(attendance)
			if key not in color_by_key:
				color_by_key[key] = self.REPORT_COLOR_PALETTE[len(color_by_key) % len(self.REPORT_COLOR_PALETTE)]

		lines = []
		for hour_from, hour_to in periods:
			cells = []
			for dayofweek in ('0', '1', '2', '3', '4'):
				entry = weekday_entries.filtered(
					lambda attendance, dayofweek=dayofweek, hour_from=hour_from, hour_to=hour_to:
						attendance.dayofweek == dayofweek and attendance.hour_from == hour_from and attendance.hour_to == hour_to
				)
				cells.append({
					'entry': entry,
					'color': color_by_key.get(self._report_color_key(entry)) if entry else False,
				})
			lines.append({
				'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
				'cells': cells,
			})
		return lines

	def _report_color_key(self, attendance):
		return ('non_teaching', attendance.non_teaching) if attendance.non_teaching else ('subject', attendance.subject_id.id)

	def _format_report_time(self, value):
		hour, minutes = divmod(round(value * 60), 60)
		return "%02d:%02d" % (hour, minutes)

	# Wednesday is dayofweek '2' (dayofweek follows date.weekday(): '0'=Monday).
	FIXED_HOURS_WEDNESDAY = '2'

	def get_schedule_hours_summary(self):
		"""Weekly hours totals for the Schedule tab's summary table, split into two columns exactly
		like the real external schedules this data is modelled on:
		- 'teaching': weekly teaching hours grouped by level (ems.group.level_id), plus every
		  non-teaching activity that ISN'T a guard duty or a Wednesday coordination meeting (the
		  break, 'BR', is dropped entirely from both columns).
		- 'fixed': guard duties (any day) and coordination meetings ('CM') specifically on Wednesday —
		  the centre's fixed non-teaching commitments.
		Each period's duration is rounded UP to the nearest whole hour (a period that only partially
		overlaps an hour still counts as one full hour), then summed. Not stored — cheap to compute
		from the calendar's own attendance_ids, and reused as-is by the PDF report's own summary table
		later. For a full-time teacher, 'total' should equal 24 (full_time_required_hours)."""
		self.ensure_one()
		weekday_entries = self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4'))

		teaching_rows = {}
		fixed_rows = {}
		for attendance in weekday_entries:
			duration = math.ceil(attendance.hour_to - attendance.hour_from)
			if attendance.subject_id:
				level = attendance.group_ids[:1].level_id
				key = ('level', level.id)
				bucket = teaching_rows
				label = level.display_name
			elif attendance.non_teaching == 'BR':
				continue
			elif attendance.non_teaching:
				is_fixed = attendance.non_teaching == 'G' or (attendance.non_teaching == 'CM' and attendance.dayofweek == self.FIXED_HOURS_WEDNESDAY)
				bucket = fixed_rows if is_fixed else teaching_rows
				key = ('activity', attendance.non_teaching)
				label = attendance.get_report_label()
			else:
				continue

			if key not in bucket:
				bucket[key] = {'label': label, 'hours': 0}
			bucket[key]['hours'] += duration

		teaching = sorted(teaching_rows.values(), key=lambda row: row['label'])
		fixed = sorted(fixed_rows.values(), key=lambda row: row['label'])
		teaching_total = sum(row['hours'] for row in teaching)
		fixed_total = sum(row['hours'] for row in fixed)

		return {
			'teaching': {'rows': teaching, 'total': teaching_total},
			'fixed': {'rows': fixed, 'total': fixed_total},
			'total': teaching_total + fixed_total,
		}

class ems_working_schedule_assignation(models.Model):
	_inherit = 'resource.calendar.attendance'
	# NOTE: no need to constraint, the main model avoids overlapping. 

	non_teaching_selection=[
		("AC", "Another Coordinations"),
		("BR", "Break"),
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

	def get_report_label(self):
		"""Display label for the working schedule PDF report. NOT 'self.name': that Char is frozen in
		whatever language was active when the row was saved (Edit/Import always write it in English —
		see 'non_teaching_items'/'nonTeachingByCode' in this file and in schedule_grid_field.js), so a
		non-teaching row would otherwise always show "Guard" even when printing in Catalan/Spanish. The
		Selection field's own option label, resolved for the report's current language, is used instead."""
		self.ensure_one()
		if self.non_teaching:
			labels = dict(self._fields['non_teaching']._description_selection(self.env))
			return labels.get(self.non_teaching, self.non_teaching)
		return self.name

class ems_working_schedules_import_wizard(models.TransientModel):
	_name = "ems.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."
	_inherit = ['ems.datetime_utils']

	attachment_id = fields.Many2one(string="Attachment", comodel_name="ir.attachment", domain="[('res_model', '=', 'ems.working_schedules_import_wizard')]")
	file = fields.Binary(string="Planner file (XML)", related="attachment_id.datas")
	# NOTE: only used when 'teacher_id' is NOT set (i.e. the general importer, opened from the
	# "Working Schedules" list's cog menu, not the per-employee 'Import' button) — lets several planner
	# files be imported in one go, each one possibly describing several teachers (see create()).
	attachment_ids = fields.Many2many(string="Planner files (XML)", comodel_name="ir.attachment")
	is_overriding = fields.Boolean(store=False)
	overrided_teachers = fields.Char(default="")
	# NOTE: set via context (default_teacher_id) when opened from an employee's 'Schedule' tab "Import"
	# button — the file is then assumed to describe that single teacher, skipping the email lookup below.
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee")

	@api.onchange("file")
	def _onchange_file(self):
		for rec in self:
			if rec.file:
				xml_content = base64.b64decode(rec.file)
				tree = ET.ElementTree(ET.fromstring(xml_content))

				root = tree.getroot()
				if rec.teacher_id:
					if rec.teacher_id.resource_calendar_id.id:
						rec.is_overriding = True
						rec.overrided_teachers = rec.teacher_id.display_name
					continue

				for teacherNode in root:
					email = teacherNode.attrib['name'].split(' ')[0]
					teacher = self.env["hr.employee"].search([("work_email", "=", email)]) or False

					if teacher and teacher.resource_calendar_id.id:
						rec.is_overriding = True
						rec.overrided_teachers = teacher.display_name if not rec.overrided_teachers else "%s, %s" % (rec.overrided_teachers, teacher.display_name)

	@api.onchange("attachment_ids")
	def _onchange_attachment_ids(self):
		for rec in self:
			rec.is_overriding = False
			rec.overrided_teachers = ""
			for attachment in rec.attachment_ids:
				xml_content = base64.b64decode(attachment.datas)
				tree = ET.ElementTree(ET.fromstring(xml_content))

				for teacherNode in tree.getroot():
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
			xml_contents = self._collect_xml_contents(item)
			if not xml_contents:
				raise ValidationError(_("No XML file has been loaded. Please, provide at least one XML file and try again."))

			for xml_content in xml_contents:
				tree = ET.ElementTree(ET.fromstring(xml_content))
				root = tree.getroot()

				if item.get('teacher_id'):
					nodes = [(root[0], self.env['hr.employee'].browse(item['teacher_id']))]
				else:
					nodes = []
					for node in root:
						email = node.attrib['name'].split(' ')[0]
						teacher = self.env["hr.employee"].search([("work_email", "=", email)])
						if not teacher.id: raise ValidationError("Teacher with email '%s' not found." % email)
						nodes.append((node, teacher))

				for node, teacher in nodes:
					entries = self._create_schedule(node, teacher, course_id)
					entries = [e for e in entries if not e["non_teaching"]]
					self.env['ems.teaching'].sync_from_schedule(teacher, entries)
					self.env['ems.attendance_template'].sync_from_schedule(teacher, entries)

		return super(models.Model, self).create(values)

	def _collect_xml_contents(self, item):
		"""Every XML source given for this wizard's 'create()' vals, decoded — 'file' (the per-employee
		single-file flow) and/or 'attachment_ids' (the general importer's multi-file flow), so a single
		call can process any combination of both."""
		contents = []
		if item.get('file'):
			contents.append(base64.b64decode(item['file']))
		attachment_ids = self._m2m_command_ids(item.get('attachment_ids'))
		for attachment in self.env['ir.attachment'].browse(attachment_ids):
			contents.append(base64.b64decode(attachment.datas))
		return contents

	def _m2m_command_ids(self, commands):
		ids = []
		for command in commands or []:
			if command[0] in (4, 1):
				ids.append(command[1])
			elif command[0] == 6:
				ids.extend(command[2])
		return ids

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
					# NOTE: 'NonTeaching' is only kept for backward compatibility with older planner
					# exports — the current external app sends non-teaching hours as a 'Subject' node
					# too (its only observable difference is the missing 'Students' sibling), so the
					# real distinction is made by code membership in 'non_teaching_items', not by tag.
					if content.tag in ('Subject', 'NonTeaching'):
						code = content.attrib['name'].split(' ')[0]
						if code in non_teaching_items:
							new_entry["name"] = "%s: %s" % (code, non_teaching_items[code])
							new_entry["subject_id"] = False
							new_entry["group_ids"] = [(6, 0, [])]
							new_entry["non_teaching"] = code
						else:
							subject = self.env["ems.subject"].search([("code", "=", code)])
							if not subject.id: raise ValidationError("Subject with code '%s' not found." % code)

							new_entry["name"] = "%s: %s" % (subject.acronym, subject.name)
							new_entry["subject_id"] = subject.id
							new_entry["non_teaching"] = False

					elif content.tag == 'Students':
						acronyms.append(content.attrib['name'].split(' ')[0])
					
				if len(acronyms) > 0:
					groups = self.env["ems.group"]
					for acro in acronyms:
						# NOTE: the external planner names a level's only group "DAM1", while EMS always
						# names groups with a trailing letter ("DAM1A" even when there's just one) — retry
						# with an appended "A" before giving up; still not found means a genuine mismatch
						# that needs manual review.
						group = self.env["ems.group"].search([("name", "=", acro)], limit=1) \
							or self.env["ems.group"].search([("name", "=", acro + "A")], limit=1)
						if not group:
							raise ValidationError("Group with acronym '%s' not found." % acro)
						groups |= group
					new_entry["group_ids"] = [(6, 0, groups.ids)]
					new_entry["name"] += " (%s)" % (", ".join(g.name for g in groups))
				dwe.append(new_entry)
				
			dwe = sorted(dwe, key=lambda e: e["hour_from"])
			for i in range(len(dwe)-1):
				dwe[i]["hour_to"] = dwe[i+1]["hour_from"]

			# NOTE: the planner XML never carries an end time, only each period's start — the day's
			# last period has no "next" one to borrow hour_to from, so it inherits the immediately
			# preceding period's own duration instead. Only a single-period day (nothing to infer
			# duration from) falls back to the fixed company setting.
			if len(dwe) > 1:
				last_period_duration = dwe[-2]["hour_to"] - dwe[-2]["hour_from"]
				dwe[-1]["hour_to"] = dwe[-1]["hour_from"] + last_period_duration
			else:
				dwe[-1]["hour_to"] = self.env.company.schedule_import_last_entry_time

			for e in (x for x in dwe if x.get("name", False)):
				meta = dict(e)
				meta["group_ids"] = e["group_ids"][0][2]
				entries.append(meta)
				attendance_ids.append([0, 0, e])

		schedule.write({ 'attendance_ids': attendance_ids })
		teacher.write({ "resource_calendar_id": schedule })
		return entries

