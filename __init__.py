# -*- coding: utf-8 -*-

from . import controllers
from . import models


def post_init_hook(env):
    """'resource.calendar' auto-fills 'attendance_ids' from the company's own calendar whenever a new
    calendar is created without attendance lines in the same create() call (resource_calendar.py's
    '_compute_attendance_ids', @api.depends('company_id')) — this silently injects extra lines into
    any schedule framework whose own attendance lines are created as separate child records/rows
    (CSV parent+child files, e.g. data/custom/resource.calendar[.attendance].csv). Every legitimate
    framework attendance line ships with a real xmlid; the auto-filled ones never get one, so purge
    any attendance line on a framework calendar that isn't backed by one."""
    env.cr.execute("""
        DELETE FROM resource_calendar_attendance rca
        USING resource_calendar rc
        WHERE rca.calendar_id = rc.id
          AND rc.is_framework = true
          AND NOT EXISTS (
              SELECT 1 FROM ir_model_data d
              WHERE d.model = 'resource.calendar.attendance' AND d.res_id = rca.id
          )
    """)
    _backfill_default_schedule_framework(env)
    _enable_unaccent_extension(env)
    # is_enrollment_default is not a CSV column (it is live state the centre moves when it
    # opens the next campaign), so a fresh install needs it seeded once.
    env['ems.course']._ems_seed_enrollment_default()
    _backfill_missing_teacher_calendars(env)
    _default_strike_family_notification_kicked_out(env)


def _backfill_default_schedule_framework(env):
    """'res.company.default_schedule_framework_id' is required, and its default resolves
    'ems.schedule_framework_default' via env.ref(). On a fresh install, Odoo's schema init
    (which evaluates that default and enforces NOT NULL) runs before this module's own data
    files are loaded, so the xmlid doesn't exist yet, the default resolves to nothing, and the
    NOT NULL constraint fails to apply (logged as an odoo.schema ERROR, but non-fatal — see
    migrations/18.0.0.20.0 and 18.0.0.21.0's post-migrate.py for the same fix on the upgrade
    path). post_init_hook runs after data files are loaded, so the xmlid is guaranteed to exist
    here — backfill any company still missing it."""
    framework = env.ref('ems.schedule_framework_default', raise_if_not_found=False)
    if not framework:
        return
    env['res.company'].search([('default_schedule_framework_id', '=', False)]).write({
        'default_schedule_framework_id': framework.id,
    })


def _backfill_missing_teacher_calendars(env):
    """'hr.employee.create()`'s auto-calendar override (models/employees/employee.py) only exists
    since commit bc29e04b (18.0.0.20.0, 2026-07-12) - a teacher already in the database before
    then (or one whose employee_type only became 'teacher' later, which write() has no equivalent
    logic for) can still be missing a personal resource.calendar. See
    plans/calendar_driven_attendance_templates.md's "Migration requirement" section for the real
    import bug this was found from, and migrations/18.0.0.22.0/post-migrate.py's own counterpart
    for the same backfill on the upgrade path (this one only ever matters for a fresh install
    whose own data files created a teacher outside the normal create() path, e.g. a hand-rolled
    CSV import - not the common case, but cheap to cover here too for the same "every one-time
    setup action needs both paths" reason as every other backfill in this file)."""
    env['hr.employee'].with_context(active_test=False).search([
        ('employee_type', '=', 'teacher'), ('resource_calendar_id', '=', False),
    ])._ems_create_personal_calendar()


def _default_strike_family_notification_kicked_out(env):
    """strike_family_notification_mode defaults to 'all' at the field level, so an
    installation upgrading into this version keeps today's always-notify-the-family
    behaviour unchanged (no migration script needed - the plain field default already
    covers the upgrade path via the schema backfill). A brand-new installation has no prior
    behaviour to preserve, so it starts on the stricter 'kicked_out' option instead."""
    env['res.company'].search([]).write({'strike_family_notification_mode': 'kicked_out'})


def _enable_unaccent_extension(env):
    """Once the PostgreSQL 'unaccent' extension is present, Odoo core automatically wraps
    every ilike/like search domain (list/kanban search bars, name_search, filters...) with
    the SQL unaccent() function, for every model, with no EMS code changes needed (see
    odoo/modules/db.py::has_unaccent and odoo/modules/registry.py). Fresh installs get it
    here; existing installs upgrading to this version get it via
    migrations/18.0.0.22.0/post-migrate.py."""
    env.cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")