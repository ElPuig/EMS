from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


class TestStudentPrivateNote(TransactionCase):
    """Issue #511: a student's private notes (tutoring) are read and written only by the student's
    tutor, every chief above that tutor (hr.employee.tutor_scope_user_ids), the guidance and
    coexistence teams and the academic admin - never by the rest of the teachers, who keep reading
    the public notes (res.partner.comment)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_private_note_tutor', name='SPN Tutor')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        create_head_of_studies_branch(cls, 'SPN', cls.tutor)
        __, __, group = create_level_study_group(cls, 'SPN', group={'tutor_id': cls.tutor.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'Private Note Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id, 'comment': '<p>Public</p>',
        })
        cls.student.private_notes = '<p>Private</p>'
        cls.teacher = create_role_user(cls, 'teacher', 'test_private_note_teacher', name='SPN Teacher')
        cls.orientation = create_role_user(cls, 'orientation', 'test_private_note_orientation')
        cls.coexistence = create_role_user(cls, 'coexistence', 'test_private_note_coexistence')
        cls.academic_admin = create_role_user(cls, 'academic_admin', 'test_private_note_admin')
        cls.secretary = create_role_user(cls, 'secretary', 'test_private_note_secretary')
        cls.allowed = (cls.tutor_user, cls.department_chief, cls.head_of_studies,
                       cls.orientation, cls.coexistence, cls.academic_admin)
        cls.denied = (cls.teacher, cls.secretary, cls.other_department_chief, cls.other_head_of_studies)

    def test_allowed_users_read_private_notes(self):
        for user in self.allowed:
            student = self.student.with_user(user)
            self.assertTrue(student.can_access_private_notes, user.login)
            self.assertIn('Private', student.private_notes, user.login)

    def test_denied_users_never_read_private_notes(self):
        for user in self.denied:
            student = self.student.with_user(user)
            self.assertFalse(student.can_access_private_notes, user.login)
            self.assertFalse(student.private_notes, user.login)
            self.assertFalse(student.read(['private_notes'])[0]['private_notes'], user.login)

    def test_every_teacher_reads_public_notes(self):
        for user in self.denied + self.allowed:
            self.assertIn('Public', self.student.with_user(user).comment, user.login)

    def test_allowed_users_write_private_notes(self):
        # Guidance and coexistence write private notes of students they don't tutor, whose
        # res.partner record they cannot otherwise write.
        for user in self.allowed:
            self.student.with_user(user).write({'private_notes': f'<p>By {user.login}</p>'})
            self.assertIn(user.login, self.student.private_notes)

    def test_denied_users_cannot_write_private_notes(self):
        for user in self.denied:
            with self.assertRaises(AccessError, msg=user.login):
                self.student.with_user(user).write({'private_notes': '<p>Intrusion</p>'})
        self.assertIn('Private', self.student.private_notes)

    def test_private_notes_are_not_reachable_directly(self):
        for user in self.denied + (self.tutor_user, self.orientation, self.coexistence):
            with self.assertRaises(AccessError, msg=user.login):
                self.env['ems.student.private_note'].with_user(user).search([])

    def test_create_with_private_notes(self):
        student = self.env['res.partner'].create({
            'name': 'Private Note New Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'private_notes': '<p>From creation</p>',
        })
        self.assertIn('From creation', student.private_notes)

    def test_one_note_per_student(self):
        self.student.private_notes = '<p>Second</p>'
        notes = self.env['ems.student.private_note'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(len(notes), 1)
        self.assertIn('Second', notes.notes)

    def test_new_tutor_takes_over(self):
        new_tutor_user = create_role_user(self, 'tutor', 'test_private_note_new_tutor')
        self.student.main_group_id.tutor_id = create_role_employee(self, new_tutor_user)
        self.assertIn('Private', self.student.with_user(new_tutor_user).private_notes)
        self.assertFalse(self.student.with_user(self.tutor_user).private_notes)

    def test_portal_user_never_reads_any_notes(self):
        # The student reading their own record through the portal user (RPC read), which the
        # form's own note under each tab promises can't happen.
        portal = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private Note Portal', 'login': 'test_private_note_portal',
            'partner_id': self.student.id, 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        student = self.student.with_user(portal)
        with self.assertRaises(AccessError):
            student.read(['comment'])
        self.assertFalse(student.read(['private_notes'])[0]['private_notes'])
