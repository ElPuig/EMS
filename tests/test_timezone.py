# -*- coding: utf-8 -*-

from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCompanyTimezone(TransactionCase):
    """models/settings/timezone.py: every partner, employee and working schedule keeps the company's
    timezone, whatever the browser that created or edited it said (issue #518, see
    docs/en/developers/shared/timezones.md)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_partner = cls.env.company.partner_id
        cls.company_partner.tz = 'Europe/Madrid'

    def test_a_new_partner_gets_the_company_timezone(self):
        # What Odoo does on a first login: the browser's timezone, from its 'tz' cookie.
        partner = self.env['res.partner'].create({'name': 'TZ Test Family', 'tz': 'America/Lima'})
        self.assertEqual(partner.tz, 'Europe/Madrid')
        partner.tz = 'Atlantic/Canary'
        self.assertEqual(partner.tz, 'Europe/Madrid')

    def test_employees_and_calendars_get_the_company_timezone(self):
        employee = self.env['hr.employee'].create({'name': 'TZ Test Teacher', 'tz': 'Europe/Berlin'})
        self.assertEqual(employee.tz, 'Europe/Madrid')
        calendar = self.env['resource.calendar'].create({'name': 'TZ Test Calendar', 'tz': 'UTC'})
        self.assertEqual(calendar.tz, 'Europe/Madrid')

    def test_changing_the_companys_timezone_moves_everyone(self):
        partner = self.env['res.partner'].create({'name': 'TZ Test Family'})
        employee = self.env['hr.employee'].create({'name': 'TZ Test Teacher'})

        self.company_partner.tz = 'Atlantic/Canary'

        self.assertEqual(self.company_partner.tz, 'Atlantic/Canary')
        self.assertEqual(partner.tz, 'Atlantic/Canary')
        self.assertEqual(employee.tz, 'Atlantic/Canary')
        self.assertEqual(self.env.ref('base.public_user').partner_id.tz, 'Atlantic/Canary')

    def test_align_fixes_existing_records(self):
        """What the 18.0.0.30.1 migration and the post_init_hook run."""
        partner = self.env['res.partner'].create({'name': 'TZ Test Family'})
        self.env.cr.execute("UPDATE res_partner SET tz = 'America/Lima' WHERE id = %s", [partner.id])
        self.env.cr.execute("UPDATE res_partner SET tz = NULL WHERE id = %s",
                            [self.env.ref('base.public_user').partner_id.id])
        self.env.invalidate_all()

        self.env['res.company']._ems_align_timezones()

        self.assertEqual(partner.tz, 'Europe/Madrid')
        self.assertEqual(self.env.ref('base.public_user').partner_id.tz, 'Europe/Madrid')

    def test_attendance_kiosk_error_shows_spanish_time(self):
        """The kiosk runs as the public user, whose empty timezone made Odoo's own attendance errors
        ("hasn't checked out since...", "was already checked in on...") show times in UTC (11:08 for
        a 13:08 check-in). Both format the time with the acting user's timezone; this checks it
        through the overlap one, built only from closed attendances, so that neither the real clock
        nor the automatic check-out of an open attendance (create()) can change the outcome. A
        winter and a summer date, so a fixed offset can't pass it."""
        self.env['res.company']._ems_align_timezones()
        employee = self.env['hr.employee'].create({'name': 'TZ Test Teacher'})
        kiosk = self.env['hr.attendance'].with_user(self.env.ref('base.public_user')).sudo()
        for utc_day, expected in ((datetime(2026, 1, 12), '12:08'), (datetime(2026, 9, 28), '13:08')):
            with self.subTest(expected=expected):
                self.env['hr.attendance'].create({
                    'employee_id': employee.id,
                    'check_in': utc_day.replace(hour=10), 'check_out': utc_day.replace(hour=12),
                })
                with self.assertRaises(ValidationError) as error:
                    kiosk.create({
                        'employee_id': employee.id,
                        'check_in': utc_day.replace(hour=11, minute=8), 'check_out': utc_day.replace(hour=13),
                    })
                self.assertIn(expected, str(error.exception))
