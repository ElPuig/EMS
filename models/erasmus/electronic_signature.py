# -*- coding: utf-8 -*-
"""Electronic signature of a participant's documents with OCA's sign_oca: a call document links the
template of its SEPIE model (where each signer signs), the Erasmus team sends the filled-in PDF to
sign, every signer signs from a link (no EMS account needed), each signature ticks its line and the
signed PDF becomes the document's file. See docs/en/developers/erasmus/records.md."""

import base64
import os

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .document_review import SIGNERS

# The states of a signature request in which the document is still out for signing.
OPEN_SIGN_STATES = ('1_draft', '0_sent')


class SignOcaRole(models.Model):
    """The Erasmus+ signer each role stands for: the template's boxes say who signs where."""
    _inherit = 'sign.oca.role'
    _sql_constraints = [
        ('ems_signer_unique', 'unique(ems_signer)', "Each Erasmus+ signer has one role."),
    ]

    # Translatable, so the team reads the Erasmus+ roles in its own language when placing the boxes.
    name = fields.Char(translate=True)
    ems_signer = fields.Selection(string="Erasmus+ signer", selection=SIGNERS)


class EmsErasmusCallDocument(models.Model):
    _inherit = 'ems.erasmus.call.document'

    sign_template_id = fields.Many2one(
        string="Signature template", comodel_name='sign.oca.template', ondelete='restrict',
        help="Signed in EMS: the SEPIE model (a copy already filled in) with the place of each signer's signature. "
             "The Erasmus team sends every filled-in copy to sign from the participant's record. Empty: signed "
             "outside EMS and uploaded.")


class EmsErasmusDocumentSignature(models.Model):
    _inherit = 'ems.erasmus.document.signature'

    sign_signer_id = fields.Many2one(string="Signed electronically", comodel_name='sign.oca.request.signer',
                                     readonly=True, ondelete='set null',
                                     help="Ticked by the electronic signature, not by the team.")

    def write(self, vals):
        """A signature made electronically is the signer's, never unticked by the team."""
        if not self.env.su and 'signed' in vals and not vals['signed'] and self.filtered('sign_signer_id'):
            raise UserError(_("A signature made electronically can't be unticked."))
        return super().write(vals)


class EmsErasmusApplicationDocument(models.Model):
    _inherit = 'ems.erasmus.application.document'

    sign_request_id = fields.Many2one(string="Signature request", comodel_name='sign.oca.request', readonly=True,
                                      copy=False, ondelete='set null',
                                      groups='ems.group_erasmus,ems.group_academic_admin')
    sign_state = fields.Selection(string="Electronic signature", related='sign_request_id.state',
                                  groups='ems.group_erasmus,ems.group_academic_admin')
    can_send_to_sign = fields.Boolean(string="Can be sent to sign", compute='_compute_can_send_to_sign')

    @api.depends('call_document_id.sign_template_id', 'review_state', 'signatures_missing',
                 'prepared_attachment_ids', 'attachment_ids')
    def _compute_can_send_to_sign(self):
        for line in self:
            line.can_send_to_sign = bool(line.call_document_id.sign_template_id and line.signatures_missing
                                         and line.review_state != 'valid' and line._ems_sign_source())

    def _ems_sign_source(self):
        """The PDF sent to sign: the newest one the team uploaded or, for a document the
        participant uploads (e.g. the report), the newest of theirs."""
        self.ensure_one()
        pdfs = (self.prepared_attachment_ids or self.attachment_ids).sudo().filtered(
            lambda attachment: attachment.mimetype == 'application/pdf')
        return pdfs.sorted(lambda attachment: (attachment.create_date, attachment.id))[-1:]

    def _ems_signer_partner(self, signer):
        """Who signs as `signer`: the participant, the first family contact of a minor with an email
        (the team can change it before sending), the Director, the Erasmus coordinator, the host
        entity's contact person. The centre's tutor is never found by EMS (only sBID asks for it,
        signed there)."""
        self.ensure_one()
        participant = self.group_participant_id.partner_id if self.group_mobility_id else self.application_id.partner_id
        if signer == 'participant':
            return participant
        if signer == 'guardian':
            return participant and participant._ems_family_contacts().filtered('email')[:1]
        if signer == 'director':
            directors = self.env.ref('ems.group_director').sudo().users.filtered(lambda user: not user.share)
            return (directors - self.env.ref('base.user_root'))[:1].partner_id
        if signer == 'coordinator':
            return self.env['ems.erasmus.group.mobility']._ems_coordinators()[:1].partner_id
        if signer == 'host':
            return (self.group_mobility_id or self.mobility_id).host_contact_id
        return self.env['res.partner']

    def action_send_to_sign(self):
        """Prepare the signature request of this document from its call document's template and
        open it: the team checks where each signer signs and sends it from there. A request still
        open is opened again instead of preparing another one."""
        self.ensure_one()
        # The Erasmus team only (it has Sign's rights), not a group's leader teacher.
        if not self.env['ems.erasmus.application']._ems_can_manage():
            raise AccessError(_("Only the Erasmus team sends documents to sign."))
        line = self.sudo()
        if line.sign_request_id.state in OPEN_SIGN_STATES:
            return line._ems_open_sign_request()
        template = line.call_document_id.sign_template_id
        if not template:
            raise UserError(_("%s has no signature template: it is signed outside EMS.", line.name))
        if line.review_state == 'valid' or line._ems_record_closed():
            raise UserError(_("%s is valid or its record is closed: nothing left to sign.", line.name))
        source = line._ems_sign_source()
        if not source:
            raise UserError(_("Upload the filled-in PDF of %s first.", line.name))
        pending = line.signature_ids.filtered(lambda signature: signature.is_required and not signature.signed)
        if not pending:
            raise UserError(_("Every signature of %s is already there.", line.name))
        roles = {role.ems_signer: role for role in template.item_ids.role_id}
        if unknown := [role.name for signer, role in roles.items() if not signer]:
            raise UserError(_("The template %(template)s has boxes for %(roles)s, which are not Erasmus+ signers.",
                              template=template.name, roles=", ".join(unknown)))
        problems, signers = [], []
        for signature in pending:
            label = signature._ems_label()
            partner = line._ems_signer_partner(signature.signer)
            if signature.signer not in roles:
                problems.append(_("the template has no place for the signature of %s", label))
            elif not partner:
                problems.append(_("no %s found to sign it", label))
            elif not partner.email:
                problems.append(_("%(signer)s (%(name)s) has no email", signer=label, name=partner.name))
            else:
                signers.append((0, 0, {'role_id': roles[signature.signer].id, 'partner_id': partner.id}))
        if problems:
            raise UserError(_("%(document)s can't be sent to sign: %(problems)s.", document=line.name,
                              problems="; ".join(problems)))
        # Only the boxes of whoever still signs: e.g. no legal guardian's for an adult.
        role_ids = {signer[2]['role_id'] for signer in signers}
        items = {key: item for key, item in template._get_signatory_data().items() if item['role_id'] in role_ids}
        request = self.env['sign.oca.request'].sudo().create({
            'name': f"{line._ems_record_label()} - {(line._ems_record_owner() or line.application_id).display_name}",
            'template_id': template.id,
            'record_ref': f"{line._name},{line.id}",
            'data': source.datas,
            'filename': source.name,
            'ask_location': template.ask_location,
            'signatory_data': items,
            'signer_ids': signers,
        })
        line.sign_request_id = request
        (line._ems_record_owner() or line.application_id).chatter(
            _("%s: prepared to sign electronically.", line._ems_record_label()))
        return line._ems_open_sign_request()

    def _ems_open_sign_request(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'sign.oca.request', 'view_mode': 'form',
                'res_id': self.sign_request_id.id, 'views': [(False, 'form')]}

    def _ems_portal_sign_url(self, partner):
        """The link `partner` signs this document with on the portal, while it waits for them."""
        self.ensure_one()
        request = self.sudo().sign_request_id
        signer = request.state == '0_sent' and request.signer_ids.filtered(
            lambda signer: signer.partner_id == partner and not signer.signed_on)[:1]
        return signer and signer.access_url

    def _ems_signed_electronically(self, signer):
        """`signer` (a sign.oca.request.signer) has signed: tick their signature; once everybody
        has, the signed PDF becomes a file of the document, for the team to review it."""
        self.ensure_one()
        line = self.sudo()
        signature = line.signature_ids.filtered(lambda signature: signature.signer == signer.role_id.ems_signer)
        if signature and not signature.signed:
            signature.with_context(ems_signed_electronically=True).write({'signed': True})
            signature.write({'signed_user_id': signer.partner_id.user_ids[:1].id, 'sign_signer_id': signer.id})
        request = signer.request_id
        if request.state == '2_signed':
            stem = os.path.splitext(request.filename or line.name)[0]
            line._ems_add_files([(f"{stem} - {_('signed')}.pdf", base64.b64decode(request.data))])


class SignOcaRequestSigner(models.Model):
    _inherit = 'sign.oca.request.signer'

    def action_sign(self, items, access_token=False, latitude=False, longitude=False):
        result = super().action_sign(items, access_token=access_token, latitude=latitude, longitude=longitude)
        request = self.request_id.sudo()
        if request.record_ref and request.record_ref._name == 'ems.erasmus.application.document':
            request.record_ref._ems_signed_electronically(self.sudo())
        return result
