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
# Audit D-17: the records of cancelled mobilities and withdrawn participants that hold evidence (a payment made,
# or a document validated or signed), apart from the live ones: inside 02_Mobilitats, and inside a group's folder.
CANCELLED_FOLDER = '99_Cancellades_i_retirades'
CHUNK = 1024 * 1024


class EmsErasmusExport(models.Model):
    """An export of Erasmus+ documents as a ZIP: one participant's record for one mobility, one
    group mobility (its common documents and every participant's record), or a whole project with
    every mobility's record and every group mobility. Each export is kept as a log line (who, when, what,
    whether it included the confidential documents and why) and is downloaded once, by whoever
    asked for it: the ZIP is built on the fly from the files where they are and never stored. The
    files go in unchanged (signed PDFs included), with an index of every document (also the ones
    still missing), a manifest and their SHA-256 hashes to verify the copy archived in Drive.
    See docs/en/developers/erasmus/records.md."""
    _name = 'ems.erasmus.export'
    _description = 'Erasmus+ document export'
    _order = 'date desc, id desc'

    scope = fields.Selection(string="What", required=True, readonly=True, selection=[
        ('project', "Whole project"), ('record', "Participant's record"), ('group', "Group mobility"),
        ('participants', "Participants' spreadsheet")])
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', readonly=True,
                                 ondelete='restrict', index=True)
    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', readonly=True,
                                  ondelete='restrict', index=True)
    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        readonly=True, ondelete='restrict', index=True)
    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', readonly=True, ondelete='restrict',
                              index=True)
    participant_count = fields.Integer(string="Participants", readonly=True,
                                       help="Participants' spreadsheet: how many people it listed.")
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
            target = {'record': export.mobility_id.display_name, 'group': export.group_mobility_id.display_name,
                      'participants': (export.call_id or export.group_mobility_id).display_name,
                      }.get(export.scope) or export.project_id.name
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
    def _ems_open_wizard(self, project_id=False, mobility_id=False, group_mobility_id=False):
        """The dialog that asks for an export of a project, of a participant's record or of a group
        mobility."""
        self._ems_check_exporter()
        scope = 'record' if mobility_id else 'group' if group_mobility_id else 'project'
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'view_mode': 'form', 'target': 'new',
            'name': {'record': _("Export the record"), 'group': _("Export the group mobility"),
                     'project': _("Export the project")}[scope],
            'views': [(self.env.ref('ems.view_erasmus_export_form').id, 'form')],
            'context': {'default_scope': scope, 'default_project_id': project_id, 'default_mobility_id': mobility_id,
                        'default_group_mobility_id': group_mobility_id},
        }

    @api.model
    def _ems_log_spreadsheet(self, target, count):
        """Audit D-10: the participants' spreadsheet of a call or a group mobility (`target`) is built on
        the fly and never stored, but each download is logged as an export (who, when, how many people)
        and in the target's chatter, as a ZIP is."""
        group = target._name == 'ems.erasmus.group.mobility'
        export = self.sudo().create({
            'scope': 'participants', 'call_id': not group and target.id, 'group_mobility_id': group and target.id,
            'project_id': group and target.project_id.id})
        export.sudo().write({'state': 'done', 'participant_count': count})
        target.sudo().chatter(escape(_("Participants' spreadsheet downloaded (%(count)s people) by %(user)s.",
                                       count=count, user=self.env.user.name)))
        return export

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
        if self.scope == 'group' and not self.group_mobility_id:
            raise UserError(_("Choose the group mobility to export."))
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
        if self.scope == 'group':
            return self._ems_group_entries(self.sudo().group_mobility_id, '')
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
        for group in self._ems_project_group_mobilities(project):
            entries += self._ems_group_entries(group, f"02_Mobilitats/{self._ems_group_folder(group)}/")
        cancelled = self._ems_project_cancelled(project)
        for mobility in cancelled:
            entries += self._ems_cancelled(mobility, self._ems_record_entries(
                mobility, f"02_Mobilitats/{CANCELLED_FOLDER}/{self._ems_record_folder(mobility)}/", shared_paths))
        cancelled_groups = self._ems_project_cancelled_groups(project)
        for group in cancelled_groups:
            entries += self._ems_cancelled(group, self._ems_group_entries(
                group, f"02_Mobilitats/{CANCELLED_FOLDER}/{self._ems_group_folder(group)}/"))
        excluded = project.with_context(active_test=False).mobility_ids - self._ems_project_mobilities(project) \
            - cancelled
        entries += [self._ems_excluded(mobility, mobility.partner_id.name, mobility.id) for mobility in excluded]
        entries += [self._ems_excluded(group, group.name, f"GRUP{group.id:05d}") for group in
                    self.env['ems.erasmus.group.mobility'].sudo().with_context(active_test=False).search([
                        ('project_id', '=', project.id)]) - self._ems_project_group_mobilities(project)
                    - cancelled_groups]
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
        """The project's mobilities in its export, archived ones too (audit R-02): only the cancelled
        are left out, and listed as such (`_ems_excluded`)."""
        return project.with_context(active_test=False).mobility_ids.filtered(
            lambda mobility: mobility.state != 'cancelled')

    @api.model
    def _ems_project_group_mobilities(self, project):
        return self.env['ems.erasmus.group.mobility'].sudo().with_context(active_test=False).search([
            ('project_id', '=', project.id), ('state', 'not in', ('draft', 'cancelled'))])

    @api.model
    def _ems_signed_domain(self, prefix=''):
        """Audit D-17: what makes a cancelled or withdrawn record worth keeping in the project's ZIP,
        besides a payment made: one of its own documents valid or with a signature ticked, or its
        commitment letter accepted in EMS (the application's documents do not count: every admitted
        application has them valid)."""
        return ['|', '|', '|', (f'{prefix}document_ids.review_state', '=', 'valid'),
                (f'{prefix}document_ids.signature_ids.signed', '=', True),
                (f'{prefix}commitment_signed_date', '!=', False),
                (f'{prefix}commitment_guardian_signed_date', '!=', False)]

    @api.model
    def _ems_project_cancelled(self, project):
        """The cancelled mobilities of the project with evidence: exported apart (audit D-17)."""
        return self.env['ems.erasmus.mobility'].sudo().with_context(active_test=False).search([
            ('project_id', '=', project.id), ('state', '=', 'cancelled'),
            '|', ('payment_ids.state', '=', 'paid')] + self._ems_signed_domain())

    @api.model
    def _ems_project_cancelled_groups(self, project):
        """The cancelled group mobilities of the project with evidence (common or a participant's)."""
        return self.env['ems.erasmus.group.mobility'].sudo().with_context(active_test=False).search([
            ('project_id', '=', project.id), ('state', '=', 'cancelled'),
            '|', '|', ('document_ids.review_state', '=', 'valid'), ('document_ids.signature_ids.signed', '=', True),
            ('participant_ids', 'any', self._ems_signed_domain())])

    @api.model
    def _ems_cancelled(self, record, entries):
        """A cancelled or withdrawn record kept for its evidence: every line says so, and what it misses
        is not counted as missing."""
        state = dict(record._fields['state']._description_selection(self.env)).get(record.state, record.state)
        for entry in entries:
            entry['notes'] = ". ".join(filter(None, [state, entry.get('notes')]))
            entry['required'] = False
        return entries

    @api.model
    def _ems_excluded(self, record, participant, mobility):
        """The index line of a record an export leaves out on purpose (a cancelled mobility, a group
        mobility in draft or cancelled, a withdrawn participant), also listed in the manifest: nothing
        is left out silently. Its documents stay in EMS and in its own record's export."""
        reason = dict(record._fields['state']._description_selection(self.env)).get(record.state, record.state)
        return {'path': '', 'participant': participant, 'mobility': mobility, 'document': _("Record"),
                'status': reason, 'notes': _("Not exported: %s", reason), 'excluded': reason,
                'record': record.display_name}

    @api.model
    def _ems_archived(self, record, entries):
        """An archived record is exported as any other, each of its lines marked as archived."""
        if not record.active:
            for entry in entries:
                entry['notes'] = ". ".join(filter(None, [_("Archived"), entry.get('notes')]))
        return entries

    def _ems_record_entries(self, mobility, prefix, shared_paths):
        """The record of one participant in one mobility, in the four categories: the call's
        documents that apply (every version uploaded), the commitment letter signed in EMS, the
        weekly self-assessments, the project's documents about them and their transfer receipts.
        In a project export a document shared with others is referenced from the index (its path
        in the common folder), not copied again."""
        self.ensure_one()
        participant = mobility.partner_id.name
        entries = self._ems_line_entries(mobility._ems_record_lines(), prefix)
        entries += self._ems_commitment_entries(mobility, prefix)
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
        return self._ems_archived(mobility, entries)

    def _ems_line_entries(self, lines, prefix):
        """The documents of the engine (`ems.erasmus.application.document`) under `prefix`, each in its
        category: every version uploaded, or one index line when it has no file (missing, not
        applicable, or confidential outside an audit export)."""
        entries = []
        for line in lines:
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
        return entries

    def _ems_commitment_entries(self, record, prefix):
        """The commitment letter accepted in EMS (`ems.erasmus.commitment`), with its earlier versions."""
        if not (record.commitment_signed_date or record.commitment_guardian_signed_date
                or record.commitment_version_ids):
            return []
        signed = record.commitment_signed_date or record.commitment_guardian_signed_date
        return [{
            'path': f"{prefix}02_Abans_de_la_mobilitat/{safe_name(_('Commitment letter'))}.html",
            'content': self._ems_commitment_html(record), 'category': '02_Abans_de_la_mobilitat',
            'document': _("Commitment letter"), 'required': True,
            'status': _("Signed in EMS") if signed else _("Earlier version only: the new one is not accepted yet"),
            'date': signed and self._ems_local(signed) or '',
            'author': (record.commitment_signed_by_id or record.commitment_guardian_signed_by_id).name or ''}]

    # --- group mobilities -----------------------------------------------------------------------

    @api.model
    def _ems_group_folder(self, group):
        return safe_name(f"GRUP{group.id:05d}_{group.name}")

    def _ems_group_entries(self, group, prefix):
        """A group mobility: its common documents once (00_Documentacio_comuna: the shared documents,
        the selection, the follow-up and the EU Survey), then each active participant's record in the
        four categories, which references the shared documents instead of copying them. Conduct and
        fewer-opportunities data only in an audit export."""
        self.ensure_one()
        common = f"{prefix}{COMMON_FOLDER}/"
        label = f"GRUP{group.id:05d}"
        entries = self._ems_line_entries(group.document_ids, common)
        shared = [entry for entry in entries if entry.get('path')]
        entries += self._ems_group_selection_entries(group, common)
        for log in group.log_ids.sorted(lambda log: (log.date, log.id)):
            folder = f"{common}03_Durant_la_mobilitat/{safe_name(_('Follow-up'))}/{log.date}_{safe_name(log.name)}"
            for entry in self._ems_files(folder, log.attachment_ids, versions=False):
                entries.append({**entry, 'category': '03_Durant_la_mobilitat', 'document': log.name,
                                'status': _("Complete")})
        if group.log_ids:
            entries.append(self._ems_csv_entry(
                f"{common}03_Durant_la_mobilitat/{safe_name(_('Follow-up'))}.csv", '03_Durant_la_mobilitat',
                _("Follow-up"), [_("Date"), _("Kind"), _("Summary"), _("Details"), _("Participants"), _("Written by")],
                [[log.date, dict(log._fields['kind']._description_selection(self.env)).get(log.kind), log.name,
                  log.description or '', ", ".join(log.participant_ids.partner_id.mapped('name')), log.author_id.name]
                 for log in group.log_ids.sorted(lambda log: (log.date, log.id))]))
        for entry in self._ems_files(f"{common}04_Despres_de_la_mobilitat/{safe_name(_('EU Survey'))}",
                                     group.eu_survey_attachment_ids, versions=False):
            entries.append({**entry, 'category': '04_Despres_de_la_mobilitat', 'document': _("EU Survey"),
                            'status': dict(group._fields['eu_survey_state']._description_selection(self.env)).get(
                                group.eu_survey_state)})
        for entry in entries:
            entry.setdefault('participant', group.name)
            entry.setdefault('mobility', label)
        everyone = group.with_context(active_test=False).participant_ids
        participants = everyone.filtered(lambda participant: participant.state == 'active').sorted(
            lambda participant: (participant.role != 'student', participant.partner_id.name or ''))
        for participant in participants:
            entries += self._ems_group_participant_entries(participant, prefix, shared, label)
        withdrawn = everyone - participants
        kept = withdrawn and withdrawn.search([('id', 'in', withdrawn.ids)] + self._ems_signed_domain())
        for participant in kept:
            entries += self._ems_cancelled(participant, self._ems_group_participant_entries(
                participant, f"{prefix}{CANCELLED_FOLDER}/", shared, label))
        entries += [self._ems_excluded(participant, participant.partner_id.name, label)
                    for participant in withdrawn - kept]
        return self._ems_archived(group, entries)

    def _ems_group_participant_entries(self, participant, prefix, shared, label):
        """One participant's record in a group mobility, referencing the group's shared documents."""
        kind = 'ALU' if participant.role == 'student' else 'PROF'
        folder = f"{prefix}{safe_name(f'{kind}{participant.id:05d}_{participant.partner_id.name}')}/"
        records = self._ems_line_entries(participant.document_ids, folder)
        records += self._ems_commitment_entries(participant, folder)
        records += [{'path': '', 'category': entry['category'], 'document': entry['document'],
                     'status': entry['status'], 'notes': _("Shared document: %s", entry['path'])}
                    for entry in shared]
        for entry in records:
            entry.setdefault('participant', participant.partner_id.name)
            entry.setdefault('mobility', label)
        return self._ems_archived(participant, records)

    def _ems_group_selection_entries(self, group, common):
        """The selection's evidence (the frozen ranking, the results, renouncements and substitutions,
        and every draw), as two spreadsheets with the participants' data. The fewer opportunities,
        the conduct warnings and the reason for an exclusion only in an audit export."""
        registrations = group.registration_ids.sorted(lambda registration: (
            registration.state != 'enrolled', registration.rank or 999999, registration.partner_id.name or ''))
        if not registrations:
            return []
        Registration = registrations.browse()
        labels = {name: dict(Registration._fields[name]._description_selection(self.env))
                  for name in ('state', 'result', 'proposed_result', 'result_override', 'exclusion',
                               'fewer_opportunities_check')}
        audit = self.include_confidential
        header = [_("Rank"), _("Student"), _("Group at closing"), _("Enrolment"), _("Record average"),
                  _("Average entered by hand"), _("Where the average comes from"), _("Meets the requirements"),
                  _("Draw"), _("Proposed"), _("Exception"), _("Reason for the exception"), _("Result"),
                  _("Renounced on"), _("Replaces")]
        if audit:
            header += [_("Fewer opportunities accredited"), _("Conduct warnings this course"), _("Reason not eligible")]
        rows = []
        for registration in registrations:
            row = [registration.rank or '', registration.partner_id.name, registration.frozen_group_id.display_name or '',
                   labels['state'].get(registration.state, ''), registration._ems_average() if registration.has_average
                   else '', _("Yes") if registration.grade_manual else '', registration.grade_manual_reason or '',
                   _("Yes") if registration.eligible else _("No"), registration.draw_order or '',
                   labels['proposed_result'].get(registration.proposed_result, ''),
                   labels['result_override'].get(registration.result_override, ''), registration.override_reason or '',
                   labels['result'].get(registration.result, ''),
                   registration.renounce_date and self._ems_local(registration.renounce_date) or '',
                   registration.substitute_for_id.partner_id.name or '']
            if audit:
                row += [labels['fewer_opportunities_check'].get(registration.fewer_opportunities_check, '')
                        if registration.fewer_opportunities else '', registration.strike_count,
                        labels['exclusion'].get(registration.exclusion, '')]
            rows.append(row)
        folder = f"{common}01_Dades_i_autoritzacions"
        entries = [self._ems_csv_entry(f"{folder}/{safe_name(_('Selection'))}.csv", '01_Dades_i_autoritzacions',
                                       _("Selection"), header, rows)]
        if group.draw_ids:
            draw_header = [_("Run on"), _("Run by"), _("Tied on the average"), _("Position"), _("Student")]
            if audit:
                draw_header.append(_("Fewer opportunities accredited"))
            draw_rows = [[self._ems_local(draw.date), draw.user_id.name, draw.grade_average, line.position,
                          line.partner_id.name, *([_("Yes") if draw.fewer_opportunities else _("No")] if audit else [])]
                         for draw in group.draw_ids.sorted('date') for line in draw.line_ids]
            entries.append(self._ems_csv_entry(f"{folder}/{safe_name(_('Draws'))}.csv", '01_Dades_i_autoritzacions',
                                               _("Draws"), draw_header, draw_rows))
        return entries

    @api.model
    def _ems_csv_entry(self, path, category, document, header, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(rows)
        return {'path': path, 'content': ('\ufeff' + buffer.getvalue()).encode(), 'category': category,
                'document': document, 'status': _("Complete")}

    @api.model
    def _ems_group_missing(self, group):
        """Required documents of a group mobility not complete (common and active participants')."""
        lines = group.document_ids | group.with_context(active_test=False).participant_ids.filtered(
            lambda participant: participant.state == 'active').document_ids
        return len(lines.filtered(lambda line: line.is_required and line.file_state != 'complete'))

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

    def _ems_commitment_html(self, record):
        """The commitment letter as it was signed in EMS, with who signed it, when and from where, and
        every earlier version (each exactly as it was accepted, and why it was replaced)."""
        def signatures(items):
            return Markup('').join(
                Markup('<li>%s: %s, %s (IP %s)</li>') % (label, user.name, self._ems_local(date), ip or '-')
                for label, user, date, ip in items if date)
        current = signatures([
            (_("Participant"), record.commitment_signed_by_id, record.commitment_signed_date,
             record.commitment_signed_ip),
            (_("Family"), record.commitment_guardian_signed_by_id, record.commitment_guardian_signed_date,
             record.commitment_guardian_signed_ip)])
        body = Markup('<h1>%s</h1><p>%s</p>') % (_("Commitment letter"), record.display_name)
        if current:
            body += Markup('%s<h2>%s</h2><ul>%s</ul>') % (
                record.commitment_signed_text or Markup(''), _("Signed in EMS"), current)
            if record.commitment_provisional:
                body += Markup('<p><strong>%s</strong></p>') % _(
                    "Accepted provisionally: the destination or the dates were still to be confirmed.")
        for version in record.commitment_version_ids.sorted('number', reverse=True):
            body += Markup('<hr/><h2>%s</h2><p>%s</p>%s<ul>%s</ul>') % (
                _("Earlier version %s", version.number),
                _("Replaced on %(date)s: %(reason)s", date=self._ems_local(version.superseded_date),
                  reason=version.reason or ''),
                version.text or Markup(''),
                signatures([(_("Participant"), version.signed_by_id, version.signed_date, version.signed_ip),
                            (_("Family"), version.guardian_signed_by_id, version.guardian_signed_date,
                             version.guardian_signed_ip)]))
        page = Markup('<!DOCTYPE html><html><head><meta charset="utf-8"/><title>%s</title></head><body>%s'
                      '</body></html>') % (_("Commitment letter"), body)
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
        export.write({'state': 'done', 'file_count': len(hashes), 'missing_count': export._ems_missing_count(),
                      'zip_sha256': digest.hexdigest()})
        target = export.mobility_id or export.group_mobility_id
        if target:
            target.chatter(self._ems_log_message())
        return archive

    def _ems_missing_count(self):
        """Required documents not complete in what was exported."""
        if self.scope == 'record':
            return self.mobility_id.record_missing
        if self.scope == 'group':
            return self._ems_group_missing(self.group_mobility_id)
        return sum(self._ems_project_mobilities(self.project_id).mapped('record_missing')) + sum(
            self._ems_group_missing(group) for group in self._ems_project_group_mobilities(self.project_id))

    def _ems_root_name(self):
        if self.scope == 'record':
            mobility = self.sudo().mobility_id
            return safe_name(f"{self._ems_record_folder(mobility)} - {mobility.call_id.name}")
        if self.scope == 'group':
            group = self.sudo().group_mobility_id
            return safe_name(f"{self._ems_group_folder(group)} - {group.project_id.name}")
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
            'mobility': export.mobility_id.display_name or None,
            'group_mobility': export.group_mobility_id.display_name or None, 'requested_by': export.requester_id.name,
            'requested_on': self._ems_local(export.date), 'audit': export.include_confidential,
            'reason': export.reason or None,
            'files': [{key: entry.get(key) for key in keys} for entry in entries if entry.get('path')],
            'not_complete': [{key: entry.get(key) for key in ('participant', 'category', 'document', 'status')}
                             for entry in entries if not entry.get('path') and entry.get('required')],
            'excluded': [{'record': entry['record'], 'reason': entry['excluded']}
                         for entry in entries if entry.get('excluded')],
        }, ensure_ascii=False, indent=1, default=str)

    def _ems_log_message(self):
        message = _("Documents exported (%(files)s files) by %(user)s.", files=self.file_count,
                    user=self.requester_id.name)
        if self.include_confidential:
            message += ' ' + _("Audit export with the confidential documents: %s", self.reason)
        return escape(message)
