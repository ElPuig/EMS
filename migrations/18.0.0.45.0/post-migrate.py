from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_centre_lang(env)


def _seed_centre_lang(env):
    """Issue #746: Catalan as the centre language of an installation that had none, and as the
    default language of its new contacts and users. The same step post_init_hook runs on install."""
    env['res.company']._ems_seed_centre_lang()
