# -*- coding: utf-8 -*-
import logging

from psycopg2.extras import Json

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _seed_notice_email_signature_default(env):
    """res.company.notice_email_signature (new in this version, Html, translate=True)
    replaces what used to be a hardcoded 'Kind regards,<br/>{company name}' baked into
    ems.mail_notice's own body_html - seed every company with the exact same text, in all
    3 shipped languages, so existing notices keep looking the same as before this became
    editable. Same logic as __init__.py's post_init_hook counterpart
    (_seed_notice_email_signature_default), duplicated here per this repo's migration
    convention (each migration script is self-contained, not cross-imported from the
    module's own __init__.py).

    Uses a direct SQL jsonb write, not record.update_field_translations(): fields.Html sets
    `translate` to the html_translate *function*, not the literal `True`, so the ORM's
    multi-lang API takes the term-by-term "translate existing content" code path (expects
    {lang: {old_term: new_term}} and requires a pre-existing value to diff against) instead
    of "set the whole value" - it silently returns False and writes nothing on a still-empty
    field like this one. Confirmed empirically (logged the return value + a read-back before
    switching to this approach)."""
    companies = env['res.company'].search([('notice_email_signature', '=', False)])
    for company in companies:
        env.cr.execute(
            "UPDATE res_company SET notice_email_signature = %s WHERE id = %s",
            (Json({
                'en_US': f"Kind regards,<br/>{company.name}",
                'ca_ES': f"Salutacions cordials,<br/>{company.name}",
                'es_ES': f"Saludos cordiales,<br/>{company.name}",
            }), company.id),
        )
    _logger.info(
        "Migration 18.0.0.23.3: seeded notice_email_signature (3 languages) for %d "
        "compan(y/ies).", len(companies))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_notice_email_signature_default(env)
