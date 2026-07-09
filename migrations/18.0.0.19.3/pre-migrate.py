# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    cr.execute(
        "UPDATE ir_model_data SET name = %s WHERE module = 'ems' AND name = %s",
        ('role_dchieff', 'role_dchieff_cs'),
    )
    _logger.info("Migration 18.0.0.19.3: renamed XML ID 'role_dchieff_cs' → 'role_dchieff'.")
