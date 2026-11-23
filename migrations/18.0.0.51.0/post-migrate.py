# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import sql

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
    _fill_closed_case_file_tutor(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _queue_existing_compression(env)
    _step_positions(env)
    _generic_certificate_types(env)


def _fill_closed_case_file_tutor(cr):
    """Issue #817: the case file now stores its own tutor (computed from the student's group while
    they have one). A case file already closed by the withdrawal belongs to a student with no
    group, so the new column came out empty: take the tutor the student had that course from their
    academic history, which freezes it just before the exit."""
    cr.execute("""
        UPDATE ems_ex_officio_withdrawal withdrawal
           SET tutor_id = record.tutor_id
          FROM ems_student_year_record record
         WHERE withdrawal.tutor_id IS NULL
           AND record.student_id = withdrawal.student_id
           AND record.course_id = withdrawal.course_id
           AND record.tutor_id IS NOT NULL
    """)
    _logger.info("Ex officio case files: tutor restored from the academic history on %s", cr.rowcount)


def _queue_existing_compression(env):
    """Issue #799: queues the compression of the PDF files and images stored before it existed.
    It only queues: every file is compressed later by a background job (queue_job), at low
    priority, so the upgrade itself takes seconds whatever the number of files. A clean install
    has no stored files, so it needs no equivalent in post_init_hook."""
    queued = env['ir.attachment']._ems_queue_existing_compression()
    _logger.info("Compression of %s stored files queued (issue #799)", queued)


def _step_positions(env):
    """Issue #851: a step of a certificate circuit may be done by several positions. Each step keeps
    the one it had (its old column is still there: Odoo drops it after the migration), and the FCT
    step that completes the data also goes to the new secretary technicians, as on a clean install."""
    cr = env.cr
    if sql.column_exists(cr, 'ems_certificate_type_step', 'role_id'):
        cr.execute("""
            INSERT INTO ems_certificate_type_step_role_rel (step_id, role_id)
            SELECT id, role_id FROM ems_certificate_type_step WHERE role_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        cr.execute("ALTER TABLE ems_certificate_type_step ALTER COLUMN role_id DROP NOT NULL")
        env.invalidate_all()
    step = env.ref('ems.certificate_step_fct_complete', raise_if_not_found=False)
    technician = env.ref('ems.role_secretary_technician', raise_if_not_found=False)
    if step and technician:
        step.role_ids = [(4, technician.id)]
    _logger.info("Certificates: step positions moved to the new list.")


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
