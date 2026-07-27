# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ems_group(models.Model):
	_name = "ems.group"
	_description = "Groups: Where the students are assigned to."
	_order = "name"

	group_type = fields.Selection(
		selection=[('main', 'Main'), ('reinforcement', 'Reinforcement')],
		string="Group Type", required=True, default="main",
		help="Main: the group a student is enrolled in (main_group_id), with a tutor, a delegate and a single study/level. "
			"Reinforcement: appears in the teaching schedule like any other group, but has no tutor/delegate and can mix "
			"students from different main groups and studies.")
	course = fields.Integer(string="Course")
	acronym = fields.Char(string="Acronym")
	external_id = fields.Char(string="External ID", help="Esfera (SAGA) group code, e.g. 'ESO LOEM101'.")
	name = fields.Char(string="Name", compute="_compute_name", store=True, readonly=False) #should not be edited manually for 'main' groups
	notes = fields.Text(string="Notes")

	level_id = fields.Many2one(string='Level', comodel_name='ems.level')
	study_id = fields.Many2one(string="Study", comodel_name="ems.study")
	tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]")

	delegate_id = fields.Many2one(string="Delegate", comodel_name="res.partner", domain="[('contact_type', '=', 'student'), ('main_group_id', '=', id)]")
	space_id = fields.Many2one(string="Classroom", comodel_name="ems.space")

	main_student_ids = fields.One2many(string="Students", comodel_name="res.partner", inverse_name="main_group_id", domain="[('contact_type', '=', 'student')]")
	reinforcement_student_ids = fields.Many2many(string="Reinforcement Students", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	enrolled_student_ids = fields.Many2many(string="Enrolled", comodel_name="res.partner", compute="_compute_enrolled_student_ids")
	enrollment_view_ids = fields.One2many(string="Enrollment", comodel_name="ems.enrollment_view", inverse_name="group_id", compute="_compute_enrollment_ids") # Contains the same data as enrolled_student_ids but filtered for the current group (sadly, it cannot be filtered on view...)
	shift = fields.Selection(selection=[('morning', 'Morning'),('afternoon', 'Afternoon'),],string="Shift",help="Morning or afternoon shift for this group.")

	@api.depends("group_type", "study_id.acronym", "course", "acronym")
	def _compute_name(self):
		for rec in self:
			#TODO: validate the uniqueness
			if rec.group_type == "main":
				# 'study_id'/'course'/'acronym' can be transiently empty right after switching from
				# 'reinforcement' back to 'main' (before the user fills them in) — building the string
				# anyway would render literal "False"/"0" instead of a blank name.
				rec.name = "%s%s%s" % (rec.study_id.acronym, rec.course, rec.acronym) \
					if rec.study_id and rec.course and rec.acronym else False
			elif not rec.name:
				rec.name = rec.acronym or rec.external_id or _("New Reinforcement Group")

	@api.onchange("group_type")
	def _onchange_group_type(self):
		# NOTE: only clears the group's OWN fields (visible to the user before Save, so nothing is lost
		# without them seeing it happen first). Existing 'main_student_ids' (other res.partner records
		# pointing here via main_group_id) are deliberately NOT touched here — see
		# '_check_group_type_fields' below, which blocks the switch instead of silently orphaning them.
		for rec in self:
			if rec.group_type == "reinforcement":
				rec.level_id = False
				rec.study_id = False
				rec.course = False
				rec.acronym = False
				rec.tutor_id = False
				rec.delegate_id = False
			elif rec.group_type == "main":
				rec.reinforcement_student_ids = [(5, 0, 0)]

	@api.constrains("group_type", "level_id", "study_id", "course", "acronym", "tutor_id", "delegate_id")
	def _check_group_type_fields(self):
		for rec in self:
			if rec.group_type == "main":
				if not (rec.level_id and rec.study_id and rec.course and rec.acronym):
					raise ValidationError(_("A main group requires a level, a study, a course and an acronym."))
			elif rec.group_type == "reinforcement":
				if rec.level_id or rec.study_id or rec.tutor_id or rec.delegate_id:
					raise ValidationError(_("A reinforcement group cannot have a level, a study, a tutor or a delegate: "
						"it is meant to mix students from different main groups and studies."))
				if rec.main_student_ids:
					raise ValidationError(_("This group has %d student(s) enrolled as their main group. Reassign them to "
						"another group before converting this one to reinforcement.") % len(rec.main_student_ids))

	def _compute_enrolled_student_ids(self):			
		for rec in self:			
			rec.enrolled_student_ids = self.env["ems.enrollment"].search([("group_id", "=", rec.id)]).mapped("student_id") or False

	def _compute_enrollment_ids(self):							
		for rec in self:							
			self.env['ems.enrollment_view'].search([('group_id', '=', rec.id)]).unlink()
			rec.enrollment_view_ids = False
			#Sources: 
			# 	https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html?highlight=read_group#search-read
			#	https://www.cybrosys.com/odoo/odoo-books/odoo-15-development/ch15/grouped-data/	
			for student in self.env['ems.enrollment'].read_group(domain=[('group_id', '=', rec.id)], fields=['student_id'], groupby=['student_id']):	
				sid = student['student_id'][0]	
				subs = self.env["ems.enrollment"].search([("group_id", "=", rec.id), ('student_id', '=', sid)]).mapped("subject_id")
				
				# Source: https://www.odoo.com/fi_FI/forum/apua-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
				rec.enrollment_view_ids.create({
					"group_id": rec.id,
					"student_id": sid,
					"subject_ids": subs,					
				})				

	def _sanitize_group_type_vals(self, vals):
		# NOTE: '_onchange_group_type' already does this client-side, purely so the user SEES the fields
		# clear before Save — it cannot be the only place this happens: it never runs for a write() that
		# doesn't go through this exact form (RPC, batch action, an import), and even in the form its
		# timing relative to other onchange/compute triggers isn't something to depend on. This is the
		# actual guarantee that '_check_group_type_fields' below never rejects a plain group_type switch.
		group_type = vals.get("group_type")
		if group_type == "reinforcement":
			for field in ("level_id", "study_id", "course", "acronym", "tutor_id", "delegate_id"):
				vals.setdefault(field, False)
		elif group_type == "main":
			vals.setdefault("reinforcement_student_ids", [(5, 0, 0)])

	def _sync_tutor_role(self, employees):
		"""Keep 'employees' Tutor role and security groups in sync with whether they
		currently tutor at least one group. Shared by create() (a group created with
		tutor_id already set) and write() (tutor_id assigned/reassigned/cleared later) so
		both paths behave the same way instead of only write() doing the sync."""
		employees.update_tutor_role()
		employees._sync_security_groups()

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			self._sanitize_group_type_vals(vals)
		groups = super().create(vals_list)
		self._sync_tutor_role(groups.mapped('tutor_id'))
		return groups

	def write(self, vals):
		self._sanitize_group_type_vals(vals)
		old_tutor = self.tutor_id
		res = super(ems_group, self).write(vals)
		new_tutor = self.tutor_id

		if 'tutor_id' in vals:
			# NOTE: tutor_id field changes when the tutor is assigned from the teacher form, but the old tutor's role
			# should be updated and must be done from here once changed.
			self._sync_tutor_role(old_tutor | new_tutor)
		return res
class ems_enrollment_view(models.TransientModel):
	_name = "ems.enrollment_view"
	_description = "Transitient model for displaying enrollment data within groups but filtered (allows ems.group.enrollment_view_ids to work: contains the same data as enrolled_student_ids but filtered for the current group because it cannot be filtered on view...)."
	
	group_id = fields.Many2one(comodel_name="ems.group")
	student_id = fields.Many2one(comodel_name="res.partner")
	subject_ids = fields.Many2many(comodel_name="ems.subject")	
	image_1920 = fields.Binary(string="Image", related='student_id.image_1920')

	# def open_form(self):
	# 	return {
	# 		'type': 'ir.actions.act_window',
	# 		'res_model': 'res.partner',
	# 		'res_id': self.student_id.id,						
	# 		'view_id': self.env.ref('base.view_partner_form').id,
	# 		'view_mode': 'form',
	# 	}		