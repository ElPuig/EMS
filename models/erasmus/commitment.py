# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EmsErasmusCommitment(models.AbstractModel):
    """The commitment letter a participant accepts and signs in EMS from the portal, and, for a
    minor, their family too, from its own portal; in any order. The text is kept exactly as it was
    at the first signature, which is what the second one signs, with who, when and from where.
    Used by the internship mobilities (issue #687, the call's annex 3) and by the students of a
    group mobility (issue #703, a common template with the mobility's data). A model using it
    says what its letter is (`_ems_commitment_letter`), whether a family signs too
    (`_ems_commitment_is_minor`), when it can be signed (`_ems_commitment_open`) and which email
    tells the family (`_ems_commitment_guardian_template`)."""
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

    @api.depends(lambda self: self._ems_commitment_depends())
    def _compute_commitment_pending(self):
        for record in self:
            letter = bool(record.commitment_signed_text) or record._ems_commitment_has_letter()
            record.commitment_pending = letter and not record.commitment_signed_date
            record.commitment_guardian_pending = (letter and record._ems_commitment_is_minor()
                                                  and not record.commitment_guardian_signed_date)

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
