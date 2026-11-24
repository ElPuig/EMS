# -*- coding: utf-8 -*-
import json
import logging

_logger = logging.getLogger(__name__)

# Issue #858: the FCT certificate's details get a hint (what to write and how), its school year is
# called "Academic course" (Curs acadèmic), and its end date cannot be earlier than its start. The type is seeded with
# noupdate, so an existing installation gets them here, only where the centre has not changed them
# (a clean install from the XML and the .po files, with these same words).
FCT_HINTS = {
    'school_year': {
        'en_US': "As YYYY-YY, e.g. 2024-25.",
        'ca_ES': "Format AAAA-AA, per exemple 2024-25.",
        'es_ES': "Formato AAAA-AA, por ejemplo 2024-25.",
    },
    'company': {
        'en_US': "The company where the training was done and, if you know it, its VAT number.",
        'ca_ES': "L'empresa on es va fer la formació i, si el saps, el seu NIF.",
        'es_ES': "La empresa donde se hizo la formación y, si lo sabes, su NIF.",
    },
    'start': {
        'en_US': "The first day of the training at the company.",
        'ca_ES': "El primer dia de la formació a l'empresa.",
        'es_ES': "El primer día de la formación en la empresa.",
    },
    'end': {
        'en_US': "The last day of the training at the company.",
        'ca_ES': "L'últim dia de la formació a l'empresa.",
        'es_ES': "El último día de la formación en la empresa.",
    },
    'hours': {
        'en_US': "The total hours of the training, e.g. 400.",
        'ca_ES': "El total d'hores de la formació, per exemple 400.",
        'es_ES': "El total de horas de la formación, por ejemplo 400.",
    },
    'agreement': {
        'en_US': "The agreement's number in sBID, e.g. 2025146951.",
        'ca_ES': "El número del conveni a sBID, per exemple 2025146951.",
        'es_ES': "El número del convenio en sBID, por ejemplo 2025146951.",
    },
}
FCT_SCHOOL_YEAR_OLD_NAME = "School year of the training"
FCT_SCHOOL_YEAR_NAME = {'en_US': "Academic course", 'ca_ES': "Curs acadèmic", 'es_ES': "Curso académico"}


def _fct_field_id(cr, key):
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'ems' AND model = 'ems.certificate.type.field' "
               "AND name = %s", (f'certificate_field_fct_{key}',))
    row = cr.fetchone()
    return row[0] if row else None


def _fct_certificate_details(cr):
    for key, hint in FCT_HINTS.items():
        field_id = _fct_field_id(cr, key)
        if field_id:
            cr.execute("UPDATE ems_certificate_type_field SET help = %s WHERE id = %s AND help IS NULL",
                       (json.dumps(hint), field_id))
    school_year_id = _fct_field_id(cr, 'school_year')
    if school_year_id:
        cr.execute("UPDATE ems_certificate_type_field SET name = %s WHERE id = %s AND name->>'en_US' = %s",
                   (json.dumps(FCT_SCHOOL_YEAR_NAME), school_year_id, FCT_SCHOOL_YEAR_OLD_NAME))
    start_id, end_id = _fct_field_id(cr, 'start'), _fct_field_id(cr, 'end')
    if start_id and end_id:
        cr.execute("""
            UPDATE ems_certificate_type_field end_field SET after_field_id = %s
              FROM ems_certificate_type_field start_field
             WHERE end_field.id = %s AND start_field.id = %s AND end_field.after_field_id IS NULL
               AND end_field.type_id = start_field.type_id
               AND end_field.field_type = 'date' AND start_field.field_type = 'date'
        """, (start_id, end_id, start_id))
    _logger.info("Issue #858: FCT certificate details given their hints.")


def migrate(cr, version):
    _fct_certificate_details(cr)
