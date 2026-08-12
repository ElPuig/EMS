from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestWithdrawalTour(HttpCase):

    def _seed_student(self, name):
        # "0000 " prefix: res.partner's _order is "name", so these sort first on the
        # list's very first page among the ~1000+ real students already in this DB.
        return self.env['res.partner'].create({
            'name': '0000 %s' % name, 'contact_type': 'student',
        })

    def test_generic_archive_action_opens_withdrawal_wizard_tour(self):
        # There is no "Withdrawal" button anymore: archiving a student (form cog-menu, or
        # list multi-selection) IS the withdrawal flow now — see toggle_active on
        # res.partner. Covers one record and several, then confirms the archived
        # (now former) student still shows up under the "Former students" filter.
        # To observe these tours in a real browser during development:
        #   self.start_tour("/odoo", "ems_archive_action_single_opens_wizard", login="admin", watch=True)
        self._seed_student('Archive Action Tour Single')
        self._seed_student('Archive Action Tour Bulk A')
        self._seed_student('Archive Action Tour Bulk B')
        # step_delay: all three tours load action_student_kanban's list view, ~1100 rows
        # in this DB — confirmed flaky without it (clicks occasionally lost to layout
        # reflow while the list is still settling, on different steps in different runs,
        # not just one specific selector). A small pause between steps gives the DOM time
        # to settle before the next interaction.
        self.start_tour("/odoo", "ems_archive_action_single_opens_wizard", login="admin", step_delay=300)
        self.start_tour("/odoo", "ems_archive_action_bulk_opens_wizard", login="admin", step_delay=300)
        self.start_tour("/odoo", "ems_archive_action_shows_in_list", login="admin", step_delay=300)

    def test_generic_archive_action_expulsion_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_archive_action_expulsion_opens_wizard", login="admin", watch=True)
        self._seed_student('Archive Action Tour Expulsion')
        self.start_tour("/odoo", "ems_archive_action_expulsion_opens_wizard", login="admin", step_delay=300)
