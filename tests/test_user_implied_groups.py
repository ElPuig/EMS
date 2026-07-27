from odoo.tests.common import TransactionCase


class TestUserImpliedGroups(TransactionCase):
    """res.users._sync_ems_implied_groups() (models/employees/user.py) — compensates for
    Odoo's own implied-group mechanism being grant-only (it never revokes). Previously
    untested."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ems.group_secretary's own implied_ids (security/groups.xml) directly grants
        # base.group_partner_manager — a real, single-hop external group to test against.
        cls.group_secretary = cls.env.ref('ems.group_secretary')
        cls.group_partner_manager = cls.env.ref('base.group_partner_manager')
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test User (Implied Groups)',
            'login': 'test_user_for_implied_groups',
        })

    def test_removing_ems_group_revokes_its_implied_external_group(self):
        self.user.write({'groups_id': [(4, self.group_secretary.id)]})
        self.assertIn(self.group_partner_manager, self.user.groups_id)

        self.user.write({'groups_id': [(3, self.group_secretary.id)]})

        self.assertNotIn(self.group_partner_manager, self.user.groups_id)

    def test_manual_external_group_unrelated_to_ems_is_not_touched(self):
        group_sale_manager = self.env.ref('sales_team.group_sale_manager')
        self.user.write({'groups_id': [(4, group_sale_manager.id)]})

        # Assigning and removing an unrelated EMS group must never touch a group that was
        # never implied by any EMS group this user held.
        self.user.write({'groups_id': [(4, self.group_secretary.id)]})
        self.user.write({'groups_id': [(3, self.group_secretary.id)]})

        self.assertIn(group_sale_manager, self.user.groups_id)
