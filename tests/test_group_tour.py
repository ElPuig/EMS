from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestGroupTour(HttpCase):

    def test_group_form_tabs_and_reinforcement_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin")

    def test_group_reactivate_archived_duplicate_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
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

    def test_group_archive_confirmation_tour(self):
        # Reinforcement groups again, for the same low-fragility reason as above - a plain Name
        # and a Many2many student list, no Many2one selection needed to set the scene up.
        student_accept = self.env['res.partner'].create({
            'name': 'Tour Archive Confirm Student Accept', 'contact_type': 'student',
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archive Confirm Accept',
            'reinforcement_student_ids': [(6, 0, [student_accept.id])],
        })
        student_decline = self.env['res.partner'].create({
            'name': 'Tour Archive Confirm Student Decline', 'contact_type': 'student',
        })
        self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'Tour Archive Confirm Decline',
            'reinforcement_student_ids': [(6, 0, [student_decline.id])],
        })
        self.start_tour("/odoo", "ems_group_archive_confirmation", login="admin")
