from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestGradeTutorMatrixTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TGTM',
            level={'name': 'Test Level (Grade Tutor Matrix Tour)'},
            study={'code': 'TGTM001', 'name': 'Test Study (Grade Tutor Matrix Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGTM001', 'acronym': 'TGTM', 'name': 'Test Subject (Grade Tutor Matrix Tour)',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'TGTM001_01RA', 'acronym': 'RA1', 'name': 'Outcome 1 (Grade Tutor Matrix Tour)',
            'subject_id': cls.subject.id,
        })
        cls.env['ems.planning'].create({
            'study_id': cls.study.id,
            'subject_id': cls.subject.id,
            'internal_ponderation': 90.0,
            'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome.id, 'ponderation': 100.0})],
        })
        # Firstname/lastname chosen so 'Alpha' sorts first (the matrix's default sort is by
        # lastname) - the tour edits the first-shown student's first cell, then pages to the
        # second, so the test needs to know exactly which student is which.
        cls.student_first = cls.env['res.partner'].create({
            'name': 'Tgtm Alpha', 'firstname': 'Tgtm', 'lastname': 'Alpha', 'contact_type': 'student',
        })
        cls.student_second = cls.env['res.partner'].create({
            'name': 'Tgtm Beta', 'firstname': 'Tgtm', 'lastname': 'Beta', 'contact_type': 'student',
        })
        for student in (cls.student_first, cls.student_second):
            cls.env['ems.enrollment'].create({
                'student_id': student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
            })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Grade Tutor Matrix Tour)', 'employee_type': 'teacher',
        })
        cls.grade_session = cls.env['ems.grade_session'].create({
            'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '1',
            'teacher_id': cls.teacher_employee.id,
        })
        cls.grade_session.fill_students()

        # ems.grade_tutor_matrix (static/src/js/backend/grade_tutor_matrix.js) resolves the
        # tutored groups from the CLICKING user's own tutorship (group_id.tutor_id.user_id),
        # not from any teacher_id on the session - a dedicated tutor user/employee is needed,
        # the same pattern already established for the daily roll-call tour
        # (attendance_passlist_tour.py: real teacher accounts only, not admin).
        cls.tutor_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Grade Tutor Matrix Tour Tutor', 'login': 'test_tutor_grade_tutor_matrix_tour',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Grade Tutor Matrix Tour Tutor', 'employee_type': 'teacher',
            'user_id': cls.tutor_user.id,
        })
        cls.group.tutor_id = cls.tutor_employee

    def test_grade_tutor_matrix_entry_tour(self):
        self.start_tour("/odoo", "ems_grade_tutor_matrix_entry", login="test_tutor_grade_tutor_matrix_tour")

        line = self.env['ems.grade_outcome_line'].search([
            ('grade_session_id', '=', self.grade_session.id),
            ('student_id', '=', self.student_first.id),
            ('outcome_id', '=', self.outcome.id),
        ])
        self.assertEqual(len(line), 1)
        self.assertTrue(line.is_scored)
        self.assertEqual(line.score, 7)
