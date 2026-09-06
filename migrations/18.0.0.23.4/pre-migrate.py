# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    # 'ems.subject.code' is no longer globally unique (models/curriculum/subject.py's
    # '_sql_constraints' dropped 'unique_code') - the same official code can now be reused by two
    # subjects that belong to different, disjoint studies (e.g. MP 3003 means different things in
    # a CFGB and a PFI), enforced instead by the new '_check_code_unique_per_study' Python
    # constraint. Odoo only reconciles '_sql_constraints' against the DB at the very end of the
    # whole module load, AFTER data files reload - so the stale DB-level constraint is still
    # enforced while 'data/cat/ems.subject.csv' tries to insert the second same-code subject,
    # confirmed empirically (2026-09-06: a plain './upgrade.sh' failed with "duplicate key value
    # violates unique constraint ems_subject_unique_code" before this migration existed). Dropping
    # it here, in pre-migrate, runs before that data reload.
    cr.execute("ALTER TABLE ems_subject DROP CONSTRAINT IF EXISTS ems_subject_unique_code")
    _logger.info("Migration 18.0.0.23.4: dropped the stale 'ems_subject_unique_code' SQL constraint.")

    # The original MP 3003/3004 (the CFGB "Serveis Administratius" ones) already exist in
    # production under their old xmlids 'ems.subject_3003'/'ems.subject_3004' - unlike the brand
    # new PFI counterparts added earlier in this same branch (which needed no migration at all,
    # since they never existed anywhere before this branch), these two DO need a rename migration
    # per the usual rule (data/cat/ems.subject.csv now ships them as 'ems.subject_3003_sa'/
    # 'ems.subject_3004_sa', to read consistently with the new 'ems.subject_3003_pfi'/
    # 'ems.subject_3004_pfi' rows added for the PFI cycle). 'noupdate' doesn't need clearing here -
    # data/cat/ems.subject.csv is plain CSV, never noupdate=1 XML, so the stored flag was already
    # False (see CLAUDE.md's migrations gotcha about noupdate="1" XML converted to CSV, which
    # doesn't apply to a record that started life as CSV).
    renames = [
        ('subject_3003', 'subject_3003_sa'),
        ('subject_3004', 'subject_3004_sa'),
    ]
    for old, new in renames:
        cr.execute(
            "UPDATE ir_model_data SET name = %s WHERE module = 'ems' AND name = %s",
            (new, old),
        )
        _logger.info("Migration 18.0.0.23.4: renamed XML ID '%s' → '%s'.", old, new)
