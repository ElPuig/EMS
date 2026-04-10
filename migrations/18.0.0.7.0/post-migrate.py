import logging
from odoo import api

_logger = logging.getLogger(__name__)

def _sync_partner_categories(env):
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

    _logger.info(f"Migration: synced categories for {len(partners)} partners.")

def _move_vat_to_document_id(env):
    partners = env['res.partner'].search([
        ('contact_type', 'in', ['student', 'family']),
        ('vat', '!=', False),
        ('vat', '!=', ''),
    ])
    for p in partners:
        if not p.document_id:
            p.document_id = p.vat
            p.vat = False

    _logger.info(f"Migration: moved vat to document_id for {len(partners)} partners.")

def migrate(cr, _version):
    env = api.Environment(cr, 1, {})
    _sync_partner_categories(env)
    _move_vat_to_document_id(env)
