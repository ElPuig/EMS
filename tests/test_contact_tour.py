from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestContactTour(HttpCase):

    def test_contact_tabs_and_relation_wizard_tour(self):
        # The tour asserts on literal English tab names (e.g. "Student data", "Studies") for
        # the real 'admin' login, which only works if admin's own language is en_US - not
        # guaranteed on every dev box. See CLAUDE.md's "Tour tests and language" convention.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
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
