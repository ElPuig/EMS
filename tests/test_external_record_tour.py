# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestExternalRecordTour(HttpCase):
    """A course taken at another centre added to the academic history (issue #585), driven by
    the secretariat from the student form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.past_course = Course.create({'start': 2078, 'end': 2079})
        cls.env.company.current_course_id = Course.create({'start': 2079, 'end': 2080})
        cls.level, cls.study = create_level_study(
            cls, 'EXRT', level={'name': 'External Record Tour Level'},
            study={'code': 'EXRTSTD', 'acronym': 'EXRT', 'name': 'External Record Tour Study'})
        # Module A carries a work placement weight, so it is left with its final pending.
        cls.subject_a, cls.subject_b = [cls.env['ems.subject'].create({
            'code': f'EXRTSUB{suffix}', 'acronym': f'EXRT{suffix}',
            'name': f'External Record Tour Subject {suffix}', 'study_ids': [(4, cls.study.id)],
        }) for suffix in 'AB']
        plannings = []
        for subject, outcome_count, external in ((cls.subject_a, 2, 10.0), (cls.subject_b, 1, 0.0)):
            outcomes = cls.env['ems.outcome'].create([{
                'code': f'{subject.code}_0{index}RA', 'acronym': f'RA{index}',
                'name': f'{subject.name} RA{index}', 'subject_id': subject.id,
            } for index in range(1, outcome_count + 1)])
            plannings.append({
                'study_id': cls.study.id, 'subject_id': subject.id, 'course_id': cls.past_course.id,
                'internal_ponderation': 100.0 - external, 'external_ponderation': external,
                'planning_outcome_ids': [(0, 0, {'outcome_id': outcome.id,
                                                 'ponderation': 100.0 / outcome_count})
                                         for outcome in outcomes],
            })
        cls.env['ems.planning'].create(plannings)
        cls.student = cls.env['res.partner'].create({
            'name': 'External Record Tour Student', 'contact_type': 'student',
            'student_id': next_student_id()})
        # create_role_user sets lang to en_US, which the English selectors of the tour need.
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_external_record_tour')

    def test_external_record_tour(self):
        self.start_tour(f"/odoo/action-ems.action_student_kanban/{self.student.id}",
                        "ems_external_record", login=self.secretary.login)
        record = self.student.year_record_ids
        self.assertTrue(record.is_external)
        self.assertEqual(record.course_id, self.past_course)
        self.assertEqual(record.origin_centre_name, 'Institut Extern Tour')
        self.assertEqual(record.subject_record_ids.subject_id, self.subject_a | self.subject_b)
        subject_a = record.subject_record_ids.filtered(lambda line: line.subject_id == self.subject_a)
        self.assertEqual(subject_a.outcome_record_ids.mapped('final_score'), [7, 6])
        self.assertTrue(subject_a.final_pending)
        self.assertEqual(record.academic_result, 'full')
