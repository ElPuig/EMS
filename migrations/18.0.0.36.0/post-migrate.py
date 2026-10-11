import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# xmlid (module '__import__') -> (name it had, corrected name)
_SUBJECT_RENAMES = {
    'subject_175_2022_FIQ2': ("Física i Química (1r)", "Física i Química (2n)"),
    'subject_175_2022_FIQ3': ("Física i Química (2n)", "Física i Química (3r)"),
    'subject_175_2022_FIQ4': ("Física i Química (3r)", "Física i Química (4t)"),
    'subject_175_2022_ROB3': ("Robòtica (2n)", "Robòtica (3r)"),
}


def _rename_eso_subjects(env):
    """These ESO subjects were named one course too low. This version's pre-migrate freezes every
    data/custom/ record, so the corrected names in data/custom/eso/ems.subject.csv no longer
    reach an existing installation by themselves. Through the ORM, so the subject's product is
    renamed with it; a subject already renamed through the app is left alone."""
    for xmlid, (old_name, new_name) in _SUBJECT_RENAMES.items():
        subject = env.ref(f'__import__.{xmlid}', raise_if_not_found=False)
        if subject and subject.name == old_name:
            subject.name = new_name
            _logger.info("Migration 18.0.0.36.0: subject %s renamed to '%s'.", subject.code, new_name)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _rename_eso_subjects(env)
