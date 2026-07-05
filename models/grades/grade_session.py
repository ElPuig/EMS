# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from psycopg2 import IntegrityError

grade_round_selection = [("1", "1a"), ("2", "2a"), ("3", "3a"), ("4", "4a")]
grade_state_selection = [("open", "Open"), ("board", "Board"), ("final", "Finalised")]

class ems_grade_session(models.Model):
	_name = "ems.grade_session"
	_description = "Grade session: student grading per learning outcome for a group, subject and round."
	_inherit = ['ems.base']
	_sql_constraints = [
		(
			'grade_session_is_duped',
			'UNIQUE(group_id, subject_id, round)',
			'A grade session already exists for this group, subject and round.' # Translated within 'create'.
		)
	]

	group_id = fields.Many2one(string="Group", comodel_name="ems.group", required=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
	allowed_subject_ids = fields.Many2many(related="group_id.study_id.subject_ids", store=False)
	round = fields.Selection(string="Round", selection=grade_round_selection, default="1", required=True)
	state = fields.Selection(string="State", selection=grade_state_selection, default="open", required=True, tracking=True)
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", default=lambda self: self._default_teacher_id())

	planning_id = fields.Many2one(string="Planning", comodel_name="ems.planning", compute="_compute_planning_id", store=True)
	has_planning = fields.Boolean(string="Has planning", compute="_compute_has_planning", store=True)
	can_edit = fields.Boolean(string="Can edit", compute="_compute_can_edit", store=False, help="Whether the current user may edit the grades at the session's current state.")

	grade_outcome_line_ids = fields.One2many(string="Grades per outcome", comodel_name="ems.grade_outcome_line", inverse_name="grade_session_id")
	grade_subject_line_ids = fields.One2many(string="Subject grades", comodel_name="ems.grade_subject_line", inverse_name="grade_session_id")

	@api.depends("group_id.study_id", "subject_id")
	def _compute_planning_id(self):
		for rec in self:
			rec.planning_id = False
			if rec.group_id.study_id and rec.subject_id:
				rec.planning_id = self.env["ems.planning"].search([
					("study_id", "=", rec.group_id.study_id.id),
					("subject_id", "=", rec.subject_id.id)
				], limit=1) or False

	@api.depends("planning_id")
	def _compute_has_planning(self):
		for rec in self:
			rec.has_planning = bool(rec.planning_id)

	@api.depends_context("uid")
	@api.depends("state", "group_id")
	def _compute_can_edit(self):
		# open: everyone in scope; board: only the group's tutor (and admin); final: only admin.
		is_admin = self.env.user.has_group("ems.group_admin")
		for rec in self:
			if is_admin:
				rec.can_edit = True
			elif rec.state == "open":
				rec.can_edit = True
			elif rec.state == "board":
				rec.can_edit = rec.group_id.tutor_id.user_id == self.env.user
			else:
				rec.can_edit = False

	@api.depends("group_id", "subject_id", "round")
	def _compute_display_name(self):
		labels = dict(grade_round_selection)
		for rec in self:
			rec.display_name = "%s %s (%s)" % (rec.group_id.name or "", rec.subject_id.display_name or "", labels.get(rec.round, ""))

	@api.onchange("group_id", "subject_id", "round")
	def _onchange_fill_students(self):
		for rec in self:
			rec.fill_students()

	def _default_teacher_id(self):
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	@api.model
	def _derive_teacher(self, group, subject):
		# The canonical teacher for a (group, subject) is the active ems.teaching entry; if there is
		# none, the group's tutor evaluates it; otherwise it is left empty to be assigned later.
		teaching = self.env["ems.teaching"].search([
			("group_id", "=", group.id),
			("subject_id", "=", subject.id),
			("active", "=", True),
		], limit=1)
		# Always return an hr.employee recordset (possibly empty) so callers can use `.id` safely.
		return teaching.teacher_id or group.tutor_id

	def fill_students(self):
		for rec in self:
			students = self.env["ems.enrollment"].search([
				("group_id", "=", rec.group_id.id),
				("subject_id", "=", rec.subject_id.id)
			]).mapped("student_id")

			# The outcomes to grade come from the planning; if there's no planning yet, fall back to the subject's outcomes.
			outcomes = rec.planning_id.planning_outcome_ids.mapped("outcome_id") or rec.subject_id.outcome_ids

			# Every evaluated outcome from an earlier round of the same group and subject is carried over:
			# the new line starts from the score of the most recent earlier round. Passed outcomes stay
			# locked (see grade_outcome_line.is_locked); failed ones are editable but keep their previous
			# score as a starting point.
			previous_scores = {}
			if rec.group_id and rec.subject_id and rec.round:
				best_round = {}
				for line in self.env["ems.grade_outcome_line"].search([
					("grade_session_id.group_id", "=", rec.group_id.id),
					("grade_session_id.subject_id", "=", rec.subject_id.id),
					("grade_session_id.round", "<", rec.round),
					("is_scored", "=", True),
				]):
					key = (line.student_id.id, line.outcome_id.id)
					line_round = line.grade_session_id.round
					# round is a single-digit selection, so a string comparison is enough to keep the latest.
					if key not in best_round or line_round > best_round[key]:
						best_round[key] = line_round
						previous_scores[key] = line.score

			outcome_cmds = [(5, 0, 0)]
			subject_cmds = [(5, 0, 0)]
			for student in students:
				subject_cmds.append((0, 0, {"student_id": student.id}))
				for outcome in outcomes:
					vals = {
						"student_id": student.id,
						"outcome_id": outcome.id,
						"is_auto_generated": True,
					}
					previous = previous_scores.get((student.id, outcome.id))
					if previous is not None:
						vals["score"] = previous
						vals["is_scored"] = True
					outcome_cmds.append((0, 0, vals))

			rec.grade_outcome_line_ids = outcome_cmds
			rec.grade_subject_line_ids = subject_cmds

	def reload_students(self):
		self.fill_students()

	@api.model
	def apply_grade_changes(self, outcome_vals, subject_vals):
		# Batch-write the buffered edits from the tutor view in a single request. Each line carries its own
		# values, so the client cannot merge them into one ORM write; grouping them here turns what used to
		# be one RPC per changed line into a single round trip. Outcome lines are written before subject
		# lines so the subject grades recompute from the new outcome scores. The per-line write() overrides
		# still enforce the locking and state rules. Computed fields recompute once at flush.
		OutcomeLine = self.env["ems.grade_outcome_line"]
		for line_id, vals in outcome_vals.items():
			OutcomeLine.browse(int(line_id)).write(vals)
		SubjectLine = self.env["ems.grade_subject_line"]
		for line_id, vals in subject_vals.items():
			SubjectLine.browse(int(line_id)).write(vals)
		return True

	@api.model_create_multi
	def create(self, vals_list):
		try:
			return super().create(vals_list)
		except IntegrityError as e:
			raise e if "grade_session_is_duped" not in str(e) else ValidationError(_('A grade session already exists for this group, subject and round. Please edit the existing one.'))

	def write(self, vals):
		if not self.env.user.has_group("ems.group_admin"):
			if "state" in vals:
				raise UserError(_("Only administrators can change the evaluation state."))
			# Archiving / unarchiving (active) is a write; only administrators may archive or restore sessions.
			if "active" in vals:
				raise UserError(_("Only administrators can archive or delete evaluation sessions."))
		return super().write(vals)
