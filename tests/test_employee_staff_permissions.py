# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import mock_outgoing_email


class TestEmployeeStaffPermissions(TransactionCase):
    """Issue #391: the Head of Studies / Deputy Head of Studies (ems.group_head_of_studies) and
    the TAC coordinator (ems.group_tac) may create and edit teachers.

    Both groups imply hr.group_hr_user, Odoo's own HR officer group: these posts manage a
    teacher's record in full, private information included, and that native group is also the
    only thing that lifts the field-level groups="hr.group_hr_user" on private_email - the
    address the Google Workspace credentials are actually delivered to.

    That native group is broader than this issue asked for, and security/rules/employees.xml
    narrows it back down on two axes, both covered here: write/create bounded to
    employee_type = 'teacher', and deletion still refused. Read access is deliberately left
    untouched throughout.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # hr.employee.create() posts a chatter note when the Google Workspace data is incomplete
        # (_gw_notify_missing_fields), which can reach real followers - see CLAUDE.md's
        # "Email safety in tests".
        mock_outgoing_email(cls)
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_head_of_studies = cls.env.ref('ems.group_head_of_studies')
        cls.group_tac = cls.env.ref('ems.group_tac')
        cls.group_tac_admin = cls.env.ref('ems.group_tac_admin')
        cls.group_academic_admin = cls.env.ref('ems.group_academic_admin')
        cls.role_tac = cls.env.ref('ems.role_tac')
        cls.base_user = cls.env.ref('base.group_user')

        cls.hos_user = cls._create_user('test_391_hos', cls.group_head_of_studies)
        cls.tac_user = cls._create_user('test_391_tac', cls.group_tac)
        cls.teacher_user = cls._create_user('test_391_teacher', cls.group_teacher)
        cls.admin_user = cls._create_user('test_391_admin', cls.group_academic_admin)

        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test 391 Teacher',
            'employee_type': 'teacher',
            'private_email': 'staff.perms@example.com',
        })
        cls.asp = cls.env['hr.employee'].create({
            'name': 'Test 391 ASP',
            'employee_type': 'asp',
        })

    @classmethod
    def _create_user(cls, login, group):
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': f'Test 391 {login}',
            'login': login,
            'groups_id': [(6, 0, [cls.base_user.id, group.id])],
        })

    def _employee_as(self, user):
        return self.env['hr.employee'].with_user(user)

    # ------------------------------------------------------------------
    # Head of Studies / Deputy Head of Studies
    # ------------------------------------------------------------------
    def test_head_of_studies_can_create_teacher(self):
        employee = self._employee_as(self.hos_user).create({
            'name': 'Created by HoS',
            'employee_type': 'teacher',
        })
        self.assertTrue(employee.exists())

    def test_head_of_studies_can_edit_teacher(self):
        self.teacher.with_user(self.hos_user).write({'name': 'Renamed by HoS'})
        self.assertEqual(self.teacher.name, 'Renamed by HoS')

    def test_head_of_studies_cannot_create_asp(self):
        with self.assertRaises(AccessError):
            self._employee_as(self.hos_user).create({
                'name': 'ASP created by HoS',
                'employee_type': 'asp',
            })

    def test_head_of_studies_cannot_edit_asp(self):
        with self.assertRaises(AccessError):
            self.asp.with_user(self.hos_user).write({'name': 'Renamed by HoS'})

    def test_head_of_studies_can_still_read_asp(self):
        """The rules deliberately leave perm_read alone, so nothing that could be seen
        before this issue stops being visible."""
        self.assertEqual(self.asp.with_user(self.hos_user).name, 'Test 391 ASP')

    def test_head_of_studies_cannot_delete_teacher(self):
        """hr.group_hr_user does grant unlink on hr.employee, so this is entirely down to
        rule_hr_employee_no_unlink_staff_manager - the test that the narrowing works."""
        with self.assertRaises(AccessError):
            self.teacher.with_user(self.hos_user).unlink()

    # ------------------------------------------------------------------
    # private_email: needed to deliver the Google Workspace credentials
    # ------------------------------------------------------------------
    def test_head_of_studies_can_read_private_email(self):
        """Carries groups="hr.group_hr_user" on the field itself, so before this issue the
        field did not exist at all for this user - and neither did the "required" the employee
        form puts on it, which is why a teacher could be created without one."""
        self.assertEqual(
            self.teacher.with_user(self.hos_user).private_email,
            'staff.perms@example.com')

    def test_head_of_studies_can_write_private_email(self):
        self.teacher.with_user(self.hos_user).write({'private_email': 'new.hos@example.com'})
        self.assertEqual(self.teacher.private_email, 'new.hos@example.com')

    def test_tac_can_write_private_email(self):
        self.teacher.with_user(self.tac_user).write({'private_email': 'new.tac@example.com'})
        self.assertEqual(self.teacher.private_email, 'new.tac@example.com')

    def test_plain_teacher_cannot_read_private_email(self):
        """The field stays closed to everybody else: a teacher must not read a colleague's
        personal address."""
        with self.assertRaises(AccessError):
            self.teacher.with_user(self.teacher_user).private_email

    def test_google_account_requires_private_email(self):
        """The functional reason private_email had to become reachable: without it the
        Google Workspace account is never created, so the credentials are never delivered."""
        no_email = self.env['hr.employee'].create({
            'name': 'Test 391 No Personal Email',
            'employee_type': 'teacher',
        })
        self.assertIn('Personal email', no_email._gw_missing_fields())
        self.assertFalse(no_email._gw_ready())
        self.teacher.invalidate_recordset()
        self.assertEqual(self.teacher._gw_missing_fields(), [])

    # ------------------------------------------------------------------
    # TAC coordinator
    # ------------------------------------------------------------------
    def test_tac_can_create_teacher(self):
        employee = self._employee_as(self.tac_user).create({
            'name': 'Created by TAC',
            'employee_type': 'teacher',
        })
        self.assertTrue(employee.exists())

    def test_tac_can_edit_teacher(self):
        self.teacher.with_user(self.tac_user).write({'name': 'Renamed by TAC'})
        self.assertEqual(self.teacher.name, 'Renamed by TAC')

    def test_tac_cannot_edit_asp(self):
        with self.assertRaises(AccessError):
            self.asp.with_user(self.tac_user).write({'name': 'Renamed by TAC'})

    def test_tac_cannot_delete_teacher(self):
        with self.assertRaises(AccessError):
            self.teacher.with_user(self.tac_user).unlink()

    # ------------------------------------------------------------------
    # No regression for the roles that already had (or lacked) these rights
    # ------------------------------------------------------------------
    def test_plain_teacher_cannot_edit_teacher(self):
        with self.assertRaises(AccessError):
            self.teacher.with_user(self.teacher_user).write({'name': 'Renamed by teacher'})

    def test_academic_admin_can_still_edit_asp(self):
        """group_academic_admin implies group_director -> group_head_of_studies, so without
        rule_hr_employee_write_all it would inherit the teacher-only restriction and lose the
        ASP write access it has today."""
        self.asp.with_user(self.admin_user).write({'name': 'Renamed by admin'})
        self.assertEqual(self.asp.name, 'Renamed by admin')

    def test_academic_admin_keeps_unlink_on_employee(self):
        """rule_hr_employee_write_all is what wins this back: group_academic_admin implies
        group_director -> group_head_of_studies, so it also picks up the "never delete" rule
        aimed at the staff managers, and without a counterpart it would lose deletion too.

        Asserts the permission on hr.employee itself rather than calling unlink(), because a
        real delete additionally cascades into resource.calendar (every teacher has a personal
        one), where only base.group_system has unlink - so an academic Administrator holding
        nothing else has never been able to delete an employee end to end. That is structural
        and predates this issue; what matters here is that the new rules did not narrow
        hr.employee itself, and that they do narrow it for the staff managers."""
        self.assertTrue(self.teacher.with_user(self.admin_user).has_access('unlink'))
        self.assertFalse(self.teacher.with_user(self.hos_user).has_access('unlink'))

    # ------------------------------------------------------------------
    # read_only reflects the record rule, not just the model-level ACL
    # ------------------------------------------------------------------
    def test_read_only_false_for_head_of_studies_on_teacher(self):
        self.assertFalse(self.teacher.with_user(self.hos_user).read_only)

    def test_read_only_true_for_head_of_studies_on_asp(self):
        self.assertTrue(self.asp.with_user(self.hos_user).read_only)

    # ------------------------------------------------------------------
    # role_tac catalog entry and its group sync
    # ------------------------------------------------------------------
    def test_role_tac_catalog_entry(self):
        self.assertEqual(self.role_tac.employee_type, 'teacher')
        self.assertFalse(self.role_tac.unipersonal, "The TAC post can be held by a team.")
        self.assertEqual(self.role_tac.group_id, self.group_tac_admin)

    def test_role_tac_is_manually_assignable(self):
        """Unlike the 7 hierarchy-managed roles, role_tac has no department/company backing:
        it is assigned by hand from the employee form."""
        self.assertFalse(self.role_tac.is_hierarchy_managed)

    def test_assign_role_tac_adds_group(self):
        user = self._create_user('test_391_tac_holder', self.group_teacher)
        employee = self.env['hr.employee'].create({
            'name': 'Test 391 TAC Holder',
            'employee_type': 'teacher',
            'user_id': user.id,
        })
        employee.write({'role_ids': [(4, self.role_tac.id)]})
        self.assertIn(self.group_tac_admin, user.groups_id)
        self.assertTrue(user.has_group('ems.group_tac'))

    def test_assign_role_tac_from_the_role_side_adds_group(self):
        """Assigning from the role's own "Assigned to" list must sync the security groups too.

        This is a different write path: it writes ems.role.employee_ids, never
        hr.employee.write(), so the sync hanging off the latter never ran. Found in the field
        (issue #391) - a TAC coordinator assigned this way held the role but none of its
        permissions, and got an AccessError on resource.calendar when creating a teacher."""
        user = self._create_user('test_391_tac_role_side', self.group_teacher)
        employee = self.env['hr.employee'].create({
            'name': 'Test 391 TAC Role Side',
            'employee_type': 'teacher',
            'user_id': user.id,
        })
        self.role_tac.write({'employee_ids': [(4, employee.id)]})
        self.assertIn(self.group_tac_admin, user.groups_id)
        self.assertTrue(user.has_group('ems.group_tac'))

    def test_unassign_role_tac_from_the_role_side_removes_group(self):
        user = self._create_user('test_391_tac_role_side_out', self.group_teacher)
        employee = self.env['hr.employee'].create({
            'name': 'Test 391 TAC Role Side Out',
            'employee_type': 'teacher',
            'user_id': user.id,
        })
        self.role_tac.write({'employee_ids': [(4, employee.id)]})
        self.role_tac.write({'employee_ids': [(3, employee.id)]})
        self.assertNotIn(self.group_tac_admin, user.groups_id)

    def test_unassign_role_tac_removes_group(self):
        user = self._create_user('test_391_tac_leaver', self.group_teacher)
        employee = self.env['hr.employee'].create({
            'name': 'Test 391 TAC Leaver',
            'employee_type': 'teacher',
            'user_id': user.id,
        })
        employee.write({'role_ids': [(4, self.role_tac.id)]})
        employee.write({'role_ids': [(3, self.role_tac.id)]})
        self.assertNotIn(self.group_tac_admin, user.groups_id)
