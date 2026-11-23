# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Issue #851: the FCT certificate's text, now a translatable value of its type. The type is
# seeded with noupdate, so an existing installation gets it here (a clean install from the XML and
# the .po files, with these same words).
FCT_TEXT = {
    'en_US': "That {name}, with identity document {document}, a student of {study}, did {hours} hours of workplace "
             "training (FCT) in the school year {school_year} at the company {company}[, with VAT number "
             "{company_vat}], from {start} to {end}.\n\nSource: the training agreement[ registered in sBID with "
             "number {agreement}], a copy of which is attached.",
    'ca_ES': "Que {name}, amb document d'identitat {document}, estudiant de {study}, va fer {hours} hores de formació "
             "en centres de treball (FCT) el curs {school_year} a l'empresa {company}[, amb NIF {company_vat}], amb "
             "data d'inici {start} i data de finalització {end}.\n\nFont: el conveni de formació[ registrat a sBID "
             "amb el número {agreement}], del qual s'adjunta una còpia.",
    'es_ES': "Que {name}, con documento de identidad {document}, estudiante de {study}, realizó {hours} horas de "
             "formación en centros de trabajo (FCT) en el curso {school_year} en la empresa {company}[, con NIF "
             "{company_vat}], del {start} al {end}.\n\nFuente: el convenio de formación[ registrado en sBID con el "
             "número {agreement}], del que se adjunta una copia.",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _generic_certificate_types(env)


def _generic_certificate_types(env):
    """Issue #851: a certificate type defines its own details and text, instead of the FCT ones
    fixed in the code. The FCT details come with the data file (new records); its text is written
    here, since the type is noupdate. No request had been processed when the old FCT columns went
    (the feature was not announced yet), so their values are not moved: each request just gets the
    lines of its type's details."""
    fct = env.ref('ems.certificate_type_fct', raise_if_not_found=False)
    if not fct:
        return
    for lang, text in FCT_TEXT.items():
        if lang == 'en_US' or env['res.lang']._lang_get(lang):
            fct.with_context(lang=lang).certificate_text = text
    certificates = env['ems.certificate'].search([])
    certificates._ems_sync_values()
    _logger.info("Certificates: FCT text written, details added to %s requests.", len(certificates))
