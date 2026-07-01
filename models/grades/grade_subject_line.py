# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ems_grade_subject_line(models.Model):
	_name = "ems.grade_subject_line"
	_description = "Grade subject line: a student's subject grade within a grade session (computed from outcomes, teacher can override)."
	_order = "student_id asc"

	grade_session_id = fields.Many2one(string="Grade session", comodel_name="ems.grade_session", required=True, ondelete="cascade")
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	image_1920 = fields.Binary(string="Image", related="student_id.image_1920")

	internal_score = fields.Float(string="Internal score", compute="_compute_scores", store=True, help="Weighted average of the student's informed outcome scores.")
	external_score = fields.Float(string="External score", default=0.0, help="External grade (e.g. work placement); informed manually.")
	computed_score = fields.Float(string="Computed grade", compute="_compute_scores", store=True, help="Suggested subject grade applying the planning ponderations.")
	final_score = fields.Float(string="Final grade", compute="_compute_final_score", store=True, readonly=False, help="Final subject grade. Defaults to the computed grade but the teacher can override it.")
	is_overridden = fields.Boolean(string="Overridden", compute="_compute_is_overridden", store=True)

	# Used only for access-rule filtering.
	teacher_id = fields.Many2one(string="Teacher", related="grade_session_id.teacher_id", store=False)

	@api.depends(
		"external_score",
		"grade_session_id.planning_id",
		"grade_session_id.planning_id.internal_ponderation",
		"grade_session_id.planning_id.external_ponderation",
		"grade_session_id.grade_outcome_line_ids.score",
		"grade_session_id.grade_outcome_line_ids.is_scored",
		"grade_session_id.grade_outcome_line_ids.ponderation",
	)
	def _compute_scores(self):
		for rec in self:
			lines = rec.grade_session_id.grade_outcome_line_ids.filtered(
				lambda line: line.student_id == rec.student_id and line.is_scored
			)
			total_pond = sum(line.ponderation for line in lines)
			if total_pond:
				rec.internal_score = round(sum(line.score * line.ponderation for line in lines) / total_pond, 2)
			else:
				rec.internal_score = 0.0

			planning = rec.grade_session_id.planning_id
			if planning:
				internal_weight = planning.internal_ponderation / 100.0
				external_weight = planning.external_ponderation / 100.0
			else:
				internal_weight, external_weight = 1.0, 0.0
			rec.computed_score = round(rec.internal_score * internal_weight + rec.external_score * external_weight, 2)

	@api.depends("computed_score")
	def _compute_final_score(self):
		# Computed-but-writable: defaults to the computed grade; a manual override persists until the
		# outcome scores change again.
		for rec in self:
			rec.final_score = rec.computed_score

	@api.depends("final_score", "computed_score")
	def _compute_is_overridden(self):
		for rec in self:
			rec.is_overridden = round(rec.final_score, 2) != round(rec.computed_score, 2)

	def write(self, vals):
		# open: scoped teachers/tutors; board: only the group's tutor; final: only admin.
		for rec in self:
			if not rec.grade_session_id.can_edit:
				if rec.grade_session_id.state == "final":
					raise UserError(_("This evaluation session is final; only administrators can edit the grades."))
				raise UserError(_("This evaluation session is in the board stage; only the group's tutor (or an administrator) can edit the grades."))
		return super().write(vals)

	@api.constrains("external_score", "final_score")
	def _check_scores(self):
		for rec in self:
			if rec.external_score < 0 or rec.external_score > 10:
				raise ValidationError(_("The external score must be within the range [0, 10]."))
			if rec.final_score < 0 or rec.final_score > 10:
				raise ValidationError(_("The final grade must be within the range [0, 10]."))

	@api.depends("student_id")
	def _compute_display_name(self):
		for rec in self:
			rec.display_name = rec.student_id.display_name or ""
