import ast

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_employee, create_role_user, next_student_id


class TestStudentTutorshipTransfer(TransactionCase):
    """Issue #807: a student whose tutorship is transferred to another group keeps their main group
    (the one in Esfer@, with its tutor for the grades), while the transferred group's tutor takes
    over as their tutor for everything else: access, notices, the student walkouts they join."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        level, study = create_level_study(cls, 'TTR')
        cls.official_user = create_role_user(cls, 'tutor', 'test_ttr_official', name='TTR Official Tutor')
        cls.official = create_role_employee(cls, cls.official_user)
        cls.new_user = create_role_user(cls, 'tutor', 'test_ttr_new', name='TTR New Tutor')
        cls.new_tutor = create_role_employee(cls, cls.new_user)
        cls.secretary = create_role_user(cls, 'secretary', 'test_ttr_secretary', name='TTR Secretary')
        Group = cls.env['ems.group']
        common = {'level_id': level.id, 'study_id': study.id, 'acronym': 'A'}
        cls.second = Group.create({**common, 'course': 2, 'tutor_id': cls.official.id})
        cls.first = Group.create({**common, 'course': 1, 'tutor_id': cls.new_tutor.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'TTR Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.second.id,
        })

    def _transfer(self, group=None):
        self.student.with_user(self.secretary).write({'transferred_group_id': (group or self.first).id})

    def test_tutor_follows_the_transfer(self):
        self.assertEqual(self.student.tutor_id, self.official)
        self._transfer()
        self.assertEqual(self.student.tutorship_group_id, self.first)
        self.assertEqual(self.student.tutor_id, self.new_tutor)
        self.assertEqual(self.student.official_tutor_id, self.official)
        self.assertEqual(self.student.main_group_id, self.second)
        self.student.with_user(self.secretary).write({'transferred_group_id': False})
        self.assertEqual(self.student.tutor_id, self.official)

    def test_edit_rights_move_to_the_new_tutor(self):
        self._transfer()
        self.student.with_user(self.new_user).check_access('write')
        with self.assertRaises(AccessError):
            self.student.with_user(self.official_user).check_access('write')
        # Stored: the record rules match on it in SQL.
        found = self.env['res.partner'].search([('tutor_id.tutor_scope_user_ids', '=', self.new_user.id)])
        self.assertIn(self.student, found)

    def test_group_tutor_change_reaches_transferred_students(self):
        self._transfer()
        other = create_role_employee(self, create_role_user(self, 'tutor', 'test_ttr_other', name='TTR Other'))
        self.first.tutor_id = other
        self.assertEqual(self.student.tutor_id, other)
        self.second.tutor_id = self.new_tutor
        self.assertEqual(self.student.official_tutor_id, self.new_tutor)
        self.assertEqual(self.student.tutor_id, other)

    def test_only_the_secretary_or_management_transfers(self):
        with self.assertRaises(AccessError):
            self.student.with_user(self.official_user).write({'transferred_group_id': self.first.id})
        self.student.with_user(self.official_user).invalidate_recordset(['can_transfer_tutorship'])
        self.assertFalse(self.student.with_user(self.official_user).can_transfer_tutorship)
        self.assertTrue(self.student.with_user(self.secretary).can_transfer_tutorship)
        for role in ('head_of_studies', 'academic_admin'):
            manager = create_role_user(self, role, f'test_ttr_{role}', name=f'TTR {role}')
            self.student.with_user(manager).write({'transferred_group_id': self.first.id})
            self.student.with_user(manager).write({'transferred_group_id': False})

    def test_transfer_to_the_main_group_is_refused(self):
        with self.assertRaises(ValidationError):
            self._transfer(self.second)

    def test_moving_into_the_transferred_group_ends_the_transfer(self):
        self._transfer()
        self.student.write({'main_group_id': self.first.id})
        self.assertFalse(self.student.transferred_group_id)
        self.assertEqual(self.student.tutor_id, self.new_tutor)

    def test_leaving_the_centre_ends_the_transfer(self):
        self._transfer()
        self.student._ems_clear_operational_records()
        self.assertFalse(self.student.transferred_group_id)

    def test_justification_offers_the_new_tutor_the_student(self):
        self._transfer()
        for user, expected in ((self.new_user, True), (self.official_user, False)):
            justification = self.env['ems.attendance_justification'].with_user(user).new(
                {'teacher_id': user.employee_id.id})
            students = self.env['res.partner'].search(ast.literal_eval(justification.student_domain))
            self.assertEqual(self.student in students, expected)

    def test_walkout_counts_the_student_in_the_transferred_group(self):
        self._transfer()
        # The walkout proposal gathers its students by tutorship_group_id (student_walkout.py).
        Partner = self.env['res.partner']
        self.assertIn(self.student, Partner.search([('tutorship_group_id', '=', self.first.id)]))
        self.assertNotIn(self.student, Partner.search([('tutorship_group_id', '=', self.second.id)]))

    def test_my_students_follows_the_transfer(self):
        Partner = self.env['res.partner']
        self._transfer()
        for user, expected in ((self.new_user, True), (self.official_user, False)):
            mine = Partner.with_user(user).search([('is_my_student', '=', True)])
            self.assertEqual(self.student in mine, expected)
