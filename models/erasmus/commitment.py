# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

# The fields of an accepted letter, kept in its version when a new one replaces it.
SIGNATURE_FIELDS = ('commitment_signed_date', 'commitment_signed_by_id', 'commitment_signed_ip',
                    'commitment_guardian_signed_date', 'commitment_guardian_signed_by_id',
                    'commitment_guardian_signed_ip', 'commitment_signed_text')


class EmsErasmusCommitment(models.AbstractModel):
    """The commitment letter a participant accepts and signs in EMS from the portal, and, for a
    minor, their family too, from its own portal; in any order. The text is kept exactly as it was
    at the first signature, which is what the second one signs, with who, when and from where.
    Used by the internship mobilities (issue #687, the call's annex 3) and by the students of a
    group mobility (issue #703, a common template with the mobility's data). A model using it
    says what its letter is (`_ems_commitment_letter`), whether a family signs too
    (`_ems_commitment_is_minor`), when it can be signed (`_ems_commitment_open`) and which email
    tells the family (`_ems_commitment_guardian_template`).

    When the conditions of the letter change after it was accepted (a group mobility's destination,
    dates or teachers), the model calls `_ems_commitment_supersede`: the acceptance is kept, unchanged,
    as an `ems.erasmus.commitment.version`, and the new letter has to be accepted again. A letter
    accepted while its essential data are still to be confirmed (`_ems_commitment_is_final`) is
    provisional: it does not let the participant leave."""
    _name = 'ems.erasmus.commitment'
    _description = 'Erasmus+ commitment letter'

    _ems_commitment_guardian_template = None

    commitment_signed_date = fields.Datetime(string="Commitment letter signed on", readonly=True, copy=False)
    commitment_signed_by_id = fields.Many2one(string="Commitment letter signed by", comodel_name='res.users',
                                              readonly=True, copy=False)
    commitment_signed_ip = fields.Char(string="Signed from IP address", readonly=True, copy=False)
    commitment_signed_text = fields.Html(string="Commitment letter signed", readonly=True, sanitize=True, copy=False,
                                         help="The text accepted, as it was when it was signed.")
    commitment_pending = fields.Boolean(string="Commitment letter pending", compute='_compute_commitment_pending')
    commitment_guardian_signed_date = fields.Datetime(string="Signed by the family on", readonly=True, copy=False)
    commitment_guardian_signed_by_id = fields.Many2one(string="Signed by the family member", comodel_name='res.users',
                                                       readonly=True, copy=False)
    commitment_guardian_signed_ip = fields.Char(string="Family signed from IP address", readonly=True, copy=False)
    commitment_guardian_pending = fields.Boolean(
        string="Family signature pending", compute='_compute_commitment_pending',
        help="A minor student's commitment letter is signed by their family too, on its own portal.")
    commitment_provisional = fields.Boolean(
        string="Accepted provisionally", compute='_compute_commitment_provisional',
        help="Accepted while the destination or the dates were still to be confirmed: once they are, the new letter "
             "has to be accepted again.")
    commitment_version_ids = fields.One2many(string="Earlier versions", comodel_name='ems.erasmus.commitment.version',
                                             compute='_compute_commitment_version_ids',
                                             help="Letters accepted before their conditions changed, kept as they were.")

    @api.depends(lambda self: self._ems_commitment_depends())
    def _compute_commitment_pending(self):
        for record in self:
            letter = bool(record.commitment_signed_text) or record._ems_commitment_has_letter()
            record.commitment_pending = letter and not record.commitment_signed_date
            record.commitment_guardian_pending = (letter and record._ems_commitment_is_minor()
                                                  and not record.commitment_guardian_signed_date)

    @api.depends(lambda self: self._ems_commitment_depends())
    def _compute_commitment_provisional(self):
        for record in self:
            record.commitment_provisional = bool(record.commitment_signed_date or record.commitment_guardian_signed_date) \
                and not record._ems_commitment_is_final()

    def _compute_commitment_version_ids(self):
        versions = self.env['ems.erasmus.commitment.version'].sudo().search(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)])
        for record in self:
            record.commitment_version_ids = versions.filtered(lambda version: version.res_id == record.id)

    def _ems_commitment_depends(self):
        return ['commitment_signed_text', 'commitment_signed_date', 'commitment_guardian_signed_date']

    def _ems_commitment_letter(self):
        """The letter to sign now (HTML), or False when there is none."""
        return False

    def _ems_commitment_has_letter(self):
        """Whether there is a letter to sign, without building it."""
        return bool(self._ems_commitment_letter())

    def _ems_commitment_is_minor(self):
        return False

    def _ems_commitment_is_final(self):
        """Whether the letter has every essential datum confirmed (an acceptance before is provisional)."""
        return True

    def _ems_commitment_open(self):
        """Whether the letter can be signed now (e.g. the mobility is being prepared)."""
        return True

    def _ems_commitment_text(self):
        """The commitment letter to sign: as it was signed first, or the current one."""
        self.ensure_one()
        return self.commitment_signed_text or self._ems_commitment_letter()

    def action_sign_commitment(self, accepted=False, ip_address=False, guardian=False):
        """The participant, or the family of a minor (`guardian`), accepts and signs the commitment
        letter in EMS, from the portal."""
        self.ensure_one()
        prefix = 'commitment_guardian_' if guardian else 'commitment_'
        if not self._ems_commitment_open() or not self[f'{prefix}pending']:
            raise UserError(_("There is no commitment letter to sign."))
        if not accepted:
            raise UserError(_("Tick that you accept the commitments first."))
        self.with_context(ems_erasmus_state=True).sudo().write({
            f'{prefix}signed_date': fields.Datetime.now(), f'{prefix}signed_by_id': self.env.uid,
            f'{prefix}signed_ip': ip_address, 'commitment_signed_text': self._ems_commitment_text()})
        self.sudo().chatter(_("Commitment letter accepted and signed in EMS by the family.") if guardian
                            else _("Commitment letter accepted and signed in EMS."))

    def _ems_commitment_supersede(self, reason, provisional=None):
        """The letter's conditions changed: keep each acceptance as it was (a version nobody can
        change) and ask for the new letter to be accepted again, by the participant and the family.
        `provisional`: whether each acceptance was provisional, read before the change ({record: bool})."""
        Version = self.env['ems.erasmus.commitment.version'].sudo()
        for record in self.sudo().filtered(lambda record: record.commitment_signed_date
                                           or record.commitment_guardian_signed_date):
            Version.create({
                'res_model': record._name, 'res_id': record.id, 'reason': reason,
                'number': Version.search_count([('res_model', '=', record._name), ('res_id', '=', record.id)]) + 1,
                'text': record.commitment_signed_text,
                'provisional': (provisional or {}).get(record.id, record.commitment_provisional),
                'signed_date': record.commitment_signed_date, 'signed_by_id': record.commitment_signed_by_id.id,
                'signed_ip': record.commitment_signed_ip,
                'guardian_signed_date': record.commitment_guardian_signed_date,
                'guardian_signed_by_id': record.commitment_guardian_signed_by_id.id,
                'guardian_signed_ip': record.commitment_guardian_signed_ip,
            })
            record.with_context(ems_erasmus_state=True).write(dict.fromkeys(SIGNATURE_FIELDS, False))
            record.invalidate_recordset(['commitment_version_ids'])
            record.chatter(_("The conditions of the commitment letter changed (%s): the letter accepted is kept as an "
                             "earlier version and the new one has to be accepted again.", reason))
            record._ems_remind_guardians()

    def _ems_commitment_student(self):
        """The student whose family signs."""
        return self.partner_id

    def _ems_remind_guardians(self):
        """Email the family of each minor whose commitment letter it still has to sign."""
        template = self.env.ref(self._ems_commitment_guardian_template)
        for record in self.filtered('commitment_guardian_pending'):
            for family in record._ems_commitment_student()._ems_family_contacts().filtered('email'):
                template.with_context(lang=family.lang).sudo().send_mail(
                    record.id, force_send=False, email_values={'email_to': family.email})


class EmsErasmusCommitmentVersion(models.Model):
    """A commitment letter accepted before its conditions changed, exactly as it was accepted: the
    text, who accepted it (the participant and the family), when and from which IP, and why it was
    replaced. Created by EMS only; never changed nor deleted."""
    _name = 'ems.erasmus.commitment.version'
    _description = 'Erasmus+ commitment letter version'
    _order = 'res_model, res_id, number'

    res_model = fields.Char(string="Model", required=True, readonly=True, index=True)
    res_id = fields.Many2oneReference(string="Record", model_field='res_model', required=True, readonly=True,
                                      index=True)
    number = fields.Integer(string="Version", required=True, readonly=True)
    text = fields.Html(string="Letter accepted", readonly=True, sanitize=True)
    provisional = fields.Boolean(string="Provisional", readonly=True,
                                 help="Accepted while the destination or the dates were still to be confirmed.")
    signed_date = fields.Datetime(string="Accepted on", readonly=True)
    signed_by_id = fields.Many2one(string="Accepted by", comodel_name='res.users', readonly=True, ondelete='restrict')
    signed_ip = fields.Char(string="From IP address", readonly=True)
    guardian_signed_date = fields.Datetime(string="Accepted by the family on", readonly=True)
    guardian_signed_by_id = fields.Many2one(string="Family member", comodel_name='res.users', readonly=True,
                                            ondelete='restrict')
    guardian_signed_ip = fields.Char(string="Family from IP address", readonly=True)
    superseded_date = fields.Datetime(string="Replaced on", readonly=True, default=fields.Datetime.now)
    superseded_by_id = fields.Many2one(string="Replaced by", comodel_name='res.users', readonly=True,
                                       default=lambda self: self.env.user, ondelete='restrict')
    reason = fields.Char(string="Why it was replaced", readonly=True)

    def write(self, vals):
        raise UserError(_("An accepted commitment letter is evidence: it cannot be changed."))

    def unlink(self):
        if not self.env.context.get(MODULE_UNINSTALL_FLAG):
            raise UserError(_("An accepted commitment letter is evidence: it cannot be deleted."))
        return super().unlink()
