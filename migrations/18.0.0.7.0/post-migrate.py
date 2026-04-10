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

def _sync_partner_fields(env):
    partners = env['res.partner'].search([
        ('contact_type', 'in', ['student', 'family']),
    ])
    for p in partners:
        if p.vat and not p.document_id:
            p.document_id = p.vat
            p.vat = False
        p.lang = 'ca_ES'

    _logger.info(f"Migration: synced fields for {len(partners)} partners.")

def _create_family_relations(env):
    try:
        relation_type = env.ref('ems.relation_type_tutor')
    except Exception:
        _logger.warning("Migration: relation type 'Tutor' not found, skipping.")
        return

    family_contacts = env['res.partner'].search([
        ('contact_type', '=', 'family'),
        ('parent_id', '!=', False),
    ])

    count = 0
    for contact in family_contacts:
        existing = env['res.partner.relation'].search([
            ('left_partner_id', '=', contact.id),
            ('right_partner_id', '=', contact.parent_id.id),
        ], limit=1)
        if not existing:
            env['res.partner.relation'].create({
                'left_partner_id': contact.id,
                'type_id': relation_type.id,
                'right_partner_id': contact.parent_id.id,
            })
            count += 1
        contact.parent_id = False

    _logger.info(f"Migration: created {count} family relations out of {len(family_contacts)} candidates.")

def migrate(cr, _version):
    env = api.Environment(cr, 1, {})
    _sync_partner_categories(env)
    _sync_partner_fields(env)
    _create_family_relations(env)
