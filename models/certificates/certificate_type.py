# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# What each step of a circuit does. 'complete' fills in data and hands it over; 'issue' gives the
# certificate its number and the "Issued" stamp; 'approve' adds an "Approved" stamp. Whichever is
# last finishes the request: the PDF is generated and sent.
STEP_ACTIONS = [
    ('complete', 'Complete'),
    ('issue', 'Issue'),
    ('approve', 'Approve'),
]

# What a certificate says, and so which data it needs and which report body prints it.
CERTIFICATE_KINDS = [
    ('fct', 'Workplace training (FCT)'),
]


class EmsCertificateType(models.Model):
    """A kind of certificate the centre issues, with its own approval circuit (issue #835).

    Not a base_tier_validation (OCA) tier definition: tiers only approve or reject a record in a
    given state, while a certificate circuit has steps where someone completes the data before
    approving, works with portal and token applicants, and leaves stamps on the PDF. A few fields
    here reuse what EMS already has instead: the positions (ems.role) to route the tasks, the
    daily summary to deliver them."""
    _name = 'ems.certificate.type'
    _description = "Certificate type: what a certificate says and the steps that issue it."
    _order = 'sequence, name'

    name = fields.Char(string="Name", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    kind = fields.Selection(string="Kind", selection=CERTIFICATE_KINDS, required=True, default='fct',
                            help="What the certificate says, and so which data the request asks for.")
    description = fields.Text(string="Description", translate=True,
                              help="Shown to the applicant on the request form.")
    level_ids = fields.Many2many(string="Levels that may request it", comodel_name='ems.level',
                                 help="Current students of these levels may request it from the portal. Leave it "
                                      "empty to register its requests from the backend only.")
    requires_annex = fields.Boolean(string="Agreement required", default=True,
                                    help="The agreement (PDF or images) must be attached before the certificate is "
                                         "issued. Its pages are appended to the certificate.")
    step_ids = fields.One2many(string="Approval circuit", comodel_name='ems.certificate.type.step',
                               inverse_name='type_id', copy=True)

    @api.constrains('step_ids')
    def _check_steps(self):
        """At least one step, exactly one that issues the certificate, and every approval after it:
        an approval stamps a certificate that already has its number."""
        for certificate_type in self:
            steps = certificate_type.step_ids.sorted('sequence')
            actions = steps.mapped('action')
            if actions.count('issue') != 1:
                raise ValidationError(_("The approval circuit of %s needs exactly one step that issues the "
                                        "certificate.", certificate_type.name))
            if 'approve' in actions[:actions.index('issue')]:
                raise ValidationError(_("In the approval circuit of %s, approvals go after the step that issues "
                                        "the certificate.", certificate_type.name))


class EmsCertificateTypeStep(models.Model):
    _name = 'ems.certificate.type.step'
    _description = "Step of a certificate's approval circuit: who does what."
    _order = 'type_id, sequence, id'

    type_id = fields.Many2one(string="Certificate type", comodel_name='ems.certificate.type', required=True,
                              ondelete='cascade', index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True, translate=True)
    role_id = fields.Many2one(string="Position", comodel_name='ems.role', required=True, ondelete='restrict',
                              help="Whoever holds this position gets the task and does the step. The "
                                   "administrator can always do it too.")
    action = fields.Selection(string="Action", selection=STEP_ACTIONS, required=True, default='complete')
