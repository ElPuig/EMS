from odoo.tests.common import TransactionCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user,
    next_student_id,
)


class TestStudentActionRights(TransactionCase):
    """A student's form only offers "Portal access", "Send authorizations" and "Request contact
    data" to whoever the matching assistant would let act on that student
    (res.partner.can_manage_portal_access / can_send_student_requests): otherwise the assistant
    opened only to drop the student. A tutor gets them on their own students, not on another
    group's."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_rights_tutor', name='TSAR Tutor')
        tutor = create_role_employee(cls, cls.tutor_user)
        other_tutor = create_role_employee(cls, create_role_user(
            cls, 'tutor', 'test_rights_other_tutor', name='TSAR Other Tutor'))
        create_head_of_studies_branch(cls, 'TSAR', tutor)
        __, __, group = create_level_study_group(cls, 'TSAR', group={'tutor_id': tutor.id})
        __, __, other_group = create_level_study_group(cls, 'TSAO', group={'tutor_id': other_tutor.id})
        cls.own, cls.foreign = cls.env['res.partner'].create([{
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': grp.id,
        } for name, grp in (('TSAR Own Student', group), ('TSAR Foreign Student', other_group))])
        cls.family = cls.env['res.partner'].create({'name': 'TSAR Family', 'contact_type': 'family'})

    def _rights(self, user, partner):
        partner = partner.with_user(user)
        return partner.can_manage_portal_access, partner.can_send_student_requests

    def test_tutor_only_on_own_students(self):
        self.assertEqual(self._rights(self.tutor_user, self.own), (True, True))
        self.assertEqual(self._rights(self.tutor_user, self.foreign), (False, False))

    def test_plain_teacher_on_no_student(self):
        teacher = create_role_user(self, 'teacher', 'test_rights_teacher')
        self.assertEqual(self._rights(teacher, self.own), (False, False))

    def test_secretary_on_every_student(self):
        secretary = create_role_user(self, 'secretary', 'test_rights_secretary')
        self.assertEqual(self._rights(secretary, self.foreign), (True, True))

    def test_head_of_studies_follows_each_assistant(self):
        # Requests: every student, like the assistants. Portal access: the portal assistant only
        # lets a Head of Studies act as the tutor scope, i.e. on their own branch's students.
        self.assertEqual(self._rights(self.head_of_studies, self.own), (True, True))
        self.assertEqual(self._rights(self.head_of_studies, self.foreign), (False, True))

    def test_nothing_on_a_family_contact(self):
        secretary = create_role_user(self, 'secretary', 'test_rights_secretary_family')
        self.assertEqual(self._rights(secretary, self.family), (False, False))
