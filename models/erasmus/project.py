# -*- coding: utf-8 -*-

import os
import re
import tempfile
import zipfile

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .call import PROJECTS, SEPIE_FOLDERS, STAGE_FOLDERS

# SEPIE: keep the documents 3 years after the project ends, 5 when its grant is above 60,000 € (issue #697).
LARGE_PROJECT = 60000


def _safe_name(name):
    """A file or folder name that works on every system, accents kept."""
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', (name or '').strip()).strip('. ') or '_'


class EmsErasmusProject(models.Model):
    """Issue #687 - an Erasmus+ project the centre runs (its grant agreement), to which the Erasmus
    coordination assigns each mobility: CFGM on a KA121-VET project, CFGS on a KA131-HED one.
    Several of each kind can be active at once (one per call year). Issue #697: its documents, in
    SEPIE's folders, downloaded as one dossier."""
    _name = 'ems.erasmus.project'
    _description = 'Erasmus+ project'
    _order = 'active desc, kind, name desc'

    name = fields.Char(string="Agreement number", required=True, help="e.g. 2026-1-ES01-KA121-VET-000123456")
    kind = fields.Selection(string="Kind", selection=PROJECTS, required=True)
    date_start = fields.Date(string="Start")
    date_end = fields.Date(string="End")
    active = fields.Boolean(string="Active", default=True)
    mobility_ids = fields.One2many(string="Mobilities", comodel_name='ems.erasmus.mobility', inverse_name='project_id')
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency',
                                  default=lambda self: self.env.company.currency_id)
    budget = fields.Monetary(string="Grant awarded", help="The project's grant: above 60,000 € its documents are kept "
                                                          "5 years after it ends, otherwise 3.")
    keep_until = fields.Date(string="Keep the documents until", compute='_compute_keep_until',
                             help="SEPIE: 3 years after the project ends, 5 when its grant is above 60,000 €.")
    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.project.document',
                                   inverse_name='project_id')
    invoice_ids = fields.One2many(string="Invoices", comodel_name='ems.erasmus.invoice', inverse_name='project_id')
    payment_ids = fields.One2many(string="Grant payments", comodel_name='ems.erasmus.payment',
                                  inverse_name='project_id')

    @api.depends('date_end', 'budget')
    def _compute_keep_until(self):
        for project in self:
            years = 5 if project.budget > LARGE_PROJECT else 3
            project.keep_until = project.date_end and project.date_end + relativedelta(years=years)

    @api.depends('name', 'kind')
    def _compute_display_name(self):
        kinds = dict(self._fields['kind'].selection)
        for project in self:
            project.display_name = f"{project.name} ({kinds.get(project.kind, '')})" if project.kind else project.name

    def action_download_dossier(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'target': 'download',
                'url': f'/ems/erasmus/project/{self.id}/dossier'}

    # --- dossier --------------------------------------------------------------------------------

    def _ems_check_dossier_reader(self):
        user = self.env.user
        if not any(user.has_group(group) for group in (
                'ems.group_erasmus', 'ems.group_secretary', 'ems.group_academic_admin')):
            raise AccessError(_("Only the Erasmus team and the Secretary download a project's dossier."))

    def _ems_dossier_files(self):
        """Every file of the project, as (folder, path inside it, attachment), in SEPIE's folders:
        what the team and the Secretary uploaded to the project, the published calls and resolutions,
        the documents of the applications and mobilities charged to it, its invoices and the transfer
        receipts. Nothing is copied: the dossier is built from where each file already is."""
        self.ensure_one()
        self._ems_check_dossier_reader()
        # Confidential files (e.g. evidence of fewer opportunities) only for the Erasmus team.
        confidential = self.env.user.has_group('ems.group_erasmus') or self.env.user.has_group('ems.group_academic_admin')
        project = self.sudo()
        files = []
        for document in project.document_ids:
            subfolder = _safe_name(document.name)
            files += [(document.folder, f"{subfolder}/{attachment.name}", attachment)
                      for attachment in document.attachment_ids]
        mobilities = project.mobility_ids.filtered(lambda mobility: mobility.state != 'cancelled')
        calls = mobilities.call_id
        selection = '02_Publicacionyseleccion'
        rules_files = self._ems_field_attachments(calls, 'rules_document')
        for call in calls:
            call_folder = _safe_name(call.name)
            rules = rules_files.get(call.id)
            if rules:
                files.append((selection, f"{call_folder}/{_safe_name(call.rules_filename or rules.name)}", rules))
            for resolution in call.resolution_ids.filtered(lambda resolution: resolution.state == 'published'):
                pdf = resolution._ems_stored_pdf()
                if pdf:
                    files.append((selection, f"{call_folder}/{_safe_name(pdf.name)}", pdf))
        for mobility in mobilities:
            person = _safe_name(mobility.partner_id.name)
            for line in mobility.application_id.document_ids | mobility.document_ids:
                if line.confidential and not confidential:
                    continue
                document = line.call_document_id
                folder = document.sepie_folder or STAGE_FOLDERS.get(document.stage, selection)
                for attachment in line.attachment_ids | line.prepared_attachment_ids:
                    files.append((folder, f"{person}/{_safe_name(document.name)}/{attachment.name}", attachment))
            for payment in mobility.payment_ids:
                files += [('08_FacturasyTransferencias', f"Transferencias/{person}/{attachment.name}", attachment)
                          for attachment in payment.receipt_ids]
        invoice_files = self._ems_field_attachments(project.invoice_ids, 'document')
        for invoice in project.invoice_ids:
            folder = f"Facturas/{_safe_name(invoice.name)}"
            invoice_file = invoice_files.get(invoice.id)
            if invoice_file:
                files.append(('08_FacturasyTransferencias',
                              f"{folder}/{_safe_name(invoice.document_filename or invoice_file.name)}", invoice_file))
            files += [('08_FacturasyTransferencias', f"{folder}/{attachment.name}", attachment)
                      for attachment in invoice.receipt_ids]
        return files

    def _ems_field_attachments(self, records, field_name):
        """The file of a Binary field of `records` (stored as an attachment), by record id, in one query."""
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', records._name), ('res_id', 'in', records.ids), ('res_field', '=', field_name)])
        return {attachment.res_id: attachment for attachment in attachments}

    def _ems_dossier_zip(self):
        """The dossier as a ZIP in a temporary file (the caller closes it): one folder per SEPIE
        folder, even empty, so the structure is always the one SEPIE asks for. Stored, not
        compressed: the files are PDFs, photos and videos that hardly shrink, and building it stays
        fast and light whatever the project's size."""
        self.ensure_one()
        files = self._ems_dossier_files()
        root = _safe_name(self.name)
        archive = tempfile.TemporaryFile()
        used = set()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED, allowZip64=True) as dossier:
            for folder, _label in SEPIE_FOLDERS:
                dossier.writestr(f"{root}/{folder}/", b'')
            for folder, path, attachment in files:
                name = f"{root}/{folder}/{path}"
                stem, extension = os.path.splitext(name)
                counter = 1
                while name in used:
                    counter += 1
                    name = f"{stem} ({counter}){extension}"
                used.add(name)
                dossier.writestr(name, attachment.raw or b'')
        archive.seek(0)
        return archive


class EmsErasmusProjectDocument(models.Model):
    """Issue #697 - files of a project that no other EMS record holds (the project application,
    the participants' link with the centre, preparatory visits, exceptional costs, dissemination...),
    filed in one of SEPIE's folders."""
    _name = 'ems.erasmus.project.document'
    _description = 'Erasmus+ project document'
    _order = 'folder, date desc, id desc'

    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', required=True,
                                 ondelete='restrict', index=True)
    folder = fields.Selection(string="Folder", selection=SEPIE_FOLDERS, required=True)
    name = fields.Char(string="Name", required=True)
    date = fields.Date(string="Date", default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_project_document_attachment_rel')
    mobility_ids = fields.Many2many(string="Participants", comodel_name='ems.erasmus.mobility',
                                    relation='ems_erasmus_project_document_mobility_rel',
                                    domain="[('project_id', '=', project_id)]",
                                    help="Optional: the participants it is about.")
    notes = fields.Text(string="Notes")
