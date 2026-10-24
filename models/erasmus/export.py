# -*- coding: utf-8 -*-

import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .records import safe_name

# Who exports: the Erasmus team, the Secretary and the administrator. Confidential documents
# (health, inclusion, bank data) only leave EMS in an audit export, asked for by the Erasmus
# coordinator or the administrator with a reason.
EXPORTERS = ('ems.group_erasmus', 'ems.group_secretary', 'ems.group_academic_admin')
AUDITORS = ('ems.group_erasmus_coordinator', 'ems.group_academic_admin')
# The folder of the documents common to several mobilities, inside 02_Mobilitats.
COMMON_FOLDER = '00_Documentacio_comuna'
CHUNK = 1024 * 1024


class EmsErasmusExport(models.Model):
    """An export of Erasmus+ documents as a ZIP: one participant's record for one mobility, or a
    whole project with every mobility's record. Each export is kept as a log line (who, when, what,
    whether it included the confidential documents and why) and is downloaded once, by whoever
    asked for it: the ZIP is built on the fly from the files where they are and never stored. The
    files go in unchanged (signed PDFs included), with an index of every document (also the ones
    still missing), a manifest and their SHA-256 hashes to verify the copy archived in Drive.
    See docs/en/developers/erasmus/records.md."""
    _name = 'ems.erasmus.export'
    _description = 'Erasmus+ document export'
    _order = 'date desc, id desc'

    scope = fields.Selection(string="What", required=True, readonly=True, selection=[
        ('project', "Whole project"), ('record', "Participant's record")])
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', readonly=True,
                                 ondelete='restrict', index=True)
    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', readonly=True,
                                  ondelete='restrict', index=True)
    include_confidential = fields.Boolean(
        string="Audit export (with confidential documents)",
        help="Includes the health, inclusion and bank documents. Only the Erasmus coordinator or the "
             "administrator, with a reason, for an audit or a SEPIE request.")
    reason = fields.Char(string="Reason", help="Required for an audit export: which audit or request it is for.")
    requester_id = fields.Many2one(string="Requested by", comodel_name='res.users', readonly=True,
                                   default=lambda self: self.env.user, index=True)
    date = fields.Datetime(string="Requested on", readonly=True, default=fields.Datetime.now)
    state = fields.Selection(string="State", required=True, readonly=True, default='requested', selection=[
        ('requested', "Requested"), ('done', "Downloaded")])
    file_count = fields.Integer(string="Files", readonly=True)
    missing_count = fields.Integer(string="Documents missing", readonly=True,
                                   help="Required documents not complete when it was exported, listed in the index.")
    zip_sha256 = fields.Char(string="SHA-256 of the ZIP", readonly=True,
                             help="To check that a copy archived elsewhere is the one downloaded.")
    can_audit = fields.Boolean(string="Can export for an audit", compute='_compute_can_audit')

    @api.depends_context('uid')
    def _compute_can_audit(self):
        self.can_audit = self._ems_is_auditor()

    def _compute_display_name(self):
        for export in self:
            target = export.mobility_id.display_name if export.scope == 'record' else export.project_id.name
            export.display_name = f"{target} - {export.date and export._ems_local(export.date)}"

    @api.model_create_multi
    def create(self, vals_list):
        """Only who may export creates one, always as themselves."""
        self._ems_check_exporter()
        for vals in vals_list:
            vals.update({'requester_id': self.env.uid, 'date': fields.Datetime.now(), 'state': 'requested'})
        return super(EmsErasmusExport, self.sudo()).create(vals_list).sudo(False)

    # --- requesting it --------------------------------------------------------------------------

    @api.model
    def _ems_open_wizard(self, project_id=False, mobility_id=False):
        """The dialog that asks for an export of a project or of a participant's record."""
        self._ems_check_exporter()
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'view_mode': 'form', 'target': 'new',
            'name': _("Export the record") if mobility_id else _("Export the project"),
            'views': [(self.env.ref('ems.view_erasmus_export_form').id, 'form')],
            'context': {'default_scope': 'record' if mobility_id else 'project',
                        'default_project_id': project_id, 'default_mobility_id': mobility_id},
        }

    def action_generate(self):
        """Check the request and download the ZIP (the controller builds it, once)."""
        self.ensure_one()
        self._ems_check_request()
        return {'type': 'ir.actions.act_url', 'target': 'download', 'url': f'/ems/erasmus/export/{self.id}'}

    @api.model
    def _ems_is_auditor(self):
        return self.env.su or any(self.env.user.has_group(group) for group in AUDITORS)

    @api.model
    def _ems_check_exporter(self):
        if not (self.env.su or any(self.env.user.has_group(group) for group in EXPORTERS)):
            raise AccessError(_("Only the Erasmus team and the Secretary export Erasmus+ documents."))

    def _ems_check_request(self):
        """Who asked for it downloads it, once; an audit export needs the right role and a reason;
        a record belongs to the mobility it says, and a project export to its project."""
        self.ensure_one()
        self._ems_check_exporter()
        if self.requester_id != self.env.user or self.state != 'requested':
            raise AccessError(_("This export was already downloaded or was asked for by someone else."))
        if self.include_confidential:
            if not self._ems_is_auditor():
                raise AccessError(_("Only the Erasmus coordinator exports the confidential documents."))
            if not (self.reason or '').strip():
                raise UserError(_("Write the reason for the audit export first."))
        if self.scope == 'record' and not self.mobility_id:
            raise UserError(_("Choose the mobility whose record to export."))
        if self.scope == 'project' and not self.project_id:
            raise UserError(_("Choose the project to export."))

    # --- what goes in ---------------------------------------------------------------------------

    def _ems_entries(self):
        """Every line of the index, as dicts: the files (with `content`, an attachment or bytes) and
        the documents still missing or not applicable (no `content`). Read as superuser once the
        request is checked, and only from the records of this mobility or this project."""
        self.ensure_one()
        if self.scope == 'record':
            mobility = self.sudo().mobility_id
            return self._ems_record_entries(mobility, '', shared_paths={})
        project = self.sudo().project_id
        entries, shared_paths = [], {}
        for document in project.document_ids:
            if document.confidential and not self.include_confidential:
                continue
            folder = document.category
            if folder == '02_Mobilitats':
                folder = f"{folder}/{COMMON_FOLDER}"
            files = self._ems_files(f"{folder}/{safe_name(document.name)}", document.attachment_ids)
            for entry in files:
                entry.update(category=document.category, document=document.name, status=_("Complete"),
                             notes=document.notes or '')
                shared_paths.setdefault(document.id, []).append(entry['path'])
            entries += files or [self._ems_pending(document.category, document.name, _("No file"))]
        for call in project.mobility_ids.call_id:
            folder = f"01_Projecte/{safe_name(_('Calls'))}/{safe_name(call.name)}"
            attachments = self._ems_field_attachments(call, 'rules_document').get(call.id) or self.env['ir.attachment']
            names = {attachment.id: call.rules_filename for attachment in attachments}
            for resolution in call.resolution_ids.filtered(lambda resolution: resolution.state == 'published'):
                attachments |= resolution._ems_stored_pdf() or attachments.browse()
            for entry in self._ems_files(folder, attachments, versions=False, names=names):
                entries.append({**entry, 'category': '01_Projecte', 'document': call.name, 'status': _("Complete")})
        for mobility in self._ems_project_mobilities(project):
            entries += self._ems_record_entries(mobility, f"02_Mobilitats/{self._ems_record_folder(mobility)}/",
                                                shared_paths)
        invoice_files = self._ems_field_attachments(project.invoice_ids, 'document')
        for invoice in project.invoice_ids:
            document = invoice_files.get(invoice.id) or self.env['ir.attachment']
            folder = f"03_Economia/{safe_name(_('Invoices'))}/{safe_name(invoice.name)}"
            for entry in self._ems_files(folder, document | invoice.receipt_ids, versions=False,
                                         names={document.id: invoice.document_filename}):
                entries.append({**entry, 'category': '03_Economia', 'document': invoice.name, 'status': _("Complete")})
        return entries

    @api.model
    def _ems_project_mobilities(self, project):
        return project.mobility_ids.filtered(lambda mobility: mobility.state != 'cancelled')

    def _ems_record_entries(self, mobility, prefix, shared_paths):
        """The record of one participant in one mobility, in the four categories: the call's
        documents that apply (every version uploaded), the commitment letter signed in EMS, the
        weekly self-assessments, the project's documents about them and their transfer receipts.
        In a project export a document shared with others is referenced from the index (its path
        in the common folder), not copied again."""
        self.ensure_one()
        entries = []
        participant = mobility.partner_id.name
        for line in mobility._ems_record_lines():
            if line.confidential and not self.include_confidential:
                if line.is_required:
                    entries.append(self._ems_pending(line.file_category, line.name, line._ems_file_state_label(),
                                                     _("Confidential: only in an audit export."), line, prefix))
                continue
            folder = f"{prefix}{line.file_category}/{safe_name(line.name)}"
            files = self._ems_files(folder, line.attachment_ids) + \
                self._ems_files(folder, line.prepared_attachment_ids, version_prefix=f"{_('team')}_v")
            for entry in files:
                entry.update(category=line.file_category, document=line.name, status=line._ems_file_state_label(),
                             required=line.is_required, signers=line.signers or '')
            entries += files or [self._ems_pending(line.file_category, line.name, line._ems_file_state_label(),
                                                   line=line, prefix=prefix)]
        if mobility.commitment_signed_date or mobility.commitment_guardian_signed_date:
            entries.append({
                'path': f"{prefix}02_Abans_de_la_mobilitat/{safe_name(_('Commitment letter'))}.html",
                'content': self._ems_commitment_html(mobility), 'category': '02_Abans_de_la_mobilitat',
                'document': _("Commitment letter"), 'status': _("Signed in EMS"), 'required': True,
                'date': self._ems_local(mobility.commitment_signed_date or mobility.commitment_guardian_signed_date),
                'author': (mobility.commitment_signed_by_id or mobility.commitment_guardian_signed_by_id).name})
        if mobility.self_assessment_ids:
            pdf, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'ems.action_report_erasmus_self_assessment', mobility.ids)
            entries.append({'path': f"{prefix}03_Durant_la_mobilitat/{safe_name(_('Weekly self-assessment'))}.pdf",
                            'content': pdf, 'category': '03_Durant_la_mobilitat',
                            'document': _("Weekly self-assessment"), 'status': mobility.self_assessment_progress})
        for document in mobility.project_document_ids:
            if document.confidential and not self.include_confidential:
                continue
            category = document.participant_category or '03_Durant_la_mobilitat'
            if document.id in shared_paths:
                entries += [{'path': '', 'category': category, 'document': document.name, 'status': _("Complete"),
                             'notes': _("Shared document: %s", path)} for path in shared_paths[document.id]]
                continue
            for entry in self._ems_files(f"{prefix}{category}/{safe_name(document.name)}", document.attachment_ids):
                entries.append({**entry, 'category': category, 'document': document.name, 'status': _("Complete")})
        for payment in mobility.payment_ids:
            folder = (f"03_Economia/{safe_name(_('Transfers'))}/{self._ems_record_folder(mobility)}" if prefix
                      else f"01_Dades_i_autoritzacions/{safe_name(_('Grant payments'))}")
            for entry in self._ems_files(folder, payment.receipt_ids, versions=False):
                entries.append({**entry, 'category': folder.split('/')[0], 'document': _("Transfer receipt"),
                                'status': _("Complete")})
        for entry in entries:
            entry.setdefault('participant', participant)
            entry.setdefault('mobility', mobility.id)
        return entries

    def _ems_files(self, folder, attachments, versions=True, version_prefix='v', names=None):
        """One entry per attachment under `folder`, in upload order: `v1_`, `v2_`... before the
        original name, so every version is kept and named consistently. `names`: the file name of
        a Binary field's attachment (stored apart from it), by attachment id."""
        entries = []
        for number, attachment in enumerate(attachments.sorted('id'), 1):
            name = safe_name((names or {}).get(attachment.id) or attachment.name)
            entries.append({
                'path': f"{folder}/{version_prefix}{number}_{name}" if versions else f"{folder}/{name}",
                'content': attachment, 'version': number if versions else '', 'attachment': attachment.id,
                'date': self._ems_local(attachment.create_date), 'author': attachment.create_uid.name})
        return entries

    def _ems_pending(self, category, document, status, notes='', line=None, prefix=''):
        return {'path': '', 'category': category, 'document': document, 'status': status, 'notes': notes,
                'required': bool(line and line.is_required), 'signers': line and line.signers or ''}

    @api.model
    def _ems_record_folder(self, mobility):
        """A stable folder name for a participant's record: ALU (students) or PROF (staff), the
        mobility's number and the participant's name."""
        kind = 'PROF' if mobility.audience == 'staff' else 'ALU'
        return safe_name(f"{kind}{mobility.id:05d}_{mobility.partner_id.name}")

    @api.model
    def _ems_field_attachments(self, records, field_name):
        """The file of a Binary field of `records` (stored as an attachment), by record id, in one query."""
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', records._name), ('res_id', 'in', records.ids), ('res_field', '=', field_name)])
        return {attachment.res_id: attachment for attachment in attachments}

    def _ems_commitment_html(self, mobility):
        """The commitment letter as it was signed in EMS, with who signed it, when and from where."""
        signatures = [(_("Participant"), mobility.commitment_signed_by_id, mobility.commitment_signed_date,
                       mobility.commitment_signed_ip),
                      (_("Family"), mobility.commitment_guardian_signed_by_id,
                       mobility.commitment_guardian_signed_date, mobility.commitment_guardian_signed_ip)]
        rows = Markup('').join(
            Markup('<li>%s: %s, %s (IP %s)</li>') % (label, user.name, self._ems_local(date), ip or '-')
            for label, user, date, ip in signatures if date)
        page = Markup('<!DOCTYPE html><html><head><meta charset="utf-8"/><title>%s</title></head><body>'
                      '<h1>%s</h1><p>%s</p>%s<h2>%s</h2><ul>%s</ul></body></html>') % (
            _("Commitment letter"), _("Commitment letter"), mobility.display_name,
            mobility.commitment_signed_text or Markup(''), _("Signed in EMS"), rows)
        return str(page).encode()

    def _ems_local(self, value):
        return self.env['ems.erasmus.call']._ems_local_format(value)

    # --- the ZIP --------------------------------------------------------------------------------

    def _ems_zip(self):
        """The ZIP in a temporary file (the caller closes it), and its log line updated. Files are
        copied one at a time from the file store in chunks, hashing them on the way: a large project
        never needs to fit in memory. Stored, not compressed: PDFs, photos and videos hardly shrink.
        Only folders with files appear; the index lists what is missing."""
        self.ensure_one()
        self._ems_check_request()
        entries = self._ems_entries()
        root = self._ems_root_name()
        archive = tempfile.TemporaryFile()
        used, hashes = set(), []
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for entry in entries:
                if not entry.get('path'):
                    continue
                path = self._ems_unique(entry['path'], used)
                entry['path'] = path
                entry['sha256'], entry['size'] = self._ems_write(bundle, f"{root}/{path}", entry['content'])
                hashes.append(f"{entry['sha256']}  {path}")
            bundle.writestr(f"{root}/index.csv", self._ems_index_csv(entries))
            bundle.writestr(f"{root}/manifest.json", self._ems_manifest(entries))
            bundle.writestr(f"{root}/SHA256SUMS", ''.join(f"{line}\n" for line in hashes))
        digest = hashlib.sha256()
        archive.seek(0)
        for chunk in iter(lambda: archive.read(CHUNK), b''):
            digest.update(chunk)
        archive.seek(0)
        export = self.sudo()
        mobilities = export.mobility_id or self._ems_project_mobilities(export.project_id)
        export.write({'state': 'done', 'file_count': len(hashes), 'missing_count': sum(mobilities.mapped('record_missing')),
                      'zip_sha256': digest.hexdigest()})
        if export.mobility_id:
            export.mobility_id.chatter(self._ems_log_message())
        return archive

    def _ems_root_name(self):
        if self.scope == 'record':
            mobility = self.sudo().mobility_id
            return safe_name(f"{self._ems_record_folder(mobility)} - {mobility.call_id.name}")
        return safe_name(self.sudo().project_id.name)

    @api.model
    def _ems_unique(self, path, used):
        stem, extension = os.path.splitext(path)
        counter = 1
        while path in used:
            counter += 1
            path = f"{stem} ({counter}){extension}"
        used.add(path)
        return path

    @api.model
    def _ems_write(self, bundle, name, content):
        """Copy one file into the ZIP unchanged and return its SHA-256 and size."""
        digest, size = hashlib.sha256(), 0
        with bundle.open(zipfile.ZipInfo(name, date_time=fields.Datetime.now().timetuple()[:6]), 'w',
                         force_zip64=True) as target:
            for chunk in self._ems_chunks(content):
                digest.update(chunk)
                size += len(chunk)
                target.write(chunk)
        return digest.hexdigest(), size

    @api.model
    def _ems_chunks(self, content):
        if isinstance(content, bytes):
            yield content
            return
        attachment = content.sudo()
        if attachment.store_fname:
            with open(attachment._full_path(attachment.store_fname), 'rb') as source:
                yield from iter(lambda: source.read(CHUNK), b'')
        else:
            yield attachment.raw or b''

    def _ems_index_csv(self, entries):
        """The index: every document, with its file (or none, when missing), state, dates and hash.
        UTF-8 with BOM so a spreadsheet opens the accents right."""
        labels = {
            **dict(self.env['ems.erasmus.project.document']._fields['category']._description_selection(self.env)),
            **dict(self.env['ems.erasmus.call.document']._fields['file_category']._description_selection(self.env))}
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([_("Participant"), _("Mobility"), _("Category"), _("Document"), _("Required"), _("Status"),
                         _("Signed by"), _("Version"), _("Path"), _("Uploaded on"), _("Uploaded by"), _("Size"),
                         _("SHA-256"), _("Notes")])
        for entry in entries:
            writer.writerow([entry.get('participant', ''), entry.get('mobility', ''),
                             labels.get(entry.get('category'), entry.get('category') or ''), entry.get('document', ''),
                             _("Yes") if entry.get('required') else '', entry.get('status') or '',
                             entry.get('signers', ''), entry.get('version', ''), entry.get('path', ''),
                             entry.get('date', ''), entry.get('author', ''), entry.get('size', ''),
                             entry.get('sha256', ''), entry.get('notes', '')])
        return '﻿' + buffer.getvalue()

    def _ems_manifest(self, entries):
        """What was exported, by whom and when, and every file with its hash, for whoever verifies the
        archived copy."""
        export = self.sudo()
        keys = ('path', 'participant', 'mobility', 'category', 'document', 'status', 'version', 'attachment', 'date',
                'author', 'size', 'sha256')
        return json.dumps({
            'export': export.id, 'scope': export.scope, 'project': export.project_id.name or None,
            'mobility': export.mobility_id.display_name or None, 'requested_by': export.requester_id.name,
            'requested_on': self._ems_local(export.date), 'audit': export.include_confidential,
            'reason': export.reason or None,
            'files': [{key: entry.get(key) for key in keys} for entry in entries if entry.get('path')],
            'not_complete': [{key: entry.get(key) for key in ('participant', 'category', 'document', 'status')}
                             for entry in entries if not entry.get('path') and entry.get('required')],
        }, ensure_ascii=False, indent=1, default=str)

    def _ems_log_message(self):
        message = _("Documents exported (%(files)s files) by %(user)s.", files=self.file_count,
                    user=self.requester_id.name)
        if self.include_confidential:
            message += ' ' + _("Audit export with the confidential documents: %s", self.reason)
        return escape(message)
