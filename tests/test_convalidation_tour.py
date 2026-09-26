import base64

from odoo.tests import HttpCase, tagged

from .common import mock_outgoing_email
from .test_portal_convalidation import create_portal_convalidation_fixtures


@tagged('post_install', '-at_install')
class TestConvalidationTour(HttpCase):
    """Issue #276 - proves every screen convalidations reach renders in a browser, each one for
    the least-privileged role that uses it: the request list/form for the two steps of the
    circuit (Head of Studies, then secretariat), the student form's stat button, CV in both
    grade views (the teacher who is also the group's tutor) and the portal page, where the
    student files a request and answers with more documentation. Logic is covered by
    test_convalidation.py and test_portal_convalidation.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_convalidation_fixtures(cls)
        cls.request = cls.env['ems.convalidation'].create({
            'student_id': cls.student.id, 'study_id': cls.study.id, 'course_id': cls.course.id,
            'line_ids': [(0, 0, {'subject_id': cls.subject.id})],
            'attachment_ids': [(0, 0, {
                'name': 'certificate.pdf', 'datas': base64.b64encode(b'%PDF-1.4 tour'),
            })],
        })

    def _convalidated_session(self):
        """The fixture teacher tutors the group and teaches the subject; the student's subject
        grade, in a closed round, is convalidated."""
        teacher_employee = self.teacher.employee_ids[:1]
        self.group.tutor_id = teacher_employee
        self.env['ems.enrollment'].create({
            'student_id': self.student.id, 'group_id': self.group.id, 'subject_id': self.subject.id})
        session = self.env['ems.grade_session'].search([
            ('group_id', '=', self.group.id), ('subject_id', '=', self.subject.id)], limit=1) \
            or self.env['ems.grade_session'].create({'group_id': self.group.id, 'subject_id': self.subject.id})
        session.teacher_id = teacher_employee
        session.fill_students()
        # A round at its evaluation board: completing the convalidation withdraws the student
        # from the subject, which deletes their line in any OPEN session only. The board round
        # keeps it - and it is the one the tutor's view still lists (it skips final rounds).
        session.state = 'board'
        self.request.line_ids.sudo().action_grant()
        self.request.sudo().action_validate()
        self.request.sudo().action_complete()
        self.assertTrue(session.grade_subject_line_ids.is_convalidated)
        return session

    def test_head_of_studies_resolves(self):
        self.start_tour("/odoo", "ems_convalidation_resolve", login=self.head_of_studies.login)
        self.assertEqual(self.request.state, 'in_progress')
        self.assertEqual(self.request.line_ids.state, 'granted')
        self.assertEqual(self.request.line_ids.grade, 8)

    def test_secretary_completes(self):
        self.request.line_ids.sudo().action_grant()
        self.request.sudo().action_validate()
        self.start_tour("/odoo", "ems_convalidation_complete", login=self.secretary.login)
        self.assertEqual(self.request.state, 'completed')

    def test_teacher_reads_the_current_course_history(self):
        self.request.line_ids.sudo().action_grant()
        self.request.sudo().action_validate()
        self.request.sudo().action_complete()
        record = self.env['ems.student.year_record'].search([
            ('student_id', '=', self.student.id), ('course_id', '=', self.course.id)])
        self.assertTrue(record.is_provisional)
        self.start_tour(f"/odoo/action-ems.action_year_record_list/{record.id}",
                        "ems_convalidation_history_current_course", login=self.teacher.login)

    def test_student_form_button(self):
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_convalidation_student_button",
                        login=self.head_of_studies.login)

    def test_grade_matrix_shows_cv(self):
        session = self._convalidated_session()
        self.start_tour(f"/odoo/action-ems.action_grade_session_tree/{session.id}",
                        "ems_convalidation_grade_matrix", login=self.teacher.login)

    def test_grade_tutor_matrix_shows_cv(self):
        self._convalidated_session()
        self.start_tour("/odoo", "ems_convalidation_grade_tutor_matrix", login=self.teacher.login)

    def test_portal_student_submits(self):
        self.request.action_cancel()
        self.start_tour("/my/convalidaciones", "ems_portal_convalidation_submit", login=self.student_user.login)
        submitted = self.env['ems.convalidation'].search([
            ('student_id', '=', self.student.id), ('state', '=', 'pending')])
        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted.basis, 'certificate')
        # The certificate filed with the request, plus the one answered with afterwards.
        self.assertEqual(sorted(submitted.attachment_ids.mapped('name')),
                         ['certificate.pdf', 'reply.pdf'])
