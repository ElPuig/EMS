import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Assigns the correct partner category (Student, Family, Provider) to all
    existing res.partner records based on their contact_type field.
    This is a one-time migration needed because category sync was added after
    existing records were created.
    NOTE: rename this folder to match the actual target version before merging.
    """
    from odoo import api, registry
    from odoo.tools import config

    dbname = cr.dbname
    with registry(dbname).cursor() as new_cr:
        env = api.Environment(new_cr, 1, {})
        try:
            cat_student = env.ref('ems.partner_category_student')
            cat_family = env.ref('ems.partner_category_family')
            cat_provider = env.ref('ems.partner_category_provider')
        except Exception:
            _logger.warning("Migration: EMS partner categories not found, skipping.")
            return

        all_managed = cat_student | cat_family | cat_provider
        category_map = {
            'student': cat_student,
            'family': cat_family,
            'provider': cat_provider,
        }

        partners = env['res.partner'].search([('contact_type', 'in', ['student', 'family', 'provider'])])
        for p in partners:
            cat = category_map.get(p.contact_type)
            if cat:
                p.category_id = (p.category_id - all_managed) | cat

        new_cr.commit()
        _logger.info(f"Migration: synced categories for {len(partners)} partners.")
