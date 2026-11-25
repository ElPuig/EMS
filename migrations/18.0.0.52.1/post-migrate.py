# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _certificate_documents_by_step(cr)
    _certificate_documents_applicant(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _certificate_open_requests_documents(env)
    _certificate_other_documentation(env)


def _column_exists(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
               (table, column))
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _certificate_documents_by_step(cr):
    """Issue #861: a type's documents are no longer all required before issuing by one checkbox
    of the type (Required attached documentation): each one says the step it is required before,
    as the details do. Every document of a type that had the checkbox ticked becomes required
    before its issuing step. The FCT agreement too, whatever the checkbox: it is the document the
    FCT certificate always required, and the checkbox was found unticked by mistake on 2026-11-25."""
    # The old column is only dropped once the upgrade ends, after this script.
    ticked = "certificate_type.requires_documents" if _column_exists(cr, 'ems_certificate_type', 'requires_documents') \
        else "FALSE"
    cr.execute(f"""
        UPDATE ems_certificate_type_document document
           SET required_step_id = step.id
          FROM ems_certificate_type certificate_type, ems_certificate_type_step step
         WHERE certificate_type.id = document.type_id
           AND step.type_id = document.type_id AND step.action = 'issue'
           AND document.required_step_id IS NULL
           AND ({ticked}
                OR document.id = (SELECT res_id FROM ir_model_data
                                   WHERE module = 'ems' AND name = 'certificate_document_fct_agreement'))
    """)
    _logger.info("Issue #861: %s certificate document(s) now required before their issuing step", cr.rowcount)


def _certificate_documents_applicant(cr):
    """Issue #861: who attaches a document is no longer chosen by positions: whoever takes part in
    the circuit always may, and Applicant says whether the applicant may too. A document with no
    position and no applicant ticked meant "anyone", the applicant included, so it keeps the
    applicant; one limited to positions keeps them out."""
    if not _table_exists(cr, 'ems_certificate_type_document_ems_role_rel'):
        return
    cr.execute("""
        UPDATE ems_certificate_type_document document
           SET applicant_uploads = TRUE
         WHERE NOT COALESCE(document.applicant_uploads, FALSE)
           AND NOT EXISTS (SELECT 1 FROM ems_certificate_type_document_ems_role_rel rel
                            WHERE rel.ems_certificate_type_document_id = document.id)
    """)
    _logger.info("Issue #861: %s certificate document(s) the applicant may attach", cr.rowcount)


def _certificate_open_requests_documents(env):
    """Issue #861: every request gets a line for each document of its type. Those of a type that
    did not require documentation had none: the open ones get them now (a closed one is kept as it
    was issued)."""
    open_requests = env['ems.certificate'].search([('state', 'in', ('draft', 'in_progress', 'documentation'))])
    open_requests._ems_sync_documents()


def _certificate_other_documentation(env):
    """Issue #861: the other documentation of a request was a list of files; now each file is a
    document of its own (its name, its files and whether it goes into the certificate: not, as
    before)."""
    if not _table_exists(env.cr, 'ems_certificate_other_attachment_rel'):
        return
    env.cr.execute("SELECT certificate_id, attachment_id FROM ems_certificate_other_attachment_rel ORDER BY attachment_id")
    rows = env.cr.fetchall()
    Attachment = env['ir.attachment']
    for certificate_id, attachment_id in rows:
        attachment = Attachment.browse(attachment_id).exists()
        if not attachment:
            continue
        line = env['ems.certificate.document'].create({
            'certificate_id': certificate_id, 'other_name': attachment.name, 'append_to_certificate': False,
            'attachment_ids': [(6, 0, attachment.ids)],
        })
        attachment.write({'res_model': line._name, 'res_id': line.id})
    env.cr.execute("DELETE FROM ems_certificate_other_attachment_rel")
    _logger.info("Issue #861: %s other certificate document(s) moved to document lines", len(rows))
