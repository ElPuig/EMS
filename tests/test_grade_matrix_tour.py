from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestGradeMatrixTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ems.group.name is computed from study_id.acronym/course/acronym for 'main' groups (any
        # override here is silently discarded) - the tour instead identifies the seeded session
        # by its subject's name, a plain writable field.
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TGMX',
            level={'name': 'Test Level (Grade Matrix Tour)'},
            study={'code': 'TGMX001', 'name': 'Test Study (Grade Matrix Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TGMX001', 'acronym': 'TGMX', 'name': 'Test Subject (Grade Matrix Tour)',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome1 = cls.env['ems.outcome'].create({
            'code': 'TGMX001_01RA', 'acronym': 'RA1', 'name': 'Outcome 1 (Grade Matrix Tour)',
            'subject_id': cls.subject.id,
        })
        cls.outcome2 = cls.env['ems.outcome'].create({
            'code': 'TGMX001_02RA', 'acronym': 'RA2', 'name': 'Outcome 2 (Grade Matrix Tour)',
            'subject_id': cls.subject.id,
        })
        cls.env['ems.planning'].create({
            'study_id': cls.study.id,
            'subject_id': cls.subject.id,
            'internal_ponderation': 90.0,
            'external_ponderation': 10.0,
            'planning_outcome_ids': [
                (0, 0, {'outcome_id': cls.outcome1.id, 'ponderation': 60.0}),
                (0, 0, {'outcome_id': cls.outcome2.id, 'ponderation': 40.0}),
            ],
        })
        # Firstname/lastname chosen so 'Alpha' sorts first (the matrix's default sort is by
        # lastname) - the tour edits the first row's first outcome cell, so the test needs to
        # know exactly which student that row belongs to, to assert on the right DB record.
        cls.student_first = cls.env['res.partner'].create({
            'name': 'Ada Alpha', 'firstname': 'Ada', 'lastname': 'Alpha', 'contact_type': 'student',
        })
        cls.student_second = cls.env['res.partner'].create({
            'name': 'Bea Beta', 'firstname': 'Bea', 'lastname': 'Beta', 'contact_type': 'student',
        })
        for student in (cls.student_first, cls.student_second):
            cls.env['ems.enrollment'].create({
                'student_id': student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
            })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Grade Matrix Tour)', 'employee_type': 'teacher',
        })
        cls.grade_session = cls.env['ems.grade_session'].create({
            'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '1',
            'teacher_id': cls.teacher_employee.id,
        })
        cls.grade_session.fill_students()

    def test_grade_matrix_entry_tour(self):
        self.start_tour("/odoo", "ems_grade_matrix_entry", login="admin")

        line = self.env['ems.grade_outcome_line'].search([
            ('grade_session_id', '=', self.grade_session.id),
            ('student_id', '=', self.student_first.id),
            ('outcome_id', '=', self.outcome1.id),
        ])
        self.assertEqual(len(line), 1)
        self.assertTrue(line.is_scored)
        self.assertEqual(line.score, 8)
