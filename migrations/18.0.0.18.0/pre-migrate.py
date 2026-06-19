# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    renames = [
        ('view_level_form',   'level_view_form'),
        ('view_level_list',   'level_view_list'),
        ('action_level_tree', 'level_action'),
        ('menu_levels',       'level_menu'),
    ]
    for old, new in renames:
        cr.execute(
            "UPDATE ir_model_data SET name = %s WHERE module = 'ems' AND name = %s",
            (new, old),
        )
        _logger.info("Migration 18.0.0.18.0: renamed XML ID '%s' → '%s'.", old, new)
