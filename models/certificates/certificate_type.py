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
    requires_documents = fields.Boolean(string="Required attached documentation",
                                        help="The documents listed below must be attached before the certificate is "
                                             "issued. Any other document can always be attached as optional.")
    document_ids = fields.One2many(string="Required documents", comodel_name='ems.certificate.type.document',
                                   inverse_name='type_id', copy=True)
    step_ids = fields.One2many(string="Approval circuit", comodel_name='ems.certificate.type.step',
                               inverse_name='type_id', copy=True)
    circuit_role_ids = fields.Many2many(string="Positions of the circuit", comodel_name='ems.role',
                                        compute='_compute_circuit_role_ids')

    @api.depends('step_ids.role_id')
    def _compute_circuit_role_ids(self):
        for certificate_type in self:
            certificate_type.circuit_role_ids = certificate_type.step_ids.role_id

    @api.constrains('requires_documents', 'document_ids')
    def _check_documents(self):
        for certificate_type in self:
            if certificate_type.requires_documents and not certificate_type.document_ids:
                raise ValidationError(_("List the documents %s requires, or untick Required attached documentation.",
                                        certificate_type.name))

    def _ems_required_documents(self):
        """The documents a request of this type must have before it is issued."""
        self.ensure_one()
        return self.document_ids.sorted('sequence') if self.requires_documents else self.document_ids.browse()

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


class EmsCertificateTypeDocument(models.Model):
    """A document a certificate type requires (e.g. the FCT agreement), and who may attach it: the
    applicant, positions of the circuit, or - nobody ticked - anyone taking part."""
    _name = 'ems.certificate.type.document'
    _description = "Document a certificate type requires, and who attaches it."
    _order = 'type_id, sequence, id'

    type_id = fields.Many2one(string="Certificate type", comodel_name='ems.certificate.type', required=True,
                              ondelete='cascade', index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Document", required=True, translate=True)
    applicant_uploads = fields.Boolean(string="Applicant",
                                       help="The applicant may attach it from the portal or the form link.")
    role_ids = fields.Many2many(string="Positions", comodel_name='ems.role',
                                help="Holders of these positions may attach it. With neither the applicant nor any "
                                     "position ticked, anyone taking part may attach it.")
    append_to_certificate = fields.Boolean(string="Add to the certificate", default=True,
                                           help="Its pages are appended to the certificate's PDF (a PDF as it is, "
                                                "each image as a page).")

    def _ems_anyone(self):
        self.ensure_one()
        return not self.applicant_uploads and not self.role_ids

    def _ems_applicant_may_upload(self):
        self.ensure_one()
        return self.applicant_uploads or self._ems_anyone()
