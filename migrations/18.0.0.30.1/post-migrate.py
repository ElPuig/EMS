import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _recompute_stale_last_attendance(env):
    """Automatic check-ins taken on a roll-call used to be stored with microseconds, a fraction of
    a second later than the "now" hr.employee's stored last_attendance_id is computed against, so
    it never became that employee's last attendance (and, being a stored compute depending only on
    'attendance_ids', was never picked up later either). The kiosk then saw them as checked out and
    tried a second check-in instead of the check-out. Recomputes it for every employee whose stored
    value isn't their actual latest attendance."""
    env.cr.execute("""
        SELECT e.id
          FROM hr_employee e
          JOIN LATERAL (
                SELECT a.id FROM hr_attendance a
                 WHERE a.employee_id = e.id AND a.check_in <= now() AT TIME ZONE 'UTC'
              ORDER BY a.check_in DESC LIMIT 1
          ) latest ON true
         WHERE e.last_attendance_id IS DISTINCT FROM latest.id
    """)
    employees = env['hr.employee'].with_context(active_test=False).browse(
        [row[0] for row in env.cr.fetchall()])
    if not employees:
        return
    env.add_to_compute(employees._fields['last_attendance_id'], employees)
    employees.flush_recordset(['last_attendance_id'])
    _logger.info("Migration 18.0.0.30.1: recomputed the last attendance of %s employees.", len(employees))


def _detach_public_holidays_from_schedules(env):
    """A public holiday tied to one working schedule only applied to the employees on exactly that
    schedule - nobody, in practice, since every teacher has a personal one (the first Diada was
    tied to the default schedule framework, with no employees). Detaching it through the ORM also
    recomputes the affected overtime and deletes the red "absence" technical attendances left on
    those days (models/employees/public_holiday.py)."""
    holidays = env['resource.calendar.leaves'].search([
        ('resource_id', '=', False), ('calendar_id', '!=', False),
    ])
    if not holidays:
        return
    holidays.write({'calendar_id': False})
    _logger.info("Migration 18.0.0.30.1: detached %s public holidays from their schedule.", len(holidays))


def _drop_stale_data_request_menu_translations(cr):
    """The "Student Data" menu (menu_contact_data_requests) was renamed "Data request". The
    upgrade writes the new English name, but loads the .po files without overwriting existing
    values, so the Catalan and Spanish names kept the old label. Dropping those two keys here
    (post-migrate runs before the translations load) lets the .po fill them in again."""
    cr.execute("""
        UPDATE ir_ui_menu
           SET name = name - 'ca_ES' - 'es_ES'
         WHERE id = (SELECT res_id FROM ir_model_data
                      WHERE module = 'ems' AND name = 'menu_contact_data_requests')
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.30.1: reset the translations of the Data request menu.")


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _recompute_stale_last_attendance(env)
    _detach_public_holidays_from_schedules(env)
    _drop_stale_data_request_menu_translations(cr)
