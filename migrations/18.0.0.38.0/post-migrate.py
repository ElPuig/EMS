from odoo import SUPERUSER_ID, api
from odoo.addons.ems import _translate_area_names


def migrate(cr, version):
    """Issue #637: the areas head the guard duty board's columns and filter, and were never
    translated (see _translate_area_names)."""
    _translate_area_names(api.Environment(cr, SUPERUSER_ID, {}))
