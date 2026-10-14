import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_study_managing_department(env)


def _backfill_study_managing_department(env):
    """Issue #622: the absences of a group's classes are organised by the department that manages
    its study (the new ems.study.managing_department_id), not by the absent teacher's. Existing
    studies start out with the department that gives more than half of their groups' classes,
    which is how the vocational families work; the rest stay blank (their absent teacher's chain
    of command, as before) and any of them can be changed on the study's form."""
    env['ems.study']._backfill_managing_department()
    studies = env['ems.study'].search([('managing_department_id', '!=', False)])
    _logger.info("Issue #622: managing department set on %s study(ies): %s", len(studies), ", ".join(
        f"{study.acronym} -> {study.managing_department_id.name}" for study in studies) or "-")
