# -*- coding: utf-8 -*-

import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# What each step of a circuit does. 'complete' fills in data and hands it over; 'issue' gives the
# certificate its number and the "Issued" stamp; 'approve' adds an "Approved" stamp. Whichever is
# last finishes the request: the PDF is generated and sent.
STEP_ACTIONS = [
    ('complete', 'Complete the data'),
    ('issue', 'Issue the certificate'),
    ('approve', 'Approve'),
]

# The kinds of data a certificate type may ask for, each stored in its own column of
# ems.certificate.value (VALUE_COLUMNS). A 'company' datum is a collaborating company: the applicant
# writes its name and VAT number, the centre links the contact.
FIELD_TYPES = [
    ('char', 'Short text'),
    ('text', 'Long text'),
    ('integer', 'Number'),
    ('date', 'Date'),
    ('boolean', 'Yes/No'),
    ('school_year', 'School year'),
    ('company', 'Collaborating company'),
]

# The data every request has, whatever its type, and the key its text prints them with.
COMMON_KEYS = ('name', 'document', 'study')

# {key} in a certificate's text, and [...] around a part printed only when its data have a value.
PLACEHOLDER = re.compile(r'\{([a-z][a-z0-9_]*)\}')
OPTIONAL_PART = re.compile(r'\[([^\[\]]*)\]')
KEY_FORMAT = re.compile(r'^[a-z][a-z0-9_]*$')


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
    # Copied by copy(), which points each detail at the copy's own step.
    field_ids = fields.One2many(string="Certificate details", comodel_name='ems.certificate.type.field',
                                inverse_name='type_id', copy=False)
    certificate_text = fields.Text(
        string="Certificate text", translate=True, copy=False,
        help="What the certificate says after \"CERTIFIES:\". Write {key} where a detail goes; a part between "
             "square brackets is printed only when every detail inside it has a value; a blank line starts a new "
             "paragraph.")
    placeholder_help = fields.Html(string="Details the text can use", compute='_compute_placeholder_help',
                                   sanitize=False)
    step_ids = fields.One2many(string="Approval circuit", comodel_name='ems.certificate.type.step',
                               inverse_name='type_id', copy=True)
    circuit_role_ids = fields.Many2many(string="Positions of the circuit", comodel_name='ems.role',
                                        compute='_compute_circuit_role_ids')

    @api.depends('step_ids.role_ids')
    def _compute_circuit_role_ids(self):
        for certificate_type in self:
            certificate_type.circuit_role_ids = certificate_type.step_ids.role_ids

    @api.depends('field_ids.key', 'field_ids.name', 'field_ids.field_type')
    def _compute_placeholder_help(self):
        common = [('name', _("Full name")), ('document', _("Identity document")), ('study', _("Study"))]
        for certificate_type in self:
            keys = list(common)
            for field in certificate_type.field_ids.sorted('sequence').filtered('key'):
                keys.append((field.key, field.name))
                if field.field_type == 'company':
                    keys.append((f'{field.key}_vat', _("%s (VAT number)", field.name)))
            certificate_type.placeholder_help = Markup(", ").join(
                Markup("<code>{{{}}}</code> {}").format(key, label) for key, label in keys)

    def _ems_text_keys(self):
        """The keys the type's text may write between braces."""
        self.ensure_one()
        keys = set(COMMON_KEYS)
        for field in self.field_ids:
            keys.add(field.key)
            if field.field_type == 'company':
                keys.add(f'{field.key}_vat')
        return keys

    @api.constrains('certificate_text', 'field_ids')
    def _check_certificate_text(self):
        """Every language's text uses only the type's keys, and its brackets pair up."""
        languages = self.env['res.lang'].get_installed()
        for certificate_type in self:
            keys = certificate_type._ems_text_keys()
            for lang, language in languages:
                text = certificate_type.with_context(lang=lang).certificate_text or ''
                unknown = set(PLACEHOLDER.findall(text)) - keys
                if unknown:
                    raise ValidationError(_("The text of %(type)s in %(language)s uses details it does not have: "
                                            "%(keys)s.", type=certificate_type.name, language=language,
                                            keys=", ".join(f'{{{key}}}' for key in sorted(unknown))))
                if set('[]') & set(OPTIONAL_PART.sub('', text)):
                    raise ValidationError(_("The text of %(type)s in %(language)s has a square bracket without its "
                                            "pair (or one inside another).", type=certificate_type.name,
                                            language=language))

    def _ems_rename_text_key(self, old_key, new_key, with_vat):
        """A detail's key changed: its text follows in every language at once. Language by language
        through write() would leave the others with the old key in between, and the text check
        would refuse the save (a key renamed from the Catalan form kept {old} in English)."""
        self.ensure_one()
        self.flush_recordset(['certificate_text'])
        self.env.cr.execute("SELECT certificate_text FROM ems_certificate_type WHERE id = %s", [self.id])
        texts = self.env.cr.fetchone()[0] or {}
        suffix = '(_vat)?' if with_vat else '()'
        pattern = re.compile(r'\{' + re.escape(old_key) + suffix + r'\}')
        renamed = {lang: pattern.sub(lambda match: '{' + new_key + (match.group(1) or '') + '}', text)
                   for lang, text in texts.items() if text}
        changed = {lang: text for lang, text in renamed.items() if text != texts[lang]}
        if changed:
            self.update_field_translations('certificate_text', changed)

    @api.constrains('requires_documents', 'document_ids')
    def _check_documents(self):
        for certificate_type in self:
            if certificate_type.requires_documents and not certificate_type.document_ids:
                raise ValidationError(_("List the documents %s requires, or untick Required attached documentation.",
                                        certificate_type.name))

    def copy(self, default=None):
        copies = super().copy(default)
        for certificate_type, new_type in zip(self, copies):
            steps = dict(zip(certificate_type.step_ids.sorted('sequence'), new_type.step_ids.sorted('sequence')))
            for field in certificate_type.field_ids:
                field.copy({'type_id': new_type.id,
                            'required_step_id': steps.get(field.required_step_id, field.required_step_id.browse()).id})
            # The text once its details exist (_check_certificate_text), in every language.
            for lang, _name in self.env['res.lang'].get_installed():
                new_type.with_context(lang=lang).certificate_text = \
                    certificate_type.with_context(lang=lang).certificate_text
        return copies

    def _ems_applicant_fields(self):
        """The details the request form asks the applicant for, in order."""
        self.ensure_one()
        return self.field_ids.filtered(lambda field: field.applicant_input != 'none').sorted('sequence')

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
    role_ids = fields.Many2many(string="Posts", comodel_name='ems.role', relation='ems_certificate_type_step_role_rel',
                                column1='step_id', column2='role_id', required=True,
                                help="Whoever holds any of these positions gets the task and may do the step. The "
                                     "administrator can always do it too.")
    action = fields.Selection(string="Action", selection=STEP_ACTIONS, required=True, default='complete')

    @api.constrains('role_ids')
    def _check_roles(self):
        if self.filtered(lambda step: not step.role_ids):
            raise ValidationError(_("Every step of the approval circuit needs at least one position."))

    def _ems_users(self):
        """The users who hold any position of the step: they get its task and may do it."""
        base = self.env['ems.base']
        users = self.env['res.users']
        for role in self.role_ids:
            users |= base.role_users(role)
        return users

    def _ems_roles_label(self):
        return ", ".join(self.role_ids.mapped('name'))


class EmsCertificateTypeField(models.Model):
    """A detail a certificate type needs besides the common ones (the student's name, identity
    document and study): who fills it in, and by when (issue #851)."""
    _name = 'ems.certificate.type.field'
    _description = "Detail a certificate type needs, and who fills it in."
    _order = 'type_id, sequence, id'
    _sql_constraints = [
        ('key_unique', 'unique(type_id, key)', "Each detail of a certificate type needs its own key."),
    ]

    type_id = fields.Many2one(string="Certificate type", comodel_name='ems.certificate.type', required=True,
                              ondelete='cascade', index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Detail", required=True, translate=True)
    key = fields.Char(string="Key", required=True,
                      help="How the certificate text writes it, between braces: lowercase letters, digits and _.")
    field_type = fields.Selection(string="Data type", selection=FIELD_TYPES, required=True, default='char')
    applicant_input = fields.Selection(string="Applicant", required=True, default='optional', selection=[
        ('required', 'Required'),
        ('optional', 'Optional'),
        ('none', 'Not asked'),
    ], help="Whether the request form asks the applicant for it, and whether they must answer.")
    required_step_id = fields.Many2one(string="Required before", comodel_name='ems.certificate.type.step',
                                       ondelete='restrict',
                                       help="The step that cannot be done until it is filled in (nor any later one). "
                                            "Empty: the circuit never requires it. Save the circuit's steps first.")
    help = fields.Char(string="Hint", translate=True, help="Shown to the applicant under the detail.")

    @api.constrains('key', 'field_type')
    def _check_key(self):
        for field in self:
            if not KEY_FORMAT.match(field.key or ''):
                raise ValidationError(_("The key of %s may only have lowercase letters, digits and _, starting with a "
                                        "letter.", field.name))
            if field.key in COMMON_KEYS or field.key.endswith('_vat'):
                raise ValidationError(_("%(key)s is a key of its own in every certificate: choose another one for "
                                        "%(detail)s.", key=field.key, detail=field.name))

    @api.constrains('required_step_id', 'type_id')
    def _check_required_step(self):
        for field in self:
            if field.required_step_id and field.required_step_id.type_id != field.type_id:
                raise ValidationError(_("%s must be required by a step of its own certificate type.", field.name))

    @api.model_create_multi
    def create(self, vals_list):
        fields_created = super().create(vals_list)
        # Requests still open get the new detail too, to fill it in.
        self.env['ems.certificate'].sudo().search([
            ('type_id', 'in', fields_created.type_id.ids), ('state', 'in', ('draft', 'in_progress', 'documentation')),
        ])._ems_sync_values()
        return fields_created

    def write(self, vals):
        renamed = [(field.type_id, field.key, field.field_type == 'company') for field in self
                   if 'key' in vals and field.key != vals['key']]
        result = super().write(vals)
        for certificate_type, old_key, was_company in renamed:
            certificate_type._ems_rename_text_key(old_key, vals['key'], was_company)
        return result

    def _ems_is_required_by(self, step):
        """Whether a request must have it filled in before `step` is done."""
        self.ensure_one()
        return bool(self.required_step_id) and bool(step) and self.required_step_id.sequence <= step.sequence


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
