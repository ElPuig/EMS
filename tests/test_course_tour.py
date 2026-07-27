from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestCourseTour(HttpCase):

    # res.config.settings always shows its Save/Discard toolbar and keeps the form in
    # edition mode by design — there's no "closed" state to navigate to on a settings
    # screen. Odoo's own test harness has this exact escape hatch for tours that
    # legitimately end on a form (odoo/tests/common.py's _check_form).
    allow_end_on_form = True

    def test_course_settings_tour(self):
        self.env['ems.course'].create({'start': 2099, 'end': 2100})
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_course_settings", login="admin", watch=True)
        self.start_tour("/odoo", "ems_course_settings", login="admin")
