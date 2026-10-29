from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user


class TestWorkgroup(TransactionCase):

    def test_employee_ids_relation(self):
        # employee_ids is hr.employee.public, not hr.employee — compare by id.
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee (Workgroup)', 'employee_type': 'teacher',
        })
        workgroup = self.env['ems.workgroup'].create({
            'name': 'Test 02', 'employee_ids': [(4, employee.id)],
        })
        self.assertIn(employee.id, workgroup.employee_ids.ids)


class TestWorkgroupQualityCommittee(TransactionCase):
    """The quality committee's access (group_quality, the Quality menu) follows the members of the
    committee workgroup (the catalogue's ems.quality): joining gives it, leaving takes it away, and
    nothing else touches it - neither another workgroup nor someone given it by hand."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref('ems.group_quality')
        cls.committee = cls.env.ref('ems.quality')
        cls.user = create_role_user(cls, 'teacher', 'committee.member@example.com', name='Committee Member')
        cls.employee = create_role_employee(cls, cls.user)

    def _sees_quality_menu(self, user):
        menu = self.env.ref('ems.menu_quality')
        return menu.id in self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()

    def test_joining_the_committee_opens_the_quality_menu(self):
        self.assertFalse(self._sees_quality_menu(self.user))
        self.committee.employee_ids = [(4, self.employee.id)]
        self.assertIn(self.user, self.group.users)
        self.assertTrue(self._sees_quality_menu(self.user))

    def test_leaving_the_committee_closes_it(self):
        self.committee.employee_ids = [(4, self.employee.id)]
        self.committee.employee_ids = [(3, self.employee.id)]
        self.assertNotIn(self.user, self.group.users)
        self.assertFalse(self._sees_quality_menu(self.user))

    def test_another_workgroup_gives_no_access(self):
        self.env['ems.workgroup'].create({'name': 'Not the committee', 'employee_ids': [(4, self.employee.id)]})
        self.assertNotIn(self.user, self.group.users)

    def test_a_member_given_by_hand_is_kept(self):
        """Someone added to the committee group from the user form, without being in the
        workgroup, keeps it whatever happens to the workgroup's members."""
        other = create_role_user(self, 'teacher', 'committee.byhand@example.com', name='By Hand Member')
        other.groups_id = [(4, self.group.id)]
        self.committee.employee_ids = [(4, self.employee.id)]
        self.committee.employee_ids = [(3, self.employee.id)]
        self.assertIn(other, self.group.users)

    def test_quality_coordination_keeps_it_on_leaving(self):
        self.user.groups_id = [(4, self.env.ref('ems.group_quality_admin').id)]
        self.committee.employee_ids = [(4, self.employee.id)]
        self.committee.employee_ids = [(3, self.employee.id)]
        self.assertIn(self.user, self.group.users)

    def test_the_sync_catches_up_with_members_added_behind_its_back(self):
        """What every install and upgrade runs (data/main/sync_quality_committee.xml): members the
        committee already had get the group."""
        self.env.cr.execute(
            "INSERT INTO hr_employee_public_ems_workgroup_rel (ems_workgroup_id, hr_employee_public_id) VALUES (%s, %s)",
            (self.committee.id, self.employee.id))
        self.env.invalidate_all()
        self.env['ems.workgroup']._ems_sync_quality_committee()
        self.assertIn(self.user, self.group.users)
