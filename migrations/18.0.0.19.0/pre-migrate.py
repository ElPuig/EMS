# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    renames = [
        ('group_admin', 'group_academic_admin'),
    ]
    for old, new in renames:
        cr.execute(
            "UPDATE ir_model_data SET name = %s WHERE module = 'ems' AND name = %s",
            (new, old),
        )
        _logger.info("Migration 18.0.0.19.0: renamed XML ID '%s' → '%s'.", old, new)
