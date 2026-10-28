# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, models

_logger = logging.getLogger(__name__)

ADULT_AGE = 18


class ResPartnerComingOfAge(models.Model):
    """Students coming of age: one daily check, one hook (issue #690).

    Whatever reads is_adult when it runs (who gets a notification, who acts on the portal)
    already follows the birthday on its own. This is for what has to *do* something that
    day: the cron finds the students who turned 18 and calls _ems_on_coming_of_age() on
    them, which every feature extends with super(). Loaded right after contact.py, so every
    extension sits above this base in the MRO.
    """
    _inherit = 'res.partner'

    @api.model
    def _ems_cron_coming_of_age(self):
        """Daily cron: run the coming-of-age actions for the students who turned 18 since
        the previous run.

        Odoo passes that run's time in the context ('lastcall'), so a failed or skipped run
        never leaves anyone behind, and nobody is handled twice. Without it (the first run,
        a call from code) only today's birthdays count.
        """
        today = self.env['ems.datetime_utils'].get_local_today()
        lastcall = self.env.context.get('lastcall')
        since = (self.env['ems.datetime_utils'].utc_datetime_to_local(lastcall).date()
                 if lastcall else today - relativedelta(days=1))
        students = self._ems_students_coming_of_age(since, today)
        if students:
            _logger.info("%s student(s) came of age since %s", len(students), since)
            students._ems_on_coming_of_age()

    @api.model
    def _ems_students_coming_of_age(self, since, today):
        """Active students whose 18th birthday falls in (since, today]."""
        adult_age = relativedelta(years=ADULT_AGE)
        return self.search([
            ('contact_type', '=', 'student'),
            ('birth_date', '>', since - adult_age),
            ('birth_date', '<=', today - adult_age),
        ])

    def _ems_on_coming_of_age(self):
        """Hook: these students have just turned 18. Extend it (calling super()) with
        whatever a feature must do that day; each extension filters out the students it
        does not apply to."""
