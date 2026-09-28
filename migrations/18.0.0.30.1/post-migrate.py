from odoo import SUPERUSER_ID, api


def migrate(cr, _version):
    """Issue #518: one timezone for the whole centre, the company's. Every existing partner (users,
    families, the public user the attendance kiosk runs as), employee and working schedule carries
    whatever timezone its browser gave it (America/Lima, Atlantic/Canary... or none, so UTC):
    align them all with the company's. See docs/en/developers/shared/timezones.md."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company']._ems_align_timezones()
