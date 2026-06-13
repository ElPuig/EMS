# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('hr_attendance.hr_attendance_check_out_cron', raise_if_not_found=False)
    if not cron:
        _logger.warning("Migration 18.0.0.15.4: cron hr_attendance_check_out_cron not found, skipping.")
        return

    company = env['res.company'].search([], limit=1)
    if not company or company.auto_checkout_mode != 'ems':
        _logger.info("Migration 18.0.0.15.4: auto_checkout_mode is not 'ems', skipping cron fix.")
        return

    utils = env['ems.datetime_utils']
    nextcall = utils.next_occurrence_utc(company.auto_checkout_time)

    cron.write({
        'active': True,
        'interval_number': 1,
        'interval_type': 'hours',
        'nextcall': nextcall,
    })
    _logger.info(
        "Migration 18.0.0.15.4: cron fixed — active=True, interval=1h, nextcall=%s.", nextcall
    )
