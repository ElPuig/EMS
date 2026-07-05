# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ems_grade_outcome_line(models.Model):
	_name = "ems.grade_outcome_line"
	_description = "Grade outcome line: a student's score for a single learning outcome within a grade session."
	_order = "student_id asc, outcome_id asc"

	grade_session_id = fields.Many2one(string="Grade session", comodel_name="ems.grade_session", required=True, ondelete="cascade")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", related="grade_session_id.subject_id", store=False)
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	student_firstname = fields.Char(string="First name", related="student_id.firstname", store=False)
	student_lastname = fields.Char(string="Last name", related="student_id.lastname", store=False)
	image_1920 = fields.Binary(string="Image", related="student_id.image_1920")
	outcome_id = fields.Many2one(string="Outcome", comodel_name="ems.outcome", required=True)
	outcome_acronym = fields.Char(string="Outcome acronym", related="outcome_id.acronym", store=False)
	ponderation = fields.Float(string="Ponderation (%)", compute="_compute_ponderation", store=True)
	score = fields.Integer(string="Score")
	is_scored = fields.Boolean(string="Scored", default=False, help="Whether the score has been informed (an empty score is excluded from the subject grade).")
	is_locked = fields.Boolean(string="Locked", compute="_compute_is_locked", store=False, help="Whether this outcome was already passed (score >= 5) in an earlier round for the same student, group and subject; a passed outcome cannot be re-evaluated.")
	is_lock_released = fields.Boolean(string="Lock released", default=False, help="Set when the official grade import overwrites this line: the cross-round lock is released for this line only, so the imported grade is shown without the padlock. Earlier rounds are left untouched, preserving their history.")
	is_auto_generated = fields.Boolean(default=False)

	# Used only for access-rule filtering.
	teacher_id = fields.Many2one(string="Teacher", related="grade_session_id.teacher_id", store=False)

	@api.depends("grade_session_id.planning_id", "outcome_id")
	def _compute_ponderation(self):
		for rec in self:
			planning_outcome = rec.grade_session_id.planning_id.planning_outcome_ids.filtered(lambda po: po.outcome_id == rec.outcome_id)
			rec.ponderation = planning_outcome[:1].ponderation

	@api.depends("student_id", "outcome_id", "grade_session_id.group_id", "grade_session_id.subject_id", "grade_session_id.round", "is_lock_released")
	def _compute_is_locked(self):
		# A passed outcome (score >= 5) from an earlier round of the same group and subject is final: it
		# must not be re-evaluated. This crosses grade sessions, so it is recomputed on read (store=False),
		# like grade_session.can_edit.
		for rec in self:
			rec.is_locked = False
			# An official import may release the lock on the line it overwrites (see is_lock_released),
			# without altering the earlier rounds that would otherwise keep it locked.
			if rec.is_lock_released:
				continue
			session = rec.grade_session_id
			if not (rec.student_id and rec.outcome_id and session.group_id and session.subject_id and session.round):
				continue
			rec.is_locked = bool(self.search_count([
				("student_id", "=", rec.student_id.id),
				("outcome_id", "=", rec.outcome_id.id),
				("grade_session_id.group_id", "=", session.group_id.id),
				("grade_session_id.subject_id", "=", session.subject_id.id),
				("grade_session_id.round", "<", session.round),
				("is_scored", "=", True),
				("score", ">=", 5),
			]))

	def write(self, vals):
		# open: scoped teachers/tutors; board: only the group's tutor; final: only admin.
		scoring = "score" in vals or "is_scored" in vals
		# The official grade importer may overwrite a locked outcome: the file is the source of
		# truth. This bypass is set only by ems.grade_import_wizard, never on manual editing.
		bypass_lock = self.env.context.get("ems_grade_import_bypass_lock")
		for rec in self:
			if not rec.grade_session_id.can_edit:
				if rec.grade_session_id.state == "final":
					raise UserError(_("This evaluation session is final; only administrators can edit the grades."))
				raise UserError(_("This evaluation session is in the board stage; only the group's tutor (or an administrator) can edit the grades."))
			# A passed outcome from an earlier round cannot be re-evaluated (no exception, not even for admins).
			if scoring and rec.is_locked and not bypass_lock:
				raise UserError(_("This learning outcome was already passed in an earlier round; its grade cannot be modified."))
		return super().write(vals)

	@api.constrains("score")
	def _check_score(self):
		for rec in self:
			if rec.score < 0 or rec.score > 10:
				raise ValidationError(_("The score must be within the range [0, 10]."))

	@api.depends("student_id", "outcome_id")
	def _compute_display_name(self):
		for rec in self:
			rec.display_name = "%s | %s" % (rec.student_id.display_name or "", rec.outcome_id.display_name or "")
