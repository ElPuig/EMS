from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _unlink_replaced_technical_attendances(env)


def _unlink_replaced_technical_attendances(env):
    """Issue #741: the technical attendances (the red "no check-in that day" ones) left on a day
    that already has a real attendance, mainly by correcting a detected absence's check-in. The
    same cleanup the attendances' create() now does, run over every real attendance of those
    employees from the oldest technical one on; through the ORM, so Odoo recomputes each day's
    overtime. A clean install has no attendances, so it needs no post_init_hook counterpart."""
    attendances = env['hr.attendance']
    technical = attendances.search([('in_mode', '=', 'technical')])
    if not technical:
        return
    attendances.search([
        ('in_mode', '!=', 'technical'), ('employee_id', 'in', technical.employee_id.ids),
        ('check_in', '>=', min(technical.mapped('check_in'))),
    ])._ems_unlink_replaced_technical_attendances()
