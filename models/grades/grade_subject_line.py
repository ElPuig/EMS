# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ems_grade_subject_line(models.Model):
	_name = "ems.grade_subject_line"
	_description = "Grade subject line: a student's subject grade within a grade session (computed from outcomes, teacher can override)."
	_order = "student_id asc"

	grade_session_id = fields.Many2one(string="Grade session", comodel_name="ems.grade_session", required=True, ondelete="cascade")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", related="grade_session_id.subject_id", store=False)
	subject_name = fields.Char(string="Subject name", related="subject_id.display_name", store=False)
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	student_firstname = fields.Char(string="First name", related="student_id.firstname", store=False)
	student_lastname = fields.Char(string="Last name", related="student_id.lastname", store=False)
	image_1920 = fields.Binary(string="Image", related="student_id.image_1920")

	internal_ponderation = fields.Float(string="Internal ponderation (%)", related="grade_session_id.planning_id.internal_ponderation")
	external_ponderation = fields.Float(string="External ponderation (%)", related="grade_session_id.planning_id.external_ponderation")
	is_overridden = fields.Boolean(string="Overridden", default=False, help="When set, the teacher's manual internal grade is kept; otherwise the internal grade is computed from the outcomes.")
	internal_score = fields.Integer(string="Internal score", compute="_compute_internal_score", store=True, readonly=False, help="Internal grade (from the outcomes). Computed unless the teacher overrides it.")
	internal_is_scored = fields.Boolean(string="Internal scored", compute="_compute_internal_is_scored", store=True, help="Whether the internal grade is informed (an outcome scored, or the teacher overrode it).")
	external_score = fields.Integer(string="External score", default=0, help="External grade (e.g. work placement); informed manually.")
	external_is_scored = fields.Boolean(string="External scored", default=False, help="Whether the external grade has been informed (an empty external grade is excluded from the subject grade).")
	computed_score = fields.Integer(string="Computed grade", compute="_compute_computed_score", store=True, help="Suggested subject grade applying the planning ponderations.")
	computed_is_scored = fields.Boolean(string="Computed scored", compute="_compute_computed_score", store=True, help="Whether every weighted component (internal / external) required by the planning has been informed.")
	final_score = fields.Integer(string="Final grade", compute="_compute_final_score", store=True, help="Final subject grade (equal to the computed grade).")
	has_final = fields.Boolean(string="Has final", compute="_compute_has_final", store=True, help="Whether there is a final grade (the computed grade is available).")
	notes = fields.Char(string="Notes", help="Free per-student remark for this subject grade.")

	# Used only for access-rule filtering.
	teacher_id = fields.Many2one(string="Teacher", related="grade_session_id.teacher_id", store=False)

	@api.depends(
		"is_overridden",
		"grade_session_id.grade_outcome_line_ids.score",
		"grade_session_id.grade_outcome_line_ids.is_scored",
		"grade_session_id.grade_outcome_line_ids.ponderation",
	)
	def _compute_internal_score(self):
		# Computed-but-writable: computed from the outcomes unless the teacher overrides it, in which case
		# the manual value is kept until the override is cleared.
		for rec in self:
			if rec.is_overridden:
				continue
			all_lines = rec.grade_session_id.grade_outcome_line_ids.filtered(
				lambda line: line.student_id == rec.student_id
			)
			scored = all_lines.filtered("is_scored")
			# An unscored outcome counts as a 0 (suspended): the average is taken over every outcome, so
			# the missing ones weigh in as zeros rather than being renormalized away. The internal grade
			# is a whole number (round half up).
			total_pond = sum(line.ponderation for line in all_lines)
			if total_pond:
				internal = int(sum(line.score * line.ponderation for line in scored) / total_pond + 0.5)
			else:
				internal = 0
			# A missing or failed outcome (score below 5) means the subject cannot be passed: the internal
			# grade is capped at 4.
			missing = len(scored) < len(all_lines)
			if (missing or any(line.score < 5 for line in scored)) and internal > 4:
				internal = 4
			rec.internal_score = internal

	@api.depends(
		"is_overridden",
		"grade_session_id.grade_outcome_line_ids.is_scored",
	)
	def _compute_internal_is_scored(self):
		# Kept apart from _compute_internal_score: writing the (computed-writable) internal_score would
		# skip a shared compute and leave this flag stale.
		for rec in self:
			if rec.is_overridden:
				rec.internal_is_scored = True
			else:
				rec.internal_is_scored = bool(rec.grade_session_id.grade_outcome_line_ids.filtered(
					lambda line: line.student_id == rec.student_id and line.is_scored
				))

	@api.depends(
		"internal_score",
		"internal_is_scored",
		"external_score",
		"external_is_scored",
		"grade_session_id.planning_id.internal_ponderation",
		"grade_session_id.planning_id.external_ponderation",
	)
	def _compute_computed_score(self):
		for rec in self:
			planning = rec.grade_session_id.planning_id
			if planning:
				internal_weight = planning.internal_ponderation / 100.0
				external_weight = planning.external_ponderation / 100.0
			else:
				internal_weight, external_weight = 1.0, 0.0

			# The computed grade needs every weighted component to be informed: a component only counts
			# as required when its ponderation is greater than 0 (e.g. subjects with no work placement
			# carry a 0% external weight and never need an external grade).
			internal_ok = rec.internal_is_scored or internal_weight == 0
			external_ok = rec.external_is_scored or external_weight == 0
			rec.computed_is_scored = internal_ok and external_ok and (rec.internal_is_scored or rec.external_is_scored)
			if rec.computed_is_scored:
				# Round half up (int(x + 0.5)).
				computed = int(rec.internal_score * internal_weight + rec.external_score * external_weight + 0.5)
				# The subject can only be passed when every weighted part is passed (>= 5): if the
				# internal or external part is failed, the computed grade is capped at 4.
				failed_part = (internal_weight > 0 and rec.internal_score < 5) or (external_weight > 0 and rec.external_score < 5)
				if failed_part and computed > 4:
					computed = 4
				rec.computed_score = computed
			else:
				rec.computed_score = 0

	@api.depends("computed_score")
	def _compute_final_score(self):
		for rec in self:
			rec.final_score = rec.computed_score

	@api.depends("computed_is_scored")
	def _compute_has_final(self):
		for rec in self:
			rec.has_final = rec.computed_is_scored

	def write(self, vals):
		# open: scoped teachers/tutors; board: only the group's tutor; final: only admin.
		for rec in self:
			if not rec.grade_session_id.can_edit:
				if rec.grade_session_id.state == "final":
					raise UserError(_("This evaluation session is final; only administrators can edit the grades."))
				raise UserError(_("This evaluation session is in the board stage; only the group's tutor (or an administrator) can edit the grades."))
		return super().write(vals)

	@api.constrains("internal_score", "external_score", "final_score")
	def _check_scores(self):
		for rec in self:
			if rec.internal_score < 0 or rec.internal_score > 10:
				raise ValidationError(_("The internal score must be within the range [0, 10]."))
			if rec.external_score < 0 or rec.external_score > 10:
				raise ValidationError(_("The external score must be within the range [0, 10]."))
			if rec.final_score < 0 or rec.final_score > 10:
				raise ValidationError(_("The final grade must be within the range [0, 10]."))

	@api.depends("student_id")
	def _compute_display_name(self):
		for rec in self:
			rec.display_name = rec.student_id.display_name or ""
