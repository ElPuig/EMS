# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 'resource.calendar' auto-fills 'attendance_ids' from the company's own calendar whenever a new
    # calendar is created without attendance lines in the same create() call (resource_calendar.py's
    # '_compute_attendance_ids', @api.depends('company_id')). Our schedule frameworks are seeded via
    # two separate CSV files (parent record, then child attendance lines) — the parent's create() has
    # no inline attendance_ids, so this auto-fill silently injects a copy of the company calendar's
    # lines before our own CSV-authored lines get added. Every legitimate line we create has an
    # ir_model_data entry (real xmlid); the auto-filled ones don't — so purge any attendance line on a
    # framework calendar that isn't backed by an xmlid.
    cr.execute("""
        DELETE FROM resource_calendar_attendance rca
        USING resource_calendar rc
        WHERE rca.calendar_id = rc.id
          AND rc.is_framework = true
          AND NOT EXISTS (
              SELECT 1 FROM ir_model_data d
              WHERE d.model = 'resource.calendar.attendance' AND d.res_id = rca.id
          )
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.20.0: purged %d spurious auto-filled attendance line(s) from framework calendars.", cr.rowcount)

    # Retire the legacy 'Standard 40 hours/week'-style company calendar: every employee still on it
    # gets their OWN personal calendar seeded from the centre's default framework (never point an
    # employee straight at the framework record itself — 'apply_schedule_changes' assumes a 1:1
    # employee<->calendar relationship, and saving from the 'Schedule' tab would otherwise overwrite
    # the shared template for everyone). The company's own base calendar is then repointed to the
    # framework, and the old calendar is deleted once nothing references it anymore.
    for company in env['res.company'].search([]):
        old_calendar = company.resource_calendar_id
        framework = company.default_schedule_framework_id
        if not old_calendar or not framework or old_calendar == framework or old_calendar.is_framework:
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
                "Migration 18.0.0.20.0: moved %d employee(s) off '%s' onto personal framework-seeded calendars.",
                len(employees), old_calendar.name,
            )

        company.resource_calendar_id = framework

        still_used = env['hr.employee'].with_context(active_test=False).search_count([('resource_calendar_id', '=', old_calendar.id)])
        if not still_used:
            try:
                with cr.savepoint():
                    old_calendar.unlink()
                _logger.info("Migration 18.0.0.20.0: deleted retired calendar '%s' (id=%d).", old_calendar.name, old_calendar.id)
            except Exception:
                _logger.warning("Migration 18.0.0.20.0: could not delete retired calendar id=%d, leaving it archived-in-place instead.", old_calendar.id)
                old_calendar.active = False
