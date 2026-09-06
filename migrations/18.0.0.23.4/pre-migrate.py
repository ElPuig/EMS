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
