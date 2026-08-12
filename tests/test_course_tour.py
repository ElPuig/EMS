from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestCourseTour(HttpCase):

    # res.config.settings always shows its Save/Discard toolbar and keeps the form in
    # edition mode by design — there's no "closed" state to navigate to on a settings
    # screen. Odoo's own test harness has this exact escape hatch for tours that
    # legitimately end on a form (odoo/tests/common.py's _check_form).
    allow_end_on_form = True

    def test_course_settings_tour(self):
        course = self.env['ems.course'].create({'start': 2099, 'end': 2100})
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_course_settings", login="admin", watch=True)
        self.start_tour("/odoo", "ems_course_settings", login="admin")
        # Asserted server-side as well as in the browser: a tour step can go green on a
        # selector that never wrote anything. Both selectors must have moved their flag,
        # and each mark must be carried by exactly one course.
        course.invalidate_recordset()
        self.assertTrue(course.is_current)
        self.assertTrue(course.is_enrollment_default)
        self.assertEqual(self.env.company.enrollment_course_id, course)
        self.assertEqual(self.env['ems.course'].search([('is_current', '=', True)]), course)
        self.assertEqual(
            self.env['ems.course'].search([('is_enrollment_default', '=', True)]), course)
