# -*- coding: utf-8 -*-

from datetime import datetime

from psycopg2.extras import Json

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
    # Must run before _ems_seed_enrollment_default() below: that method's own "course after the
    # operational one" logic already reads is_current to decide, and would otherwise always find
    # it empty on a fresh install.
    _ems_seed_current_course(env)
    # ems.planning.course_id (issue #503) can't have a DB-level default resolved at the time the
    # centre's own data/custom/ccff/*.csv rows are created (current_course_id isn't set until
    # the line above runs, strictly after all data has loaded) - backfill any still-empty one
    # now that it is.
    current_course = env.company.current_course_id
    if current_course:
        env['ems.planning'].search([('course_id', '=', False)]).write({'course_id': current_course.id})
    # is_enrollment_default is not a CSV column (it is live state the centre moves when it
    # opens the next campaign), so a fresh install needs it seeded once.
    env['ems.course']._ems_seed_enrollment_default()
    _backfill_missing_teacher_calendars(env)
    # Installing hr_holidays hands its Administrator group to every existing user via
    # 'base.default_user'; take it back from everyone EMS does not actually grant it to.
    env['res.users']._ems_sync_time_off_groups()
    # Odoo's own absence types are none of the centre's nine, and carry noupdate=True
    # so no data file can archive them.
    env['hr.leave.type']._ems_deactivate_native_types()
    # Same reason, same mechanism: the Catalan Odoo ships for the two approval activity types
    # is machine-generated nonsense, and it heads every request in the chatter.
    env['mail.activity.type']._ems_fix_approval_activity_names()
    _default_strike_family_notification_kicked_out(env)
    _seed_notice_email_signature_default(env)
    _apply_icu_collation_to_sort_fields(env)


def _ems_seed_current_course(env):
    """res.company.current_course_id is never auto-seeded on a fresh install (the code itself
    already documents this gap - see res.company.get_current_course_or_raise()) - nothing sets
    it, so a freshly installed instance runs with no operational course at all until an admin
    configures one by hand. Seeds a real course for the actual installation year (no Sept-Aug
    academic-year cutover logic - not worth it yet, per the developer) and sets it as current, so
    a fresh install starts in a sane state. See plans/current_course_auto_seed.md.

    Reuses an existing course for that year if one already exists (e.g. an existing
    installation's __import__-owned courses already cover it) instead of creating a
    duplicate - ems.course's own unique_course_name constraint would block that anyway."""
    year = datetime.now().year
    course = env['ems.course'].search([('start', '=', year)], limit=1) \
        or env['ems.course'].create({'start': year, 'end': year + 1})
    env['res.company'].search([]).write({'current_course_id': course.id})


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


def _seed_notice_email_signature_default(env):
    """res.company.notice_email_signature (Html, translate=True) replaces what used to be a
    hardcoded 'Kind regards,<br/>{company name}' baked into ems.mail_notice's own body_html -
    seed every company still missing it with the exact same text, in all 3 shipped languages,
    so a fresh install's notices keep looking the same as before this became editable (see
    migrations/<version>/post-migrate.py for the upgrade-path counterpart)."""
    for company in env['res.company'].search([('notice_email_signature', '=', False)]):
        # Two ORM approaches were tried and rejected before this one - both real gotchas, not
        # style choices: (1) a plain sequence of with_context(lang=X).write(...) calls
        # auto-cascades a new value to every OTHER language that still looks "not manually
        # customized," so writing en_US then ca_ES then es_ES in a loop ends up clobbering
        # earlier languages with later ones (confirmed empirically - en_US ended up with the
        # Catalan text); (2) record.update_field_translations(field, {lang: value}) - the
        # ORM's own multi-lang API - silently returns False and writes nothing here, because
        # fields.Html sets `translate` to the html_translate *function*, not the literal
        # `True`, so the ORM takes the term-by-term "translate existing content" code path
        # (expects {lang: {old_term: new_term}} and requires a pre-existing value to diff
        # against) instead of the "set the whole value" path - neither applies when seeding a
        # brand-new, still-empty field. A direct SQL write of the full jsonb value sidesteps
        # both: correct and simple for a one-time initial seed (not an ongoing translation
        # workflow, which is what those ORM APIs are actually built for).
        env.cr.execute(
            "UPDATE res_company SET notice_email_signature = %s WHERE id = %s",
            (Json({
                'en_US': f"Kind regards,<br/>{company.name}",
                'ca_ES': f"Salutacions cordials,<br/>{company.name}",
                'es_ES': f"Saludos cordiales,<br/>{company.name}",
            }), company.id),
        )


def _enable_unaccent_extension(env):
    """Once the PostgreSQL 'unaccent' extension is present, Odoo core automatically wraps
    every ilike/like search domain (list/kanban search bars, name_search, filters...) with
    the SQL unaccent() function, for every model, with no EMS code changes needed (see
    odoo/modules/db.py::has_unaccent and odoo/modules/registry.py). Fresh installs get it
    here; existing installs upgrading to this version get it via
    migrations/18.0.0.22.0/post-migrate.py."""
    env.cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


def _apply_icu_collation_to_sort_fields(env):
    """This database's default collation ('C.UTF-8', fixed at CREATE DATABASE time and never
    changeable afterwards without recreating the whole database) sorts strings by raw Unicode
    code point rather than alphabetically - an accented uppercase letter like 'Á' (U+00C1) has
    a higher code point than 'Z' (U+005A), so it sorts *after* every plain A-Z letter instead of
    next to 'A' (issue #454). This has nothing to do with the 'unaccent' extension above, which
    only affects ilike/like search, never ORDER BY.

    PostgreSQL's built-in ICU collations (bundled with this server, no extra install needed)
    fix this per-column: overriding a column's collation to 'und-x-icu' (locale-neutral Unicode
    default ordering - deliberately not a Catalan/Spanish-specific collation, since these
    columns hold personal names of many different origins) makes every ORDER BY on that column
    sort accented letters next to their base letter, with no application code changes. Verified
    empirically (2026-09-16): ALTER TABLE ... ALTER COLUMN ... TYPE varchar COLLATE "und-x-icu"
    transparently rewrites the column and rebuilds any dependent index in place - existing data,
    NOT NULL constraints and indexes all survive untouched, only the sort order changes.

    Scoped to the columns actually used to order the app's main people/catalog list views -
    not a blanket fix for every text column in the database. Fresh installs get it here;
    existing installs upgrading to this version get it via
    migrations/18.0.0.26.0/pre-migrate.py.

    Gotcha confirmed empirically 2026-09-16: PostgreSQL refuses to ALTER COLUMN TYPE on a
    column any view depends on ('cannot alter type of a column used by a view or rule').
    hr_employee.name is one such column - hr.employee.public (hr/models/hr_employee_public.py)
    is a native Odoo SQL-view model selecting it. Drop the view first; Odoo unconditionally
    recreates it (CREATE OR REPLACE VIEW in its own init(), inherited/extended by
    hr_attendance and hr_skills) as part of every module load that follows, install or
    upgrade alike, so dropping it here is always safe."""
    env.cr.execute("DROP VIEW IF EXISTS hr_employee_public")
    for table, column in _ICU_COLLATION_SORT_COLUMNS:
        env.cr.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE varchar COLLATE "und-x-icu"')


_ICU_COLLATION_SORT_COLUMNS = [
    ('ems_group', 'name'),
    ('ems_level', 'name'),
    ('ems_study', 'name'),
    ('ems_subject', 'name'),
    ('hr_employee', 'name'),
    ('res_partner', 'name'),
    ('res_partner', 'firstname'),
    ('res_partner', 'lastname'),
    ('res_partner', 'complete_name'),
]