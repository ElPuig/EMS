from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPublicHolidayTour(HttpCase):
    """Absences > Configuration > Public Holidays. Logs in as admin because the screen is
    Time Off Administrator only, and admin is the one account that keeps that group (see
    res.users._ems_sync_time_off_groups()). The tour uses structural selectors only, so the
    account's language doesn't matter. The action's list is editable, so its form view is never
    reached from the UI."""

    def test_public_holiday_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_public_holiday", login="admin", watch=True)
        self.start_tour("/odoo", "ems_public_holiday", login="admin")

        holiday = self.env['resource.calendar.leaves'].search([('name', '=', 'Tour Public Holiday')])
        self.assertEqual(len(holiday), 1)
        self.assertFalse(holiday.calendar_id)
        self.assertFalse(holiday.resource_id)
