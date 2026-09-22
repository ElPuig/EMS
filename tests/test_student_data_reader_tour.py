# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import (
    create_level_study_group, create_role_employee, create_role_user, create_student_academic_file,
    mock_outgoing_email,
)


@tagged('post_install', '-at_install')
class TestStudentDataReaderTour(HttpCase):
    """Browser coverage for issue #393: the records being readable is not the same as the
    screens rendering them. Both traps this feature hit are invisible to a TransactionCase -
    the Students list re-domains itself inside an ir.actions.server, and the Secretary tab's
    authorizations are resolved by walking the enrolment (a sale.order)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Signing an authorization can notify - see CLAUDE.md's "Email safety in tests".
        mock_outgoing_email(cls)

        # The tutor of the seeded group: nobody driving the tours is this employee, so every
        # record below is out of their own tutees' scope.
        cls.tutor_user = create_role_user(
            cls, 'tutor', 'tour_tutor_reader', name='Tour Tutor (Reader)', email='tour_tutor_reader@example.com')
        cls.tutor_employee = create_role_employee(cls, cls.tutor_user, name='Tour Tutor Employee (Reader)')

        # 'lang' (set by create_role_user) is required because the tours assert on English
        # labels ("Secretary", "Academic history") - a fresh res.users does not reliably
        # default to en_US.
        cls.guidance_user = create_role_user(
            cls, 'orientation', 'tour_guidance', name='Tour Guidance', email='tour_guidance@example.com')
        cls.teacher_user = create_role_user(
            cls, 'teacher', 'tour_teacher', name='Tour Plain Teacher', email='tour_teacher@example.com')

        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TOUR',
            level={'name': 'Test Level (Reader Tour)'},
            study={'code': 'TOUR001', 'name': 'Test Study (Reader Tour)'},
            group={'name': 'Test Group (Reader Tour)', 'tutor_id': cls.tutor_employee.id},
        )
        cls.academic_file = create_student_academic_file(cls, 'TOUR', cls.group)
        cls.student = cls.academic_file['student']

    def test_guidance_student_file_tour(self):
        """The Students list, then the Secretary and Academic history tabs, as a guidance user."""
        self.assertFalse(
            self.env['ems.group'].search([('tutor_id.user_id', '=', self.guidance_user.id)]),
            "the tour is only meaningful if this user tutors nobody")
        self.assertTrue(self.academic_file['authorization'])

        self.start_tour("/odoo", "ems_guidance_students_list", login="tour_guidance")
        # Opened by URL: clicking the row in that list lands on the enrolment, since the list
        # carries ems_current_enrollment_id as a many2one column.
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_guidance_student_file",
                        login="tour_guidance")

    def test_guidance_edits_special_needs_tour(self):
        """Issue #465: guidance sets the special educational needs of a student it does not tutor."""
        self.assertFalse(self.student.special_needs)

        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_guidance_special_needs",
                        login="tour_guidance")

        self.assertEqual(self.student.special_needs, 'nee_a')

    def test_teacher_academic_history_tour(self):
        """The widened scope: a plain teacher reaches the Academic history menu and its records."""
        self.assertFalse(
            self.env['ems.group'].search([('tutor_id.user_id', '=', self.teacher_user.id)]),
            "the tour is only meaningful if this user tutors nobody")

        self.start_tour("/odoo", "ems_teacher_academic_history", login="tour_teacher")
