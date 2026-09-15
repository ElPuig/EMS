# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _unlock_portal_authorization_rule(cr):
    """rule_ems_authorization_portal lived in a <data noupdate="1"> block until this version,
    which stamped noupdate=true on its ir_model_data row when it was first created. This
    version rewrites its domain_force (from enrollment_id.partner_id to partner_id, now that
    an authorization can exist without an enrollment at all - issue #443) and moves it into a
    plain <data> block for good, so the rule keeps tracking the data model from now on.

    The stored flag has to be cleared here regardless: models._load_records() checks the
    *record's* own ir_model_data.noupdate before updating it, so a row still carrying true
    from its old block would go on being skipped however the file is written. Without this,
    portal families would keep seeing only the authorizations that hang off an enrollment and
    none of the ones sent to them during the course - on every existing installation, while
    working perfectly on a fresh one.

    (The file-level flag is the other half of the same trap, and the reason the block moved:
    odoo/tools/convert.py::_tag_record() skips an already-existing record on the FILE's
    noupdate flag alone, before _load_records() is ever reached. Verified empirically on this
    dev database - clearing the stored flag with the block left as noupdate="1" changed
    nothing at all.)
    """
    cr.execute("""
        UPDATE ir_model_data SET noupdate = false
         WHERE module = 'ems' AND model = 'ir.rule'
           AND name = 'rule_ems_authorization_portal'
    """)
    _logger.info(
        "Migration 18.0.0.25.0: cleared noupdate on %s portal authorization rule(s) so the "
        "new domain can load.", cr.rowcount)


def migrate(cr, version):
    _unlock_portal_authorization_rule(cr)
