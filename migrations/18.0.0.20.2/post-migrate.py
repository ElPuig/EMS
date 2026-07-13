# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 18.0.0.20.0's post-migrate tried to retire the legacy company calendar, but its companion
    # pre-migrate backfilled 'default_schedule_framework_id' from the 'ems.schedule_framework_default'
    # xmlid *before* that xmlid's own record was loaded (it was introduced in that same version, in
    # 'data/main/ems.schedule_framework_default.xml') — pre-migrate runs before data files load, so the
    # lookup found nothing and left the field NULL/wrong on any company reaching that version for the
    # first time. With the field unset, 18.0.0.20.0's post-migrate guard ('if not framework: continue')
    # silently skipped the whole retirement step. By now the xmlid is guaranteed to exist (data files
    # have already loaded), so re-resolve it directly here and redo the retirement defensively.
    framework = env.ref('ems.schedule_framework_default', raise_if_not_found=False)
    if not framework:
        _logger.warning("Migration 18.0.0.20.2: 'ems.schedule_framework_default' not found, nothing to fix.")
        return

    companies = env['res.company'].search([('default_schedule_framework_id', '!=', framework.id)])
    if companies:
        companies.write({'default_schedule_framework_id': framework.id})
        _logger.info(
            "Migration 18.0.0.20.2: corrected default_schedule_framework_id on %d company(ies).",
            len(companies),
        )

    for company in env['res.company'].search([]):
        old_calendar = company.resource_calendar_id
        if not old_calendar or old_calendar == framework or old_calendar.is_framework:
            continue

        employees = env['hr.employee'].with_context(active_test=False).search([
            ('resource_calendar_id', '=', old_calendar.id),
        ])
        course = company.current_course_id
        for employee in employees:
            schedule = env['resource.calendar'].create({
                'name': "%s (%s)" % (employee.name, course.name) if course else employee.name,
                'company_id': company.id,
            })
            schedule.seed_from_framework(framework)
            employee.resource_calendar_id = schedule
        if employees:
            _logger.info(
                "Migration 18.0.0.20.2: moved %d employee(s) off '%s' onto personal framework-seeded calendars.",
                len(employees), old_calendar.name,
            )

        company.resource_calendar_id = framework

        still_used = env['hr.employee'].with_context(active_test=False).search_count([('resource_calendar_id', '=', old_calendar.id)])
        if not still_used:
            try:
                with cr.savepoint():
                    old_calendar.unlink()
                _logger.info("Migration 18.0.0.20.2: deleted retired calendar '%s' (id=%d).", old_calendar.name, old_calendar.id)
            except Exception:
                _logger.warning("Migration 18.0.0.20.2: could not delete retired calendar id=%d, leaving it archived-in-place instead.", old_calendar.id)
                old_calendar.active = False
