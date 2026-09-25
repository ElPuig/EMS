from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestStudentPrivateNoteTour(HttpCase):
    """Issue #511: the public and private notes tabs of a student's form, as its tutor and as a
    teacher outside the tutoring team. See docs/en/developers/contacts/contact.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_private_note_tour_tutor')
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_private_note_tour_teacher')
        __, __, group = create_level_study_group(
            cls, 'SPNT', group={'tutor_id': create_role_employee(cls, cls.tutor_user).id})
        cls.student = cls.env['res.partner'].create({
            'name': 'Private Note Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id, 'comment': '<p>Public tour note</p>',
            'private_notes': '<p>Private tour note</p>',
        })
        cls.url = f"/odoo/action-ems.action_student_kanban/{cls.student.id}"

    def test_tutor_edits_private_notes(self):
        self.start_tour(self.url, "ems_student_private_note_tutor", login="test_private_note_tour_tutor")
        self.assertIn('Written by the tutor', self.student.private_notes)

    def test_teacher_only_sees_public_notes(self):
        self.start_tour(self.url, "ems_student_private_note_teacher", login="test_private_note_tour_teacher")
