import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    cr.execute("""
        UPDATE ems_course SET is_current = True
        WHERE start = 2025 AND "end" = 2026
    """)
    _logger.info("Migration: set is_current=True on course 2025-2026 (%d rows)", cr.rowcount)

    cr.execute("""
        UPDATE ems_course SET is_current = False
        WHERE start != 2025 OR "end" != 2026
    """)
    _logger.info("Migration: set is_current=False on other courses (%d rows)", cr.rowcount)

    categories = [
        ("Sales", [
            "group_sale_salesman", "group_sale_salesman_all_leads", "group_sale_manager",
            "group_auto_done_setting", "group_warning_sale", "group_sale_order_template",
        ]),
        ("Accounting", [
            "group_delivery_invoice_address", "group_account_readonly", "group_account_invoice",
            "group_account_basic", "group_account_user", "group_account_manager",
            "group_account_secured", "group_warning_account", "group_cash_rounding",
            "group_sale_receipts", "group_purchase_receipts", "group_validate_bank_account",
            "group_analytic_accounting",
        ]),
        ("Canned Responses", ["group_mail_canned_response_admin"]),
        ("Product Creation", ["group_product_manager"]),
    ]

    for category, group_names in categories:
        cr.execute("""
            DELETE FROM res_groups_users_rel
            WHERE gid IN (
                SELECT rg.id FROM res_groups rg
                JOIN ir_model_data imd ON imd.res_id = rg.id AND imd.model = 'res.groups'
                WHERE imd.name = ANY(%s)
            )
            AND uid != (SELECT id FROM res_users WHERE login = 'admin')
        """, (group_names,))
        _logger.info("Migration: removed '%s' permissions from %d user-group assignments", category, cr.rowcount)
