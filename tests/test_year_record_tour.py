from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestYearRecordTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ems.student.year_record is create="0" in the UI - records only ever come from
        # generate_for_students(), the same recipe tests/test_year_record.py uses.
        cls.current_course = cls.env['ems.course'].create({'start': 2098, 'end': 2099})
        cls.env.company.current_course_id = cls.current_course

        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'YRTR',
            level={'name': 'Test Level (Year Record Tour)'},
            study={'code': 'YRTR001', 'name': 'Test Study (Year Record Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'YRTR001', 'acronym': 'YRTR', 'name': 'Year Record Tour Subject',
            'study_ids': [(4, cls.study.id)],
        })
        cls.outcome = cls.env['ems.outcome'].create({
            'code': 'YRTR001_01RA', 'acronym': 'RA1', 'name': 'Year Record Tour Outcome',
            'subject_id': cls.subject.id,
        })
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subject.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.outcome.id, 'ponderation': 100.0})],
        })
        # Makes the study a "flow" study, required by generate_for_students' academic-result logic.
        cls.env['sale.order.template'].create({
            'name': 'Year Record Tour Template', 'ems_study_id': cls.study.id, 'study_year': 1,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Year Record Tour Student', 'contact_type': 'student', 'main_group_id': cls.group.id,
        })
        cls.env['ems.enrollment'].create({
            'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id,
        })
        session = cls.env['ems.grade_session'].create({
            'group_id': cls.group.id, 'subject_id': cls.subject.id, 'round': '1',
        })
        session.fill_students()
        line = session.grade_outcome_line_ids.filtered(
            lambda l: l.student_id == cls.student and l.outcome_id == cls.outcome)
        line.write({'score': 8, 'is_scored': True})

        cls.year_record = cls.env['ems.student.year_record'].generate_for_students(
            cls.student, cls.current_course)

    def test_year_record_list_and_subject_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_year_record_list_and_subject", login="admin")

    def test_year_record_partner_tab_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_year_record_partner_tab", login="admin")
