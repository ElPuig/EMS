import base64
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.ems.models.employees.employee import write_photo

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _repair_text_plain_placeholders(cr)


def _repair_text_plain_placeholders(cr):
    """Issue #714: the initials placeholder of a teacher whose EMS account a Head of Studies
    created was stored as text/plain, so it showed as "Binary file". Generate it again and write
    it as the superuser on every employee and contact whose photo is an SVG stored that way (or
    whose file is missing). The stored bytes are never trusted: an SVG that wasn't Odoo's own must
    not end up served as an image. post-migrate: it goes through the ORM. A clean install has no
    such photos, so it needs no post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT res_model, array_agg(res_id)
          FROM ir_attachment
         WHERE res_model IN ('hr.employee', 'res.partner')
           AND res_field = 'image_1920'
           AND mimetype = 'text/plain'
         GROUP BY res_model
    """)
    repaired = 0
    for model, ids in cr.fetchall():
        for record in env[model].with_context(active_test=False).browse(ids).exists():
            # A missing file (empty read) is just as broken, and a placeholder is better.
            raw = base64.b64decode(record.image_1920 or b'')
            if not raw or raw.lstrip().startswith(b'<'):
                write_photo(record, record._avatar_generate_svg())
                repaired += 1
    _logger.info("Issue #714: %s initials placeholders stored as text/plain rewritten.", repaired)
