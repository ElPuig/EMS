# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools

# A student's whole academic history in one list (issue #672): one line per course of the per-course
# history (ems.student.year_record) and one per previous curriculum record
# (ems.student.previous_curriculum_record). A read-only SQL view: the two models keep their own data
# and every process keeps working on its own one; this only shows them together, on the student
# form and on the convalidation request. Opening a line opens the record behind it.


class EmsStudentHistoryLine(models.Model):
    _name = 'ems.student.history_line'
    _description = 'Academic history line: a course of the history or a previous curriculum record.'
    _auto = False
    # Newest first, as the history is read: the oldest course (or previous curriculum) at the bottom.
    _order = 'start_year desc, id desc'

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', readonly=True)
    year_record_id = fields.Many2one(string="Year record", comodel_name='ems.student.year_record',
                                     readonly=True)
    previous_curriculum_record_id = fields.Many2one(
        string="Previous curriculum record", comodel_name='ems.student.previous_curriculum_record',
        readonly=True)
    is_previous_curriculum = fields.Boolean(string="Previous curriculum", readonly=True)
    # The course ("2024-2025"), or the years of a previous curriculum ("2020-2022").
    course_name = fields.Char(string="Course", readonly=True)
    start_year = fields.Integer(string="From year", readonly=True)
    is_provisional = fields.Boolean(string="Current course", readonly=True)
    is_external = fields.Boolean(string="Previous record", readonly=True)
    study_name = fields.Char(string="Study name", readonly=True)
    group_name = fields.Char(string="Group name", readonly=True)
    centre_name = fields.Char(string="Origin centre", readonly=True)
    tutor_name = fields.Char(string="Tutor name", readonly=True)
    academic_result = fields.Selection(string="Academic result", readonly=True, selection=[
        ('full', 'Fully passed'),
        ('partial', 'Partially passed'),
        ('repeating', 'Repeating'),
        ('withdrawn', 'Withdrawn'),
    ])
    title_obtained = fields.Boolean(string="Title obtained", readonly=True)
    subject_count = fields.Integer(string="Subjects taken", readonly=True)
    attendance_rate = fields.Float(string="Attendance (%)", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Even ids for the courses, odd for the previous curricula: unique across both.
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT record.id * 2 AS id,
                       record.student_id,
                       record.id AS year_record_id,
                       NULL::integer AS previous_curriculum_record_id,
                       FALSE AS is_previous_curriculum,
                       course.name AS course_name,
                       course.start AS start_year,
                       record.is_provisional,
                       record.is_external,
                       record.study_name,
                       record.group_name,
                       record.origin_centre_name AS centre_name,
                       record.tutor_name,
                       record.academic_result,
                       record.title_obtained,
                       (SELECT count(*) FROM ems_student_year_record_subject subject
                         WHERE subject.record_id = record.id) AS subject_count,
                       record.attendance_rate
                  FROM ems_student_year_record record
                  JOIN ems_course course ON course.id = record.course_id
                UNION ALL
                SELECT previous.id * 2 + 1,
                       previous.student_id,
                       NULL,
                       previous.id,
                       TRUE,
                       CASE WHEN previous.start_year > 0
                            THEN previous.start_year || '-' || previous.end_year END,
                       previous.start_year,
                       FALSE,
                       FALSE,
                       previous.curriculum_name,
                       NULL,
                       previous.centre_name,
                       NULL,
                       NULL,
                       previous.title_obtained,
                       (SELECT count(*) FROM ems_student_previous_curriculum_record_line line
                         WHERE line.record_id = previous.id AND line.kind = 'module'),
                       NULL
                  FROM ems_student_previous_curriculum_record previous
            )
        """)

    @api.depends('course_name', 'study_name')
    def _compute_display_name(self):
        for line in self:
            line.display_name = f"{line.study_name or ''} ({line.course_name or ''})"

    def action_open_record(self):
        """The record behind the line, in a dialog, as the history opened it before (issue #672)."""
        self.ensure_one()
        record = self.year_record_id or self.previous_curriculum_record_id
        return {
            'type': 'ir.actions.act_window',
            'res_model': record._name,
            'res_id': record.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
