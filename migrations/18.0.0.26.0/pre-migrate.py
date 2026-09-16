# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

_ICU_COLLATION_SORT_COLUMNS = [
    ('ems_group', 'name'),
    ('ems_level', 'name'),
    ('ems_study', 'name'),
    ('ems_subject', 'name'),
    ('hr_employee', 'name'),
    ('res_partner', 'name'),
    ('res_partner', 'firstname'),
    ('res_partner', 'lastname'),
    ('res_partner', 'complete_name'),
]


def migrate(cr, _version):
    # Same fix, same rationale as __init__.py's _apply_icu_collation_to_sort_fields() (issue
    # #454): this database's default collation ('C.UTF-8') sorts by raw Unicode code point, so
    # accented letters land after 'Z' instead of next to their base letter. Pure raw SQL, no ORM
    # access needed, so this is safe to run in pre-migrate (see CLAUDE.md's pre- vs post-migrate
    # rule of thumb).
    #
    # hr_employee.name can't have its type/collation altered while hr.employee.public's native
    # SQL view still depends on it ('cannot alter type of a column used by a view or rule',
    # confirmed empirically) - drop it first; Odoo's own init() unconditionally recreates it
    # later in this same module load, install or upgrade alike.
    cr.execute("DROP VIEW IF EXISTS hr_employee_public")
    for table, column in _ICU_COLLATION_SORT_COLUMNS:
        cr.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE varchar COLLATE "und-x-icu"')
        _logger.info("Migration 18.0.0.26.0: applied 'und-x-icu' collation to %s.%s for accent-correct sorting.", table, column)
