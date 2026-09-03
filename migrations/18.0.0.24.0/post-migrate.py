# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _sync_time_off_groups(env):
    """Take back the Time Off groups Odoo hands out when hr_holidays is installed.

    hr_holidays grants its Administrator group to 'base.default_user', the template every new
    user is copied from, and Odoo propagates that to the existing users at install time. On this
    centre's database that handed every internal user 'group_hr_holidays_manager' plus, by
    implication, 'group_hr_holidays_user' and 'hr.group_hr_user' - so every teacher could read
    every colleague's absence reason and supporting document, and every employee record besides.

    This is also what grants the approver group to whoever is actually named as an employee's
    'leave_manager_id', which no group chain can express, and what removes it from the members of
    the secretariat, who used to inherit it from 'ems.group_secretary' (that implication is
    dropped declaratively in security/groups.xml, but Odoo's implied-group writes are additive
    and never revoke what a user already materialised).

    The same call runs from post_init_hook for installations created from now on.
    """
    revoked = env['res.users']._ems_sync_time_off_groups()
    for xmlid, logins in revoked.items():
        _logger.info(
            "Migration 18.0.0.24.0: revoked %s from %s user(s): %s",
            xmlid, len(logins), ', '.join(sorted(logins)))
    if not revoked:
        _logger.info("Migration 18.0.0.24.0: no Time Off group had to be revoked.")


def _deactivate_native_leave_types(env):
    """Archive the absence types Odoo ships with, leaving only the centre's own nine.

    'Paid Time Off', 'Sick Time Off', 'Unpaid', 'Compensatory Days' and (from
    hr_holidays_attendance) 'Extra Hours' are none of the nine options the request form offers,
    and an employee picking one would land outside the centre's own rules entirely.

    This cannot be done from a data file: all five carry ir_model_data.noupdate = True, and it is
    that stored flag - not the loading file's own context - that decides whether an existing
    record gets written. Same call as post_init_hook's.
    """
    archived = env['hr.leave.type']._ems_deactivate_native_types()
    _logger.info(
        "Migration 18.0.0.24.0: archived %s of Odoo's own absence types%s",
        len(archived), (": " + ", ".join(archived.mapped('name'))) if archived else "")


def _recompute_leave_managers(env):
    """Make sure every employee's absence approver is the Area Manager of their top-level
    department, and not Odoo's own guess.

    'leave_manager_id' is a stored compute, and hr_holidays fills it when it creates the column -
    during this very upgrade. EMS overrides that computation (see
    ems_employee_base._compute_leave_manager: Odoo derives it from 'parent_id', which here is the
    Seminar Chief or Department Chief, the wrong person for an absence). Rather than depend on
    the two happening in the right order, recompute it explicitly afterwards.

    Archived employees included, and not for tidiness: an archived record left pointing at its
    Department Chief keeps handing that chief the approver group back, because hr_holidays
    grants it from any write of 'leave_manager_id' (hr_employee_base.write) while
    '_ems_sync_time_off_groups' only ever counts *active* employees when deciding who is
    entitled to keep it. The two disagreed on every upgrade.
    """
    employees = env['hr.employee'].with_context(active_test=False).search([])
    env.add_to_compute(employees._fields['leave_manager_id'], employees)
    employees.flush_recordset()
    without = employees.filtered(lambda employee: employee.department_id and not employee.leave_manager_id)
    _logger.info(
        "Migration 18.0.0.24.0: recomputed the absence approver of %s employee(s).", len(employees))
    if without:
        # Not an error: an Area Manager with no res.users cannot be an approver, and Odoo falls
        # back to letting an officer approve. Worth naming, because it is invisible otherwise.
        _logger.warning(
            "Migration 18.0.0.24.0: %s employee(s) have no absence approver, because their "
            "area's manager has no user account: %s",
            len(without), ', '.join(sorted(without.mapped('name'))))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Order matters: '_sync_time_off_groups' grants the approver group from
    # 'employee.leave_manager_id', which until '_recompute_leave_managers' has run still holds
    # Odoo's own guess (derived from 'parent_id' - here the Department or Seminar Chief, the
    # wrong person entirely). Running the sync first therefore handed the approver group to
    # every Department Chief, and then quietly left it on them once the field was recomputed to
    # the real Area Manager - which is how four of them were still holding it on the development
    # database. The same call in post_init_hook has no such ordering problem, since a fresh
    # install computes 'leave_manager_id' with EMS's own method from the start.
    _recompute_leave_managers(env)
    _sync_time_off_groups(env)
    _deactivate_native_leave_types(env)
