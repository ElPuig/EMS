# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    cr.execute("ALTER TABLE IF EXISTS ems_communication RENAME TO ems_notice;")
    cr.execute("ALTER TABLE IF EXISTS ems_communication_line RENAME TO ems_notice_line;")
    cr.execute("ALTER SEQUENCE IF EXISTS ems_communication_id_seq RENAME TO ems_notice_id_seq;")
    cr.execute("ALTER SEQUENCE IF EXISTS ems_communication_line_id_seq RENAME TO ems_notice_line_id_seq;")

    # Rename FK column so Odoo does not recreate it as nullable
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ems_notice_line' AND column_name = 'communication_id'
            ) THEN
                ALTER TABLE ems_notice_line RENAME COLUMN communication_id TO notice_id;
            END IF;
        END$$;
    """)

    cr.execute("UPDATE mail_message SET model = 'ems.notice' WHERE model = 'ems.communication';")
    cr.execute("UPDATE mail_message SET model = 'ems.notice.line' WHERE model = 'ems.communication.line';")

    renames = [
        ('view_communication_list',                 'view_notice_list'),
        ('view_communication_form',                 'view_notice_form'),
        ('view_communication_line_exception_popup', 'view_notice_line_exception_popup'),
        ('access_ems_communication_admin',          'access_ems_notice_admin'),
        ('access_ems_communication_line_admin',     'access_ems_notice_line_admin'),
        ('rule_communication_admin',                'rule_notice_admin'),
        ('rule_communication_own',                  'rule_notice_own'),
        ('mail_communication',                      'mail_notice'),
    ]
    for old, new in renames:
        cr.execute(
            "UPDATE ir_model_data SET name = %s WHERE module = 'ems' AND name = %s",
            (new, old),
        )
        _logger.info("Migration 18.0.0.18.4: renamed XML ID '%s' → '%s'.", old, new)
