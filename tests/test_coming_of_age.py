from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests.common import TransactionCase

from .common import next_student_id


class TestComingOfAge(TransactionCase):
    """Issue #690: the daily check that hands the students who just turned 18 to
    res.partner._ems_on_coming_of_age(), the hook every feature extends."""

    def _today(self):
        return self.env['ems.datetime_utils'].get_local_today()

    def _student_aged(self, name, **age):
        return self.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'birth_date': self._today() - relativedelta(years=18) + relativedelta(**age),
        })

    def _came_of_age(self, lastcall=None):
        """The students the cron hands to the hook (patched, so no feature's action runs:
        the development data the test shards clone has its own real birthdays)."""
        partners = self.env['res.partner']
        if lastcall:
            partners = partners.with_context(lastcall=lastcall)
        with patch.object(type(partners), '_ems_on_coming_of_age', autospec=True) as hook:
            partners._ems_cron_coming_of_age()
        return partners.union(*(call.args[0] for call in hook.call_args_list))

    def test_students_turning_18_today(self):
        birthday = self._student_aged('Coming Of Age Today')
        minor = self._student_aged('Coming Of Age Tomorrow', days=1)
        archived = self._student_aged('Coming Of Age Archived')
        archived.write({'active': False})
        family = self._student_aged('Coming Of Age Family')
        family.contact_type = 'family'
        came_of_age = self._came_of_age()
        self.assertIn(birthday, came_of_age)
        self.assertNotIn(minor, came_of_age)
        self.assertNotIn(archived, came_of_age)
        self.assertNotIn(family, came_of_age)
        self.assertTrue(birthday.is_adult)

    def test_catches_up_on_birthdays_since_the_last_run(self):
        # A run that failed or was skipped must not leave anyone behind: the window starts
        # at the previous successful run, which Odoo passes in the context.
        three_days_ago = self._student_aged('Coming Of Age Three Days', days=-3)
        long_ago = self._student_aged('Coming Of Age Long Ago', days=-10)
        came_of_age = self._came_of_age(lastcall=fields.Datetime.now() - relativedelta(days=4))
        self.assertIn(three_days_ago, came_of_age)
        self.assertNotIn(long_ago, came_of_age)

    def test_never_handles_a_student_twice(self):
        three_days_ago = self._student_aged('Coming Of Age Three Days', days=-3)
        came_of_age = self._came_of_age(lastcall=fields.Datetime.now() - relativedelta(days=1))
        self.assertNotIn(three_days_ago, came_of_age)
