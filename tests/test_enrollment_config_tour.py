from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestEnrollmentConfigTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'EGCT',
            level={'name': 'Test Level (Enrollment Config Tour)'},
            study={'code': 'EGCT001', 'name': 'Test Study (Enrollment Config Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'EGCT001', 'acronym': 'EGCT', 'name': 'Enrollment Config Tour Subject',
            'study_ids': [(4, cls.study.id)],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Enrollment Config Tour Student', 'contact_type': 'student',
        })

    def test_enrollment_config_crud_tour(self):
        self.start_tour("/odoo", "ems_enrollment_config_crud", login="admin")

        enrollment = self.env['ems.enrollment'].search([
            ('student_id', '=', self.student.id), ('subject_id', '=', self.subject.id),
        ])
        self.assertEqual(len(enrollment), 1)
        self.assertEqual(enrollment.group_id, self.group)
