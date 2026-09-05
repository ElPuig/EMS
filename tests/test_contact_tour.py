from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestContactTour(HttpCase):

    def _force_admin_language_to_english(self):
        # The tour asserts on literal English tab names (e.g. "Student data", "Studies") for
        # the real 'admin' login, which only works if admin's own language is en_US - not
        # guaranteed on every dev box. Scoped to this test's own transaction (rolled back
        # afterward) and additionally restored via addCleanup for clarity, since this mutates
        # a real, pre-existing user. See feedback_tour_tests_force_english_language in memory.
        admin_user = self.env.ref('base.user_admin')
        original_lang = admin_user.lang
        admin_user.lang = 'en_US'
        self.addCleanup(lambda: admin_user.write({'lang': original_lang}))

    def test_contact_tabs_and_relation_wizard_tour(self):
        self._force_admin_language_to_english()
        # "0000 " prefix: res.partner's _order is "name", so this seeded student sorts
        # first on the list's very first page among the ~1000+ real students already in
        # this DB (see test_withdrawal_tour.py for the same pattern).
        self.env['res.partner'].create({
            'name': '0000 Contact Tour Student', 'contact_type': 'student',
            'student_email': 'contact.tour.student@example.com',
        })
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_contact_tabs_and_relation_wizard", login="admin", watch=True)
        self.start_tour("/odoo", "ems_contact_tabs_and_relation_wizard", login="admin", step_delay=300)
