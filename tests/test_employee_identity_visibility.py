from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_head_of_studies_branch, create_role_employee, create_role_user, mock_outgoing_email

IDENTITY_FIELDS = ['scoped_identification_id', 'scoped_ssnid', 'can_view_identity']


class TestEmployeeIdentityVisibility(TransactionCase):
    """A Department Chief sees, read-only, the identity document and social security number of
    the employees in their own department, and so does everyone above them in the chain of
    command (hr.employee.tutor_scope_user_ids) - never those of another chief's department.
    The Head of Studies (teachers only, issue #391) and the secretariat (all staff) edit them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # hr.employee writes can post chatter notes (_gw_notify_missing_fields) - see CLAUDE.md's
        # "Email safety in tests".
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_identity_teacher', name='IDV Teacher')
        cls.teacher = create_role_employee(
            cls, cls.teacher_user, identification_id='11111111H', ssnid='081234567890')
        create_head_of_studies_branch(cls, 'IDV', cls.teacher)
        cls.colleague = create_role_user(cls, 'teacher', 'test_identity_colleague', name='IDV Colleague')
        create_role_employee(cls, cls.colleague, parent_id=cls.teacher.parent_id.id)
        cls.secretary = create_role_user(cls, 'secretary', 'test_identity_secretary', name='IDV Secretary')
        cls.asp = cls.env['hr.employee'].create({'name': 'IDV ASP', 'employee_type': 'asp'})

    def _read_as(self, user):
        return self.teacher.with_user(user).read(IDENTITY_FIELDS)[0]

    def _assert_sees(self, user):
        values = self._read_as(user)
        self.assertTrue(values['can_view_identity'])
        self.assertEqual(values['scoped_identification_id'], '11111111H')
        self.assertEqual(values['scoped_ssnid'], '081234567890')

    def _assert_blind(self, user):
        values = self._read_as(user)
        self.assertFalse(values['can_view_identity'])
        self.assertFalse(values['scoped_identification_id'])
        self.assertFalse(values['scoped_ssnid'])

    def test_own_department_chief_sees(self):
        self._assert_sees(self.department_chief)

    def test_chain_above_sees(self):
        self._assert_sees(self.head_of_studies)
        director = create_role_user(self, 'director', 'test_identity_director', name='IDV Director')
        self.env.company.director_id = create_role_employee(self, director)
        self._assert_sees(director)

    def test_employee_sees_own(self):
        self._assert_sees(self.teacher_user)

    def test_other_department_chief_blind(self):
        self._assert_blind(self.other_department_chief)

    def test_colleague_blind(self):
        self._assert_blind(self.colleague)

    def test_hr_officer_outside_chain_sees(self):
        # The Head of Studies' group implies hr.group_hr_user, which already reads the native
        # identification_id/ssnid on any record (issue #391): hiding them here would only be
        # cosmetic.
        self._assert_sees(self.other_head_of_studies)

    def test_hierarchy_change_applies_at_once(self):
        self.teacher.parent_id = self.other_department_chief.employee_id
        self._assert_sees(self.other_department_chief)
        self._assert_blind(self.department_chief)

    def _write_identity_as(self, user, employee):
        employee.with_user(user).write({'identification_id': '33333333P', 'ssnid': '080000000001'})
        self.assertEqual(employee.identification_id, '33333333P')
        self.assertEqual(employee.ssnid, '080000000001')

    def test_head_of_studies_edits_teacher(self):
        self._write_identity_as(self.other_head_of_studies, self.teacher)

    def test_head_of_studies_cannot_edit_asp(self):
        with self.assertRaises(AccessError):
            self.asp.with_user(self.head_of_studies).write({'identification_id': '33333333P'})

    def test_secretary_edits_teacher_and_asp(self):
        self._write_identity_as(self.secretary, self.teacher)
        self._write_identity_as(self.secretary, self.asp)

    def test_secretary_cannot_delete_staff(self):
        with self.assertRaises(AccessError):
            self.asp.with_user(self.secretary).unlink()

    def test_department_chief_cannot_edit(self):
        with self.assertRaises(AccessError):
            self.teacher.with_user(self.department_chief).write({'identification_id': '33333333P'})
