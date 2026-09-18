# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestYearRecordDiligenceTour(HttpCase):
    """The diligence wizard driven by the secretariat (issue #493).

    Logged in as a secretary, not admin: the feature exists because this is secretariat work,
    and the wizard is the only thing on the whole academic history that is not read-only for
    that role."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].create({'start': 2086, 'end': 2087})
        cls.level, cls.study = create_level_study(
            cls, 'DLGT', level={'name': 'Diligence Tour Level'},
            study={'code': 'DLGTSTD', 'acronym': 'DLGT', 'name': 'Diligence Tour Study'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'DLGTSUB', 'acronym': 'DLGT', 'name': 'Diligence Tour Subject',
            'study_ids': [(4, cls.study.id)]})
        cls.student = cls.env['res.partner'].create({
            'name': 'Diligence Tour Student', 'contact_type': 'student',
            'student_id': next_student_id()})
        # A closed course with a single subject failed on its second outcome: what the
        # diligence resolves. ems.student.year_record is create="0" in the UI, so the record is
        # seeded here exactly like tests/test_year_record_tour.py does.
        cls.year_record = cls.env['ems.student.year_record'].create({
            'student_id': cls.student.id, 'course_id': cls.course.id,
            'study_id': cls.study.id, 'study_name': cls.study.display_name,
            'academic_result': 'partial',
            'subject_record_ids': [(0, 0, {
                'subject_id': cls.subject.id, 'subject_name': cls.subject.display_name,
                'internal_weight': 100.0, 'external_weight': 0.0,
                'internal_grade': 4, 'final_grade': 4, 'has_final': True, 'state': 'failed',
                'outcome_record_ids': [
                    (0, 0, {'outcome_name': 'RA1', 'weight': 50.0,
                            'final_score': 7, 'final_is_scored': True}),
                    (0, 0, {'outcome_name': 'RA2', 'weight': 50.0,
                            'final_score': 4, 'final_is_scored': True}),
                ]})]})
        # create_role_user sets lang to en_US, which the English selectors of the tour need.
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_diligence_tour')

    def test_year_record_diligence_tour(self):
        self.start_tour("/odoo", "ems_year_record_diligence", login=self.secretary.login)
        subject_record = self.year_record.subject_record_ids
        self.assertEqual(subject_record.state, 'passed')
        self.assertEqual(subject_record.internal_grade, 6)
        self.assertEqual(subject_record.diligence_user_id, self.secretary)
        self.assertEqual(self.year_record.academic_result, 'full')
