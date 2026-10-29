from odoo import SUPERUSER_ID, api

from odoo.addons.ems import _seed_declaration_codes


def migrate(cr, version):
    """Issue #723: seed the official schedule declaration's codes of the existing levels and
    non-teaching types (post_init_hook does it on a clean install). post-migrate: the columns are
    new in this version and it goes through the ORM."""
    _seed_declaration_codes(api.Environment(cr, SUPERUSER_ID, {}))
