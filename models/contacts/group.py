# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, ValidationError

class EmsGroup(models.Model):
	_name = "ems.group"
	_description = "Groups: Where the students are assigned to."
	_order = "name"

	active = fields.Boolean(default=True, help="A group that won't be used this course but may come back in a "
		"future one (e.g. a cycle not running this year) should be archived instead of deleted, so it can be "
		"reactivated later instead of being recreated as a duplicate.")
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
		for group in self:
			#TODO: validate the uniqueness
			if group.group_type == "main":
				# 'study_id'/'course'/'acronym' can be transiently empty right after switching from
				# 'reinforcement' back to 'main' (before the user fills them in) — building the string
				# anyway would render literal "False"/"0" instead of a blank name.
				group.name = "%s%s%s" % (group.study_id.acronym, group.course, group.acronym) \
					if group.study_id and group.course and group.acronym else False
			elif not group.name:
				group.name = group.acronym or group.external_id or _("New Reinforcement Group")

	@api.onchange("group_type")
	def _onchange_group_type(self):
		# NOTE: only clears the group's OWN fields (visible to the user before Save, so nothing is lost
		# without them seeing it happen first). Existing 'main_student_ids' (other res.partner records
		# pointing here via main_group_id) are deliberately NOT touched here — see
		# '_check_group_type_fields' below, which blocks the switch instead of silently orphaning them.
		for group in self:
			if group.group_type == "reinforcement":
				group.level_id = False
				group.study_id = False
				group.course = False
				group.acronym = False
				group.tutor_id = False
				group.delegate_id = False
			elif group.group_type == "main":
				group.reinforcement_student_ids = [(5, 0, 0)]

	@api.constrains("group_type", "level_id", "study_id", "course", "acronym", "tutor_id", "delegate_id")
	def _check_group_type_fields(self):
		for group in self:
			if group.group_type == "main":
				if not (group.level_id and group.study_id and group.course and group.acronym):
					raise ValidationError(_("A main group requires a level, a study, a course and an acronym."))
			elif group.group_type == "reinforcement":
				if group.level_id or group.study_id or group.tutor_id or group.delegate_id:
					raise ValidationError(_("A reinforcement group cannot have a level, a study, a tutor or a delegate: "
						"it is meant to mix students from different main groups and studies."))
				if group.main_student_ids:
					raise ValidationError(_("This group has %d student(s) enrolled as their main group. Reassign them to "
						"another group before converting this one to reinforcement.") % len(group.main_student_ids))

	def _compute_enrolled_student_ids(self):
		for group in self:
			group.enrolled_student_ids = self.env["ems.enrollment"].search([("group_id", "=", group.id)]).mapped("student_id") or False

	def _compute_enrollment_ids(self):
		# NOTE: deliberately a compute WITH side effects (delete + recreate ems.enrollment_view
		# rows) rather than a pure read — the only way found to expose "enrollment_view_ids
		# filtered to just this group" as a One2many, since Odoo can't filter a computed
		# relation server-side the way a stored inverse can. ems.enrollment_view is a
		# TransientModel (auto-vacuumed), so the churn is cheap, but this does mean every read
		# of an unset/stale enrollment_view_ids re-runs a delete+insert, not just a select —
		# worth knowing if this model's read patterns ever become a hot path.
		for group in self:
			self.env['ems.enrollment_view'].search([('group_id', '=', group.id)]).unlink()
			group.enrollment_view_ids = False
			# Sources:
			# 	https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html?highlight=read_group#search-read
			#	https://www.cybrosys.com/odoo/odoo-books/odoo-15-development/ch15/grouped-data/
			for student in self.env['ems.enrollment'].read_group(domain=[('group_id', '=', group.id)], fields=['student_id'], groupby=['student_id']):
				sid = student['student_id'][0]
				subs = self.env["ems.enrollment"].search([("group_id", "=", group.id), ('student_id', '=', sid)]).mapped("subject_id")

				# Source: https://www.odoo.com/fi_FI/forum/apua-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
				group.enrollment_view_ids.create({
					"group_id": group.id,
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

	def _raise_if_archived_duplicate(self, groups):
		# 'name' (e.g. 'DAM1A') is the group's real-world identity and is confirmed unique in
		# practice: a group not running this course may well come back in a future one, so the
		# right move is to reactivate the existing (archived) record, not create a second one
		# with the same name. Raised from inside a savepoint (see create()/write() below), so
		# the offending create/rename never actually persists once this propagates out.
		for group in groups:
			archived = self.with_context(active_test=False).search([
				("name", "=", group.name), ("active", "=", False), ("id", "!=", group.id),
			], limit=1)
			if archived:
				raise RedirectWarning(
					_("A group named \"%s\" already exists but is archived. Reactivate it instead "
						"of creating a duplicate?") % group.name,
					self.env.ref("ems.action_server_group_reactivate").id,
					_("Reactivate"),
					{"active_model": self._name, "active_id": archived.id, "active_ids": archived.ids},
				)

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			self._sanitize_group_type_vals(vals)
		with self.env.cr.savepoint():
			groups = super().create(vals_list)
			self._raise_if_archived_duplicate(groups)
		self._sync_tutor_role(groups.mapped('tutor_id'))
		return groups

	def _archive_confirmation_message(self):
		# Archiving is always allowed (it never removes/unenrolls anyone) - this only builds the
		# confirmation message when there's something worth confirming (at least one active
		# student). Shared by the write()-time safety net below and by
		# 'get_archive_confirmation_message()', which the client calls proactively so it can show
		# its OWN dialog (proper title, "Proceed"/"Cancel" labels) instead of ever letting Odoo's
		# generic RedirectWarning dialog ("Odoo Warning" title, no control over button styling) be
		# what the user actually sees.
		count = sum(
			len(group.main_student_ids) + len(group.reinforcement_student_ids.filtered("active"))
			for group in self
		)
		if not count:
			return False
		return "\n\n".join([
			_("This group still has %(count)s active student(s) as members.") % {"count": count},
			_("Archiving is allowed and will not remove or unenroll any student. The group's "
				"member list stays exactly as it is, they simply won't appear in the default "
				"(non-archived) views anymore."),
			_("If these students are still here because the end-of-course transition hasn't run "
				"yet, that process will move or clear them from this group when it does, the same "
				"as for any other group. Archiving this one now has no effect on that, and doesn't "
				"need to wait for it either."),
			_("Do you want to archive this group anyway?"),
		])

	def get_archive_confirmation_message(self):
		"""RPC-callable: returns the confirmation message (or False if none is needed) so
		EmsGroupFormController/EmsGroupListController can show their own dialog BEFORE ever
		calling archive - the normal, expected path. write()'s own guard below still exists as a
		safety net for anything that archives outside that UI (a direct ORM call, an import
		script, an RPC client), where it falls back to the plainer RedirectWarning dialog."""
		return self._archive_confirmation_message()

	def _raise_if_archiving_active_students(self):
		# Self-retriggering RedirectWarning, same pattern Odoo core uses for e.g.
		# account.account's Unmerge: the button re-runs this same write() with a context flag
		# that skips the check the second time, so declining (closing the dialog) leaves the
		# group untouched - nothing has been written yet at the point this raises.
		if self.env.context.get("ems_group_archive_confirmed"):
			return
		message = self._archive_confirmation_message()
		if not message:
			return
		raise RedirectWarning(
			message,
			self.env.ref("ems.action_server_group_confirm_archive").id,
			_("Proceed"),
			{"active_model": self._name, "active_ids": self.ids},
		)

	def write(self, vals):
		self._sanitize_group_type_vals(vals)
		if vals.get("active") is False:
			self._raise_if_archiving_active_students()
		old_tutor = self.tutor_id
		name_affecting = vals.keys() & {"name", "course", "acronym", "study_id", "group_type", "external_id"}
		with self.env.cr.savepoint():
			res = super(EmsGroup, self).write(vals)
			if name_affecting:
				self._raise_if_archived_duplicate(self)
		new_tutor = self.tutor_id

		if 'tutor_id' in vals:
			# NOTE: tutor_id field changes when the tutor is assigned from the teacher form, but the old tutor's role
			# should be updated and must be done from here once changed.
			self._sync_tutor_role(old_tutor | new_tutor)
		return res

	def action_reactivate(self):
		self.ensure_one()
		self.active = True
		return {
			"type": "ir.actions.act_window",
			"res_model": self._name,
			"res_id": self.id,
			"view_mode": "form",
			"target": "current",
		}

	def action_confirm_archive(self):
		self.with_context(ems_group_archive_confirmed=True).write({"active": False})
		return {
			"type": "ir.actions.client",
			"tag": "soft_reload",
		}


class EmsEnrollmentView(models.TransientModel):
	_name = "ems.enrollment_view"
	_description = "Transient model for displaying enrollment data within groups but filtered (allows ems.group.enrollment_view_ids to work: contains the same data as enrolled_student_ids but filtered for the current group because it cannot be filtered on view...)."

	group_id = fields.Many2one(comodel_name="ems.group")
	student_id = fields.Many2one(comodel_name="res.partner")
	subject_ids = fields.Many2many(comodel_name="ems.subject")
	image_1920 = fields.Binary(string="Image", related='student_id.image_1920')