# -*- coding: utf-8 -*-
"""What the Erasmus team records while reviewing a document of a participant's record (audit D-1,
D-2): who signed it, ticked per signer, and the reason for removing a file uploaded by mistake. See
docs/en/developers/erasmus/records.md."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .workflow import check_kept

# Who may sign a document outside EMS, as the call document says (its sign_<signer> fields).
SIGNERS = [('participant', "Participant"), ('guardian', "Legal guardian"), ('director', "Director"),
           ('coordinator', "Erasmus coordinator"), ('tutor', "Centre's tutor"), ('host', "Host entity")]
SIGNER_KEYS = [key for key, _label in SIGNERS]
# The signature lines every line of a document someone signs needs, created where they are missing
# (an upgrade of a database whose lines predate them; new lines get them when created).
MISSING_SIGNATURES_SQL = """
    INSERT INTO ems_erasmus_document_signature (line_id, signer, sequence, signed, create_uid, create_date,
                                                write_uid, write_date)
    SELECT line.id, signer.key, signer.sequence, FALSE, 1, now() AT TIME ZONE 'UTC', 1, now() AT TIME ZONE 'UTC'
      FROM ems_erasmus_application_document line
      JOIN ems_erasmus_call_document document ON document.id = line.call_document_id
      JOIN (VALUES {values}) AS signer(key, sequence) ON (
               (signer.key = 'participant' AND document.sign_participant)
            OR (signer.key = 'guardian' AND document.sign_guardian)
            OR (signer.key = 'director' AND document.sign_director)
            OR (signer.key = 'coordinator' AND document.sign_coordinator)
            OR (signer.key = 'tutor' AND document.sign_tutor)
            OR (signer.key = 'host' AND document.sign_host))
     WHERE NOT EXISTS (SELECT 1 FROM ems_erasmus_document_signature existing
                        WHERE existing.line_id = line.id AND existing.signer = signer.key)
"""


class EmsErasmusDocumentSignature(models.Model):
    """Audit D-1 - one signature of a document someone signs outside EMS (the call document's
    signers): the Erasmus team ticks it when it sees it on the uploaded copy, and EMS keeps who ticked
    it and when. It is not an electronic signature, it is the team's check of the scan. A document is
    only valid once every signature that applies is ticked (the legal guardian's, only for a minor)."""
    _name = 'ems.erasmus.document.signature'
    _description = 'Erasmus+ document signature'
    _order = 'line_id, sequence, id'
    _sql_constraints = [
        ('line_signer_unique', 'unique(line_id, signer)', "A document has one signature per signer."),
    ]

    line_id = fields.Many2one(string="Document", comodel_name='ems.erasmus.application.document', required=True,
                              ondelete='cascade', index=True, readonly=True)
    signer = fields.Selection(string="Signer", selection=SIGNERS, required=True, readonly=True)
    sequence = fields.Integer(string="Sequence", readonly=True)
    is_required = fields.Boolean(string="Required", compute='_compute_is_required',
                                 help="The legal guardian signs only for a minor; a signer the call document no "
                                      "longer asks for is kept if it was ticked, not required.")
    signed = fields.Boolean(string="Signed")
    signed_user_id = fields.Many2one(string="Ticked by", comodel_name='res.users', readonly=True)
    signed_date = fields.Datetime(string="Ticked on", readonly=True)

    @api.depends('signer', 'line_id.call_document_id.sign_participant', 'line_id.call_document_id.sign_guardian',
                 'line_id.call_document_id.sign_director', 'line_id.call_document_id.sign_coordinator',
                 'line_id.call_document_id.sign_tutor', 'line_id.call_document_id.sign_host')
    def _compute_is_required(self):
        for signature in self:
            line = signature.line_id
            signature.is_required = line.call_document_id[f'sign_{signature.signer}'] and (
                signature.signer != 'guardian' or line._ems_is_minor())

    def write(self, vals):
        """Only the tick changes, through whoever reviews the document; a ticked signature is only
        unticked while the document is not valid, and nothing changes in a closed record."""
        if not self.env.su:
            if set(vals) - {'signed'}:
                raise AccessError(_("A signature is only ticked or unticked."))
            self.line_id._ems_check_reviewer()
        if 'signed' not in vals:
            return super().write(vals)
        changed = self.filtered(lambda signature: signature.signed != bool(vals['signed']))
        for signature in changed:
            line = signature.line_id
            if line._ems_record_closed() or (not vals['signed'] and line.review_state == 'valid'):
                raise UserError(_("%s is valid or its record is closed: its signatures are kept.", line.name))
        labels = dict(self._fields['signer']._description_selection(self.env))
        result = super(EmsErasmusDocumentSignature, changed.sudo()).write({
            'signed': bool(vals['signed']), 'signed_user_id': vals['signed'] and self.env.uid,
            'signed_date': vals['signed'] and fields.Datetime.now()})
        for signature in changed:
            line = signature.line_id
            owner = line._ems_record_owner() or line.application_id
            if self.env.context.get('ems_signed_electronically'):
                message = _("%(document)s: %(signer)s signed electronically.")
            elif vals['signed']:
                message = _("%(document)s: signature of %(signer)s ticked.")
            else:
                message = _("%(document)s: signature of %(signer)s unticked.")
            owner.sudo().chatter(message % {'document': line._ems_record_label(),
                                            'signer': labels[signature.signer]})
        return result

    def _ems_label(self):
        self.ensure_one()
        return dict(self._fields['signer']._description_selection(self.env)).get(self.signer, '')

    def unlink(self):
        check_kept(self, self.filtered('signed'))
        return super().unlink()

    def init(self):
        self.env.cr.execute(MISSING_SIGNATURES_SQL.format(
            values=", ".join(f"('{key}', {index})" for index, key in enumerate(SIGNER_KEYS, 1))))


class EmsErasmusApplicationDocument(models.Model):
    """The signatures of a document someone signs, and the files it keeps: a file removed from a
    document not valid yet needs a reason (audit D-2)."""
    _inherit = 'ems.erasmus.application.document'

    signature_ids = fields.One2many(string="Signatures", comodel_name='ems.erasmus.document.signature',
                                    inverse_name='line_id',
                                    groups='ems.group_erasmus,ems.group_academic_admin,ems.group_erasmus_group_teacher')
    signatures_missing = fields.Char(string="Signatures missing", compute='_compute_signatures_missing',
                                     help="Signatures the Erasmus team has not ticked yet: the document is valid "
                                          "once every one is ticked.")

    @api.depends('signature_ids.signed', 'signature_ids.is_required')
    def _compute_signatures_missing(self):
        labels = dict(self.env['ems.erasmus.document.signature']._fields['signer']._description_selection(self.env))
        for line in self:
            missing = line.sudo().signature_ids.filtered(lambda signature: signature.is_required and not signature.signed)
            line.signatures_missing = ", ".join(labels[signature.signer] for signature in missing)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._ems_sync_signatures()
        return lines

    def write(self, vals):
        """A file is removed only through `Remove a file`, with a reason (audit D-2), and a document
        someone signs is valid only once every signature that applies is ticked (audit D-1)."""
        files = [name for name in ('attachment_ids', 'prepared_attachment_ids') if name in vals]
        before = {(line, name): line[name] for line in self for name in files} if not self.env.su else {}
        if vals.get('review_state') == 'valid' and (unsigned := self.filtered('signatures_missing')):
            raise UserError(_("Tick the signatures first: %s", "; ".join(
                f"{line.name} ({line.signatures_missing})" for line in unsigned)))
        result = super().write(vals)
        for (line, name), attachments in before.items():
            if attachments - line[name]:
                raise UserError(_("A file of %s is removed with Remove a file, saying why.", line.name))
        return result

    def _ems_sync_signatures(self):
        """One signature per signer the call document asks for; one no longer asked for goes, unless
        it was ticked (then it is kept, not required)."""
        Signature = self.env['ems.erasmus.document.signature'].sudo()
        to_create, to_remove = [], Signature
        for line in self.sudo():
            document = line.call_document_id
            wanted = [key for key in SIGNER_KEYS if document[f'sign_{key}']]
            existing = set(line.signature_ids.mapped('signer'))
            to_create += [{'line_id': line.id, 'signer': key, 'sequence': SIGNER_KEYS.index(key) + 1}
                          for key in wanted if key not in existing]
            to_remove |= line.signature_ids.filtered(lambda signature: signature.signer not in wanted
                                                     and not signature.signed)
        Signature.create(to_create)
        to_remove.unlink()

    def action_open_signatures(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _("Signatures of %s", self.name), 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
            'views': [(self.env.ref('ems.view_erasmus_document_signatures_form').id, 'form')],
        }

    def action_remove_file(self):
        self.ensure_one()
        self._ems_check_reviewer()
        return {
            'type': 'ir.actions.act_window', 'name': _("Remove a file"), 'res_model': 'ems.erasmus.file.removal.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_line_id': self.id},
        }


class EmsErasmusCallDocument(models.Model):
    _inherit = 'ems.erasmus.call.document'

    def write(self, vals):
        result = super().write(vals)
        if any(key.startswith('sign_') for key in vals):
            self.env['ems.erasmus.application.document'].sudo().search(
                [('call_document_id', 'in', self.ids)])._ems_sync_signatures()
        return result


class EmsErasmusFileRemovalWizard(models.TransientModel):
    """Audit D-2 - the reviewer removes a file uploaded by mistake from a document not valid yet,
    saying why: the file is not deleted, it stays attached to the record's history with the reason,
    who removed it and when."""
    _name = 'ems.erasmus.file.removal.wizard'
    _description = 'Erasmus+ remove a file'

    line_id = fields.Many2one(string="Document", comodel_name='ems.erasmus.application.document', required=True,
                              ondelete='cascade')
    file_ids = fields.Many2many(string="Its files", comodel_name='ir.attachment', compute='_compute_file_ids')
    attachment_id = fields.Many2one(string="File", comodel_name='ir.attachment', required=True,
                                    domain="[('id', 'in', file_ids)]", ondelete='cascade')
    reason = fields.Text(string="Reason", required=True, help="Why the file is removed: it stays in the history.")

    @api.depends('line_id')
    def _compute_file_ids(self):
        for wizard in self:
            line = wizard.line_id.sudo()
            wizard.file_ids = line.attachment_ids | line.prepared_attachment_ids

    def action_confirm(self):
        self.ensure_one()
        line = self.line_id
        line._ems_check_reviewer()
        if not (self.reason or '').strip():
            raise UserError(_("Write the reason for removing the file first."))
        line = line.sudo()
        if line.review_state == 'valid' or line._ems_record_closed():
            raise UserError(_("%s is valid or its mobility is closed: its files are kept. Upload a new version "
                              "instead of removing one.", line.name))
        attachment = self.attachment_id.sudo()
        field = next((name for name in ('attachment_ids', 'prepared_attachment_ids') if attachment in line[name]),
                     None)
        if not field:
            raise UserError(_("The file is not one of this document's."))
        line.write({field: [(3, attachment.id)]})
        owner = line._ems_record_owner() or line.application_id
        owner.sudo().message_post(
            body=_("%(document)s: file %(file)s removed by %(user)s: %(reason)s. It is attached here.",
                   document=line._ems_record_label(), file=attachment.name, user=self.env.user.name,
                   reason=self.reason.strip()),
            attachment_ids=attachment.ids, message_type='notification', subtype_xmlid='mail.mt_note')
        return {'type': 'ir.actions.act_window_close'}
