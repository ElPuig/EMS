from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestGroupTour(HttpCase):

    def test_group_form_tabs_and_reinforcement_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin")

    def test_group_reactivate_archived_duplicate_tour(self):
        # Reinforcement groups (plain Name, no Many2one selection) keep this tour free of the
        # level->study->tutor selection fragility already noted in the tour above - only the
        # create()/write() duplicate-name-vs-archived-group behaviour is under test here, not
        # 'main' group creation itself (already covered by that other tour and test_group.py).
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archived Reinforcement Reactivate',
        }).active = False
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archived Reinforcement Cancel',
        }).active = False
        self.start_tour("/odoo", "ems_group_reactivate_archived_duplicate", login="admin")
