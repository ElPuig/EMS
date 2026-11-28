# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import date

from odoo import api, fields, models

from ..grades.grade_session import grade_round_selection

BOARD_TYPE_XMLID = "__import__.minute_type_board"
WRITE_TASK = "ems.mail_activity_board_minute_write"
# The statistics' thresholds, as a share of the group's hours in the term (the tutor's spreadsheet).
ABSENCE_THRESHOLD = 0.25
UNJUSTIFIED_THRESHOLD = 0.05
BOARD_KINDS = ("board_difficulties", "board_statistics", "board_students")


class EmsMinuteBoardDifficulty(models.Model):
    """One of the four areas of the group's difficulties an evaluation board reviews (issue #880),
    as in the tutor's spreadsheet: how they were detected, the group's diagnosis, the teaching
    team's objectives and their priority."""
    _name = "ems.minute.board.difficulty"
    _description = "Group difficulty reviewed by an evaluation board."
    _order = "minute_id, area"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete="cascade", index=True)
    area = fields.Selection(string="Difficulty", required=True, selection=[
        ("a", "A. Prior knowledge and basic competences"),
        ("b", "B. Expectations and interests"),
        ("c", "C. Study techniques and habits"),
        ("d", "D. Behaviour"),
    ])
    tests = fields.Text(string="Tests", help="How the difficulty was detected: an initial questionnaire, an interview, observation...")
    diagnosis = fields.Text(string="Group result or diagnosis")
    objectives = fields.Text(string="Teaching team's objectives")
    priority = fields.Selection(string="Priority", selection=[("high", "High"), ("medium", "Medium"), ("low", "Low")])


class EmsMinuteBoardStudent(models.Model):
    """A student of the group in an evaluation board's minute (issue #880): the outcomes passed and
    evaluated in the round (from the grades), whether they work, the teaching team's comments, which
    stay in the minute, and the tutor's comment for the student and the family, which the portal and
    the grades' PDF show once the round's grades are published."""
    _name = "ems.minute.board.student"
    _description = "Student reviewed by an evaluation board."
    _order = "minute_id, student_lastname, student_id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(string="Student", comodel_name="res.partner", required=True, index=True)
    student_lastname = fields.Char(related="student_id.lastname", store=True)
    passed_count = fields.Integer(string="Outcomes passed")
    evaluated_count = fields.Integer(string="Outcomes evaluated")
    works = fields.Boolean(string="Works")
    comments = fields.Text(string="Teaching team's comments", help="Stay in the minute: never shown to the student or the family.")
    family_comment = fields.Text(string="Tutor's comment for the family",
                                 help="Shown to the student and the family in the portal and the grades' PDF once the round's grades are published.")


class EmsMinute(models.Model):
    _inherit = "ems.minute"

    grade_round = fields.Selection(string="Evaluation", selection=grade_round_selection, tracking=True,
                                   help="The round an evaluation board's minute is about.")
    board_difficulty_ids = fields.One2many(string="Group difficulties", comodel_name="ems.minute.board.difficulty",
                                           inverse_name="minute_id")
    board_student_ids = fields.One2many(string="Students", comodel_name="ems.minute.board.student", inverse_name="minute_id")
    board_withdrawals = fields.Text(string="Withdrawals (students and reasons)")
    board_absence_count = fields.Integer(string="Students missing more than 25% of the hours")
    board_unjustified_count = fields.Integer(string="Students with unjustified absences above 5% of the hours")
    board_working_count = fields.Integer(string="Students who work", compute="_compute_board_working_count")
    board_period_from = fields.Date(string="Term from", readonly=True)
    board_period_to = fields.Date(string="Term until", readonly=True)
    board_kinds = fields.Char(compute="_compute_board_kinds",
                              help="The evaluation board sections the minute's type has, comma-separated: which blocks the form shows.")

    @api.depends("board_student_ids.works")
    def _compute_board_working_count(self):
        for minute in self:
            minute.board_working_count = len(minute.board_student_ids.filtered("works"))

    @api.depends("type_id.section_ids.kind")
    def _compute_board_kinds(self):
        for minute in self:
            minute.board_kinds = ",".join(kind for kind in BOARD_KINDS if kind in minute.type_id.section_ids.mapped("kind"))

    # --- creation, when a group's sessions reach the board ------------------------------------------

    @api.model
    def _ems_create_board_minutes(self, sessions):
        """One evaluation board minute per group and round of `sessions` that just moved to the
        board, unless it already exists (developer, issue #880): written by the group's tutor, who
        gets a quiet task, with the students, their outcomes, the statistics and the four
        difficulty areas already filled in. sudo: whoever changes the sessions' state (the Head
        of Studies) need not be able to create the tutor's minute."""
        board_type = self.env.ref(BOARD_TYPE_XMLID, raise_if_not_found=False)
        if not board_type:
            return self.browse()
        Minute = self.sudo()
        created = Minute
        for group, grade_round in {(session.group_id, session.round) for session in sessions}:
            if Minute.search_count([("type_id", "=", board_type.id), ("group_id", "=", group.id),
                                    ("grade_round", "=", grade_round)]):
                continue
            tutor = group.tutor_id
            minute = Minute.create({
                "type_id": board_type.id,
                "group_id": group.id,
                "grade_round": grade_round,
                "redactor_employee_id": tutor.id or False,
                "board_difficulty_ids": [(0, 0, {"area": area}) for area in ("a", "b", "c", "d")],
            })
            minute._ems_board_prefill()
            created |= minute
        created._ems_sync_board_task()
        return created

    def _ems_board_students(self):
        """The group's students: those it tutors (tutorship_group_id), the ones the board talks about."""
        self.ensure_one()
        return self.env["res.partner"].sudo().search([
            ("tutorship_group_id", "=", self.group_id.id), ("contact_type", "=", "student")])

    def _ems_board_prefill(self):
        """Fill the students and the statistics, once: the tutor corrects them by hand afterwards
        (developer, issue #880)."""
        for minute in self.sudo():
            students = minute._ems_board_students()
            minute.board_student_ids = [(5, 0, 0)] + [(0, 0, {"student_id": student.id}) for student in students]
            minute.action_board_refresh_grades()
            period_from, period_to = minute._ems_board_period()
            withdrawals = minute._ems_board_withdrawals(period_from, period_to)
            absent, unjustified = minute._ems_board_absences(students, period_from, period_to)
            minute.write({
                "board_period_from": period_from,
                "board_period_to": period_to,
                "board_withdrawals": withdrawals or False,
                "board_absence_count": absent,
                "board_unjustified_count": unjustified,
            })

    def action_board_refresh_grades(self):
        """The outcomes passed and evaluated in the round, per student, from the round's grades of
        every session: filled on creation and again on request while the minute is open (the grades
        can change during the board). Two searches for the whole minute."""
        for minute in self:
            lines = minute.board_student_ids
            if not lines or not minute.grade_round:
                continue
            counts = defaultdict(lambda: [0, 0])
            outcome_lines = self.env["ems.grade_outcome_line"].sudo().search([
                ("student_id", "in", lines.student_id.ids),
                ("grade_session_id.round", "=", minute.grade_round),
                ("is_scored", "=", True),
            ])
            for line in outcome_lines:
                count = counts[line.student_id.id]
                count[1] += 1
                if line.score >= 5:
                    count[0] += 1
            for line in lines:
                passed, evaluated = counts[line.student_id.id]
                line.write({"passed_count": passed, "evaluated_count": evaluated})
        return True

    def _ems_board_period(self):
        """The term the statistics cover: from the group's previous board minute (or the start of
        the course, 1 September) until today."""
        self.ensure_one()
        today = self.env["ems.datetime_utils"].get_local_today()
        previous = self.sudo().search([
            ("type_id", "=", self.type_id.id), ("group_id", "=", self.group_id.id),
            ("grade_round", "<", self.grade_round), ("date", "!=", False)], order="grade_round desc", limit=1)
        if previous:
            return previous.date, today
        course = self.env.company.current_course_id
        start = date(course.start, 9, 1) if course and course.start else date(today.year if today.month >= 9 else today.year - 1, 9, 1)
        return start, today

    def _ems_board_withdrawals(self, period_from, period_to):
        """The group's students who withdrew or were expelled in the term, each with the reason
        registered, one per line."""
        self.ensure_one()
        enrolled = self.env["ems.enrollment"].sudo().with_context(active_test=False).search(
            [("group_id", "=", self.group_id.id)]).student_id
        gone = enrolled.with_context(active_test=False).filtered(
            lambda student: student.exit_type in ("withdrawal", "expulsion") and student.exit_date
            and period_from <= student.exit_date <= period_to)
        return "\n".join(f"{student.name}: {student.exit_reason or ''}".rstrip(": ") for student in gone.sorted("name"))

    def _ems_board_absences(self, students, period_from, period_to):
        """How many students missed more than 25% of their hours in the term, and how many have
        unjustified absences above 5%, from the roll-calls (ems.attendance_session_line). Hours are
        each session's length: one grouped query for the whole group. Raw SQL: the length lives on
        the session header (start_time/end_time), which _read_group cannot sum through the line."""
        if not students:
            return 0, 0
        justified = self.env.ref("ems.attendance_status_justified").id
        self.env["ems.attendance_session_line"].flush_model()
        self.env["ems.attendance_session_header"].flush_model(["start_time", "end_time", "active"])
        self.env.cr.execute("""
            SELECT line.student_id,
                   SUM(header.end_time - header.start_time) AS total,
                   SUM(CASE WHEN status.category = 'absence' THEN header.end_time - header.start_time ELSE 0 END) AS absent,
                   SUM(CASE WHEN status.category = 'absence' AND status.id != %s
                            THEN header.end_time - header.start_time ELSE 0 END) AS unjustified
              FROM ems_attendance_session_line line
              JOIN ems_attendance_session_header header ON header.id = line.attendance_session_id
              JOIN ems_attendance_status status ON status.id = line.status_id
             WHERE line.student_id IN %s AND line.date BETWEEN %s AND %s
               AND line.active AND header.active
             GROUP BY line.student_id
        """, (justified, tuple(students.ids), period_from, period_to))
        absent = unjustified = 0
        for __, total, absent_hours, unjustified_hours in self.env.cr.fetchall():
            if total:
                absent += absent_hours / total > ABSENCE_THRESHOLD
                unjustified += unjustified_hours / total > UNJUSTIFIED_THRESHOLD
        return absent, unjustified

    def _ems_sync_board_task(self):
        """A quiet "Write the evaluation board minute" task for its writer (the group's tutor) while
        it is being written; done once it is sent for approval."""
        activity_type = self.env.ref(WRITE_TASK)
        for minute in self.sudo().filtered("grade_round"):
            users = minute.redactor_employee_id.user_id if minute.state in ("draft", "meeting") else self.env["res.users"]
            minute._ems_sync_user_tasks(activity_type, users, minute.date or self.env["ems.datetime_utils"].get_local_today(),
                                        done=minute.state in ("to_approve", "approved"))

    def write(self, vals):
        result = super().write(vals)
        if {"state", "redactor_employee_id"} & set(vals):
            self.filtered("grade_round")._ems_sync_board_task()
        return result


class EmsGradeSession(models.Model):
    _inherit = "ems.grade_session"

    def write(self, vals):
        result = super().write(vals)
        if vals.get("state") == "board":
            self.env["ems.minute"]._ems_create_board_minutes(self)
        return result


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _ems_portal_board_comments(self):
        """{round: the tutor's comment for the family} from the evaluation board minutes (issue
        #880), for the rounds the portal shows. sudo, scoped to this student."""
        self.ensure_one()
        lines = self.env["ems.minute.board.student"].sudo().search([
            ("student_id", "=", self.id), ("family_comment", "!=", False), ("minute_id.grade_round", "!=", False)])
        return {line.minute_id.grade_round: line.family_comment for line in lines}
