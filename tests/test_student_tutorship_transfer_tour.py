from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_role_employee, create_role_user, next_student_id


@tagged('post_install', '-at_install')
class TestStudentTutorshipTransferTour(HttpCase):
    """Issue #807: the secretary's office transfers a student's tutorship from the Studies tab, and
    the new tutor finds the student among their own in every view. See
    docs/en/developers/contacts/contact.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        level, study = create_level_study(cls, 'TTRT')
        official = create_role_employee(
            cls, create_role_user(cls, 'teacher', 'test_ttrt_official', name='TTRT Official Tutor'),
            name='TTRT Official Tutor')
        cls.new_user = create_role_user(cls, 'teacher', 'test_ttrt_new', name='TTRT New Tutor')
        new_tutor = create_role_employee(cls, cls.new_user, name='TTRT New Tutor')
        create_role_user(cls, 'secretary', 'test_ttrt_secretary', name='TTRT Secretary')
        Group = cls.env['ems.group']
        common = {'level_id': level.id, 'study_id': study.id, 'acronym': 'A'}
        cls.second = Group.create({**common, 'course': 2, 'tutor_id': official.id})
        cls.first = Group.create({**common, 'course': 1, 'tutor_id': new_tutor.id})
        cls.student = cls.env['res.partner'].create({
            'name': '0000 TTRT Transfer Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.second.id,
        })

    def test_secretary_transfers_the_tutorship_tour(self):
        self.start_tour("/odoo", "ems_student_tutorship_transfer", login="test_ttrt_secretary")
        self.assertEqual(self.student.transferred_group_id, self.first)
        self.assertEqual(self.student.main_group_id, self.second)

    def test_new_tutor_manages_the_student_tour(self):
        self.student.sudo().transferred_group_id = self.first
        self.start_tour("/odoo", "ems_student_tutorship_transfer_new_tutor", login="test_ttrt_new")
        self.assertIn('600000807', ''.join(self.student.mobile.split()))
