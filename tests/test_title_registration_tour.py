# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email, next_student_id


@tagged('post_install', '-at_install')
class TestTitleRegistrationTour(HttpCase):
    """Titles registered by the secretariat: from the import and from the student form
    (issue #635)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Leaving the centre revokes the portal and schedules the Google suspension notice.
        mock_outgoing_email(cls)
        Course = cls.env['ems.course']
        cls.title_course = Course.create({'start': 2086, 'end': 2087})
        cls.env.company.current_course_id = Course.create({'start': 2087, 'end': 2088})
        # create_role_user sets lang to en_US.
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_title_tour')

    def _student(self, name, student_id=None):
        student = self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': student_id or next_student_id()})
        record = self.env['ems.student.year_record'].create({
            'student_id': student.id, 'course_id': self.title_course.id})
        return student, record

    def test_title_import_tour(self):
        # Its IDALU is the one in the tour's file.
        student, record = self._student('Title Import Tour Student', student_id='TESTTITLETOUR1')
        self.start_tour("/odoo/action-ems.action_title_import_wizard", "ems_title_import",
                        login=self.secretary.login)
        self.assertTrue(record.title_obtained)
        self.assertEqual(student.contact_type, 'alumni')

    def test_title_register_tour(self):
        student, record = self._student('Title Register Tour Student')
        self.start_tour(f"/odoo/action-ems.action_student_kanban/{student.id}", "ems_title_register",
                        login=self.secretary.login)
        self.assertTrue(record.title_obtained)
        self.assertEqual(student.contact_type, 'alumni')
