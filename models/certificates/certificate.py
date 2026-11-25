# -*- coding: utf-8 -*-

import io
import re

from markupsafe import Markup, escape
from PIL import Image

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date
from odoo.tools.pdf import merge_pdf

from .certificate_type import OPTIONAL_PART, PLACEHOLDER, STEP_ACTIONS

# What a stamp records: a step of the circuit, or - issue #861 - the approver attesting instead of
# the certificate being issued and approved.
STAMP_ACTIONS = STEP_ACTIONS + [('attest', 'Attest')]

# States in which the request is in somebody's hands: a step, or the applicant's answer.
OPEN_STATES = ('in_progress', 'documentation')

# What every applicant fills in, whatever the type, on the portal or through the form link. Each
# type adds its own details (ems.certificate.type.field), stored in ems.certificate.value.
APPLICANT_REQUIRED_FIELDS = ('student_name', 'student_document', 'study_id')

# The column of ems.certificate.value that holds each data type. A company also keeps, in
# value_char and value_vat, the name and VAT number the applicant wrote.
VALUE_COLUMNS = {
    'char': 'value_char',
    'school_year': 'value_char',
    'text': 'value_text',
    'number': 'value_number',
    'date': 'value_date',
    'boolean': 'value_boolean',
    'company': 'value_company_id',
}

# Written only by the circuit's own methods (with sudo).
CIRCUIT_FIELDS = {'state', 'step_id', 'name', 'course_id', 'stamp_ids', 'certificate_pdf_id', 'origin',
                  'applicant_form_open', 'document_kind'}

# A school year as 2024-25 or 2024-2025 (issue #858): stored as 2024-25.
SCHOOL_YEAR = re.compile(r'^(\d{4})\s*[-/]\s*(\d{2}|\d{4})$')

# Files a document appended to the certificate may come as: a PDF, or photos/scans of its pages.
ANNEX_IMAGE_MIMETYPES = ('image/jpeg', 'image/png')


class EmsCertificate(models.Model):
    """Issue #835 - a request for a certificate of the centre, issued through its type's circuit.
    See docs/en/developers/certificates/certificate.md."""
    _name = 'ems.certificate'
    _description = "Certificate request: the centre certifies something about a student."
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'

    name = fields.Char(string="Certificate number", readonly=True, copy=False, index=True,
                       help="CERT-<course>-<number>, the number starting again every course. Given when the "
                            "certificate is issued.")
    type_id = fields.Many2one(string="Certificate type", comodel_name='ems.certificate.type', required=True,
                              ondelete='restrict', default=lambda self: self.env['ems.certificate.type'].search([], limit=1))
    state = fields.Selection(string="State", default='draft', required=True, index=True, copy=False, readonly=True,
                             tracking=True, selection=[
                                 ('draft', "Waiting for the applicant's form"),
                                 ('in_progress', 'In process'),
                                 ('documentation', 'Pending documentation'),
                                 ('issued', 'Issued'),
                                 ('rejected', 'Rejected'),
                                 ('cancelled', 'Cancelled'),
                             ])
    step_id = fields.Many2one(string="Current step", comodel_name='ems.certificate.type.step', readonly=True,
                              copy=False, ondelete='restrict', tracking=True)
    # Issue #861: the Director cannot issue certificates, but may attest ("fer constar"). What the
    # request ends with: a certificate (issued and approved), or an accrediting document (attested by
    # whoever holds the approving step's post, numbered DACR).
    document_kind = fields.Selection(string="Document", default='certificate', required=True, readonly=True,
                                     copy=False, tracking=True, selection=[
                                         ('certificate', 'Certificate'),
                                         ('attestation', 'Accrediting document'),
                                     ])
    step_role_ids = fields.Many2many(string="Pending", related='step_id.role_ids')
    step_action = fields.Selection(related='step_id.action')
    origin = fields.Selection(string="Requested from", readonly=True, default='secretariat', selection=[
        ('portal', 'Portal'),
        ('secretariat', 'Secretariat'),
    ])
    submission_date = fields.Date(string="Request date", readonly=True, copy=False)
    student_id = fields.Many2one(string="Student", comodel_name='res.partner', ondelete='restrict', index=True,
                                 domain=[('contact_type', 'in', ('student', 'alumni', 'withdrawal', 'expelled'))],
                                 help="The student or former student in EMS. A former student who is not in EMS can "
                                      "be left empty: the applicant's details and email are enough.")
    requester_id = fields.Many2one(string="Requested by", comodel_name='res.partner', readonly=True,
                                   ondelete='set null')
    applicant_email = fields.Char(string="Applicant's email",
                                  help="Where the form, the requests for documentation and the certificate are sent "
                                       "when the request was registered by the secretariat (a former student has no "
                                       "portal).")
    course_id = fields.Many2one(string="Issued in course", comodel_name='ems.course', readonly=True, copy=False,
                                ondelete='restrict')

    # The applicant's details.
    student_name = fields.Char(string="Full name")
    student_document = fields.Char(string="Identity document", help="DNI, NIE or passport.")
    study_id = fields.Many2one(string="Study", comodel_name='ems.study', ondelete='restrict')
    type_level_ids = fields.Many2many(related='type_id.level_ids')

    # The details of its type.
    value_ids = fields.One2many(string="Certificate details", comodel_name='ems.certificate.value',
                                inverse_name='certificate_id', copy=False)
    # Issue #861: one model for both, the type's documents (one line each, kept by
    # _ems_sync_documents) and any other document someone attaches, each deciding whether it goes
    # into the certificate.
    document_ids = fields.One2many(string="Documentation", comodel_name='ems.certificate.document',
                                   inverse_name='certificate_id', copy=False,
                                   domain=[('type_document_id', '!=', False)])
    other_document_ids = fields.One2many(string="Other documentation", comodel_name='ems.certificate.document',
                                         inverse_name='certificate_id', copy=False,
                                         domain=[('type_document_id', '=', False)],
                                         help="Any other document anyone taking part attaches. Each one says whether "
                                              "it is added to the certificate.")

    applicant_form_open = fields.Boolean(
        string="The applicant can still edit their details", readonly=True, copy=False,
        help="From the moment the form is sent (or the portal request filed) until someone of the centre changes or "
             "acts on the request: meanwhile the applicant may complete or correct their details and documents "
             "from the link.")

    stamp_ids = fields.One2many(string="Stamps", comodel_name='ems.certificate.stamp', inverse_name='certificate_id',
                                readonly=True, copy=False)
    certificate_pdf_id = fields.Many2one(string="Certificate PDF", comodel_name='ir.attachment', readonly=True,
                                         copy=False, ondelete='set null')
    certificate_pdf_link = fields.Html(string="Certificate", compute='_compute_certificate_pdf_link', sanitize=False)

    info_request = fields.Text(string="Documentation requested", readonly=True, copy=False)
    return_reason = fields.Text(string="Returned", readonly=True, copy=False,
                                help="Why the request was last sent back to the previous step.")
    reject_reason = fields.Text(string="Reason for rejecting", readonly=True, copy=False)
    cancel_reason = fields.Text(string="Reason for cancelling", readonly=True, copy=False)

    step_user_ids = fields.Many2many(string="Pending for", comodel_name='res.users', compute='_compute_step_user_ids',
                                     search='_search_step_user_ids')
    is_pending_for_me = fields.Boolean(string="Pending for me", compute='_compute_is_pending_for_me',
                                       search='_search_is_pending_for_me')
    can_act = fields.Boolean(string="Can do the current step", compute='_compute_is_pending_for_me')
    can_manage = fields.Boolean(string="Can reject or cancel it", compute='_compute_is_pending_for_me',
                                help="The secretariat, and whoever does the current step.")
    is_first_step = fields.Boolean(string="On the first step", compute='_compute_is_first_step')
    can_issue_now = fields.Boolean(string="Can issue it right away", compute='_compute_can_issue_now',
                                   help="Whoever issues the certificate, while the request is still before their "
                                        "step: they may skip the earlier ones when they already have every detail.")
    can_attest = fields.Boolean(string="Can attest it", compute='_compute_can_attest',
                                help="Whoever holds the approving step's post, until the certificate is issued: "
                                     "they may attest it instead, as an accrediting document.")

    # --- computes ------------------------------------------------------------

    def _compute_access_url(self):
        super()._compute_access_url()
        for certificate in self:
            certificate.access_url = f'/my/certificats/{certificate.id}'

    @api.depends('certificate_pdf_id')
    def _compute_certificate_pdf_link(self):
        for certificate in self:
            attachment = certificate.certificate_pdf_id
            certificate.certificate_pdf_link = Markup(
                '<a href="/web/content/{}" target="_blank"><i class="fa fa-file-pdf-o me-1"/>{}</a>'
            ).format(attachment.id, attachment.name) if attachment else False

    @api.depends('step_id', 'stamp_ids')
    def _compute_step_user_ids(self):
        users_by_step = {step: step._ems_users() for step in self.step_id}
        for certificate in self:
            users = users_by_step.get(certificate.step_id, self.env['res.users'])
            certificate.step_user_ids = users - certificate._ems_excluded_approvers()

    def _search_step_user_ids(self, operator, value):
        if operator not in ('=', 'in'):
            raise NotImplementedError(f"Unsupported search on step_user_ids: {operator}")
        user_ids = value if isinstance(value, (list, tuple)) else [value]
        roles = self.env['ems.role'].sudo().search([('employee_ids.user_id', 'in', user_ids)])
        # Issue #861: never the approving step of a certificate they issued themselves.
        return [('step_id.role_ids', 'in', roles.ids),
                '|', ('step_id.action', '!=', 'approve'),
                ('stamp_ids', 'not any', [('action', '=', 'issue'), ('user_id', 'in', user_ids)])]

    def _ems_excluded_approvers(self):
        """Issue #861: a certificate is never issued and approved by the same person. On an approving
        step, whoever issued it is left out of the step, whatever posts they hold."""
        self.ensure_one()
        if self.step_id.action != 'approve':
            return self.env['res.users']
        return self.stamp_ids.filtered(lambda stamp: stamp.action == 'issue').user_id

    @api.depends('state', 'step_id')
    @api.depends_context('uid')
    def _compute_is_pending_for_me(self):
        is_admin = self._ems_is_admin()
        is_secretariat = self._ems_is_secretariat()
        for certificate in self:
            holds_step = self.env.user in certificate.step_user_ids
            mine = certificate.state == 'in_progress' and (is_admin or holds_step) \
                and self.env.user not in certificate._ems_excluded_approvers()
            certificate.is_pending_for_me = mine
            certificate.can_act = mine
            certificate.can_manage = is_secretariat or holds_step

    def _search_is_pending_for_me(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(f"Unsupported search on is_pending_for_me: {operator} {value!r}")
        if self._ems_is_admin():
            # Issue #861: not the approval of a certificate they issued.
            domain = ['&', ('state', '=', 'in_progress'),
                      '|', ('step_id.action', '!=', 'approve'),
                      ('stamp_ids', 'not any', [('action', '=', 'issue'), ('user_id', '=', self.env.uid)])]
        else:
            domain = ['&', ('state', '=', 'in_progress'), ('step_user_ids', '=', self.env.uid)]
        if (operator == '=') == value:
            return domain
        return ['!'] + domain

    @api.depends('step_id', 'type_id.step_ids')
    def _compute_is_first_step(self):
        for certificate in self:
            certificate.is_first_step = certificate.step_id == certificate._ems_steps()[:1]

    @api.depends('state', 'step_id', 'type_id.step_ids')
    @api.depends_context('uid')
    def _compute_can_issue_now(self):
        is_admin = self._ems_is_admin()
        issuers_by_step = {}
        for certificate in self:
            issue_step = certificate._ems_issue_step()
            if certificate.state not in ('draft', 'in_progress') or not issue_step or (
                    certificate.state == 'in_progress' and certificate.step_id.sequence >= issue_step.sequence):
                certificate.can_issue_now = False
                continue
            if issue_step not in issuers_by_step:
                issuers_by_step[issue_step] = issue_step._ems_users()
            certificate.can_issue_now = is_admin or self.env.user in issuers_by_step[issue_step]

    @api.depends('state', 'stamp_ids', 'type_id.step_ids')
    @api.depends_context('uid')
    def _compute_can_attest(self):
        """Issue #861: only whoever really holds the approving step's post (not the administrator by
        being one), while the request is open and not issued yet."""
        attesters_by_type = {}
        for certificate in self:
            certificate_type = certificate.type_id
            if certificate_type not in attesters_by_type:
                attesters_by_type[certificate_type] = certificate._ems_approve_steps()._ems_users()
            certificate.can_attest = certificate.state in ('draft', 'in_progress') \
                and not certificate._ems_is_issued_step_done() \
                and self.env.user in attesters_by_type[certificate_type]

    @api.depends('name', 'student_id', 'student_name', 'type_id')
    def _compute_display_name(self):
        for certificate in self:
            label = f"{certificate.type_id.name or ''} - {certificate._ems_applicant_name()}"
            certificate.display_name = f"{certificate.name} - {label}" if certificate.name else label

    @api.constrains('student_id', 'student_name', 'applicant_email', 'origin')
    def _check_applicant(self):
        """Opening a request for a former student who is not in EMS takes their full name and email:
        the rest they write in the form sent to that email."""
        for certificate in self:
            if not certificate.student_id and not certificate.student_name:
                raise ValidationError(_("Write the full name of the student the certificate is for."))
            if certificate.origin == 'secretariat' and not certificate.student_id and not certificate.applicant_email:
                raise ValidationError(_("Write the email of the former student: the request form is sent there."))

    @api.constrains('type_id', 'study_id')
    def _check_study_level(self):
        """A type for some levels (FCT: CFGM and CFGS) certifies only studies of those levels."""
        for certificate in self:
            levels = certificate.type_id.level_ids
            if levels and certificate.study_id and certificate.study_id.level_id not in levels:
                raise ValidationError(_("%(study)s is not a study of the levels of %(type)s.",
                                        study=certificate.study_id.name, type=certificate.type_id.name))

    # --- CRUD ----------------------------------------------------------------

    def _ems_applicant_name(self):
        """Who the certificate is for: the contact in EMS, or the name written in the request for a
        former student who is not in EMS."""
        self.ensure_one()
        return self.student_id.display_name or self.student_name or self.applicant_email or ''

    @api.onchange('student_id')
    def _onchange_student_id(self):
        """Prefill the applicant's details from the contact: what EMS already knows."""
        for certificate in self.filtered('student_id'):
            certificate.update(certificate._ems_student_defaults(certificate.student_id))

    @api.model
    def _ems_student_defaults(self, student):
        """What EMS knows about the student for the applicant's details and the email: their
        personal one. A legacy contact that still keeps the centre's corporate address there (from
        before issue #514) gets none (issue #858): that account is suspended once they leave."""
        student = student.sudo()
        company = student.company_id or self.env.company
        return {
            'student_name': student.name,
            'student_document': student.document_id,
            'study_id': student.main_group_id.study_id.id,
            'applicant_email': False if company._ems_is_corporate_email(student.email) else student.email,
        }

    @api.model_create_multi
    def create(self, vals_list):
        # Nobody follows a request: the applicant is emailed on the circuit's own terms, and a
        # follower would get every internal note too.
        certificates = super(EmsCertificate, self.with_context(mail_create_nosubscribe=True)).create(vals_list)
        certificates._ems_sync_documents()
        certificates._ems_sync_values()
        return certificates

    def write(self, vals):
        if not self.env.su:
            if CIRCUIT_FIELDS & set(vals):
                raise UserError(_("The state of a certificate request only changes through its buttons."))
            if self.filtered(lambda certificate: certificate.state not in ('draft',) + OPEN_STATES):
                raise UserError(_("A certificate request that is closed cannot be changed."))
            self._ems_close_applicant_form()
        res = super().write(vals)
        if 'type_id' in vals:
            self._ems_sync_documents()
            self._ems_sync_values()
        return res

    def _ems_check_documentation_open(self):
        """Documents are attached, renamed or removed while the request is open; doing it closes the
        applicant's form, as any change of the centre does."""
        for certificate in self:
            if certificate.state not in ('draft',) + OPEN_STATES:
                raise UserError(_("A certificate request that is closed cannot be changed."))
        self._ems_close_applicant_form()

    def _ems_close_applicant_form(self):
        """Someone of the centre changes or acts on a request already in its circuit: from then on
        the applicant only follows it, they can no longer edit their form."""
        opened = self.filtered(lambda certificate: certificate.applicant_form_open and certificate.state != 'draft')
        if opened:
            super(EmsCertificate, opened.sudo()).write({'applicant_form_open': False})

    def _ems_sync_documents(self):
        """One line per document of the type, to attach it to."""
        self._ems_sync_lines('document_ids', 'type_document_id',
                             lambda certificate: certificate.type_id._ems_documents())

    def _ems_sync_values(self):
        """One value line per detail of the type."""
        self._ems_sync_lines('value_ids', 'field_id', lambda certificate: certificate.type_id.field_ids)

    def _ems_sync_lines(self, lines_field, link_field, needed_by):
        """Keep one line of `lines_field` per record `needed_by(certificate)` returns, linked by
        `link_field`. A request whose type changes (only possible before it is submitted) loses the
        previous type's lines and gets the new type's."""
        lines = self[lines_field]
        to_create = []
        stale = lines.browse()
        for certificate in self:
            needed = needed_by(certificate)
            current = certificate[lines_field]
            stale |= current.filtered(lambda line: line[link_field] not in needed)
            to_create += [{'certificate_id': certificate.id, link_field: record.id}
                          for record in needed - current[link_field]]
        stale.sudo().unlink()
        lines.sudo().create(to_create)

    def _ems_details_by_field(self):
        """Each detail of the request (ems.certificate.type.field) with the values it holds."""
        self.ensure_one()
        return {line.field_id: {'value_char': line.value_char, 'value_date': line.value_date}
                for line in self.value_ids}

    def _ems_check_details(self):
        """Raise if a detail is not valid (_ems_detail_errors): when it is written, and before any
        step, for a value written before the check existed."""
        Value = self.env['ems.certificate.value']
        for certificate in self:
            errors = Value._ems_detail_errors(certificate._ems_details_by_field())
            if errors:
                raise ValidationError("\n".join(errors))

    def _ems_portal_detail_errors(self, details, certificate_type=None):
        """What is wrong in the details of a submitted form ({key: column values}, as
        _ems_parse_portal_form gives them), together with those the request already holds."""
        certificate_type = certificate_type or self.type_id
        by_field = self._ems_details_by_field() if self else {}
        by_key = {field.key: field for field in certificate_type.field_ids}
        for key, values in details.items():
            if key in by_key:
                by_field[by_key[key]] = {**by_field.get(by_key[key], {}), **values}
        return self.env['ems.certificate.value']._ems_detail_errors(by_field)

    def _ems_set_values(self, values_by_key):
        """Write details by their key: {key: value}, the value in its type's column; a company's
        value may be a dict of columns (e.g. the name and VAT number the applicant wrote)."""
        for certificate in self:
            for line in certificate.value_ids:
                if line.field_id.key in values_by_key:
                    value = values_by_key[line.field_id.key]
                    line.sudo().write(value if isinstance(value, dict) else {line._ems_column(): value})

    # --- who may do what -----------------------------------------------------

    def _ems_is_admin(self):
        """The administrator is above every position (developer, 2026-10-07): may do any step."""
        return self.env.su or self.env.user.has_group('ems.group_academic_admin')

    def _ems_is_secretariat(self):
        return self._ems_is_admin() or self.env.user.has_group('ems.group_secretary')

    def _ems_check_secretariat(self):
        if not self._ems_is_secretariat():
            raise AccessError(_("Only the secretariat can do this."))

    def _ems_check_can_act(self):
        for certificate in self:
            if not certificate.can_act:
                raise AccessError(_("The current step of %(request)s is not yours: it is for %(position)s.",
                                    request=certificate.display_name, position=certificate.step_id._ems_roles_label() or '-'))

    def _ems_check_state(self, expected):
        labels = dict(self._fields['state']._description_selection(self.env))
        for certificate in self:
            if certificate.state not in expected:
                raise UserError(_("This request cannot be processed in its current state (%s).",
                                  labels[certificate.state]))

    # --- the circuit ---------------------------------------------------------

    def _ems_steps(self):
        self.ensure_one()
        return self.type_id.step_ids.sorted('sequence')

    def _ems_next_step(self):
        steps = self._ems_steps()
        index = list(steps).index(self.step_id)
        return steps[index + 1] if index + 1 < len(steps) else steps.browse()

    def _ems_previous_step(self):
        steps = self._ems_steps()
        index = list(steps).index(self.step_id)
        return steps[index - 1] if index else steps.browse()

    def _ems_issue_step(self):
        self.ensure_one()
        return self._ems_steps().filtered(lambda step: step.action == 'issue')[:1]

    def _ems_approve_steps(self):
        self.ensure_one()
        return self._ems_steps().filtered(lambda step: step.action == 'approve')

    def _ems_is_issued_step_done(self):
        """Whether the certificate already has its number and the issuer's stamp."""
        self.ensure_one()
        return bool(self.stamp_ids.filtered(lambda stamp: stamp.action == 'issue'))

    def _ems_missing_applicant_data(self):
        """The labels of what the applicant must fill in and is still empty: the common details and
        the type's required ones."""
        self.ensure_one()
        labels = self.fields_get(APPLICANT_REQUIRED_FIELDS, ['string'])
        missing = [labels[name]['string'] for name in APPLICANT_REQUIRED_FIELDS if not self[name]]
        required = self.value_ids.filtered(lambda line: line.field_id.applicant_input == 'required')
        return missing + required.filtered(lambda line: not line._ems_has_value()).mapped('name')

    def _ems_check_applicant_data(self):
        for certificate in self:
            missing = certificate._ems_missing_applicant_data()
            if missing:
                raise UserError(_("Fill in the applicant's details first: %s.", ", ".join(missing)))

    def _ems_check_step_data(self, action=None):
        """What the current step (or the step doing `action`) needs before it is done: the
        applicant's details always; the details and documents the type requires by that step or an
        earlier one (issue #861: documents by step too, as details)."""
        self._ems_check_applicant_data()
        self._ems_check_details()
        for certificate in self:
            # Attesting (issue #861) closes the request: whatever any step requires.
            step = certificate._ems_issue_step() if action == 'issue' \
                else certificate._ems_steps()[-1:] if action == 'attest' else certificate.step_id
            missing = certificate.value_ids.filtered(
                lambda line: line.field_id._ems_is_required_by(step) and not line._ems_has_value(linked=True))
            if missing:
                raise UserError(_("Fill in the certificate details first: %s.", ", ".join(missing.mapped('name'))))
            missing_documents = certificate.document_ids.filtered(
                lambda line: line.type_document_id._ems_is_required_by(step) and not line.attachment_ids)
            if missing_documents:
                raise UserError(_("Attach the required documentation first: %s.",
                                  ", ".join(missing_documents.mapped('name'))))

    def _ems_submit(self):
        """The applicant's form is in: the request enters its circuit, on the first step."""
        self._ems_check_applicant_data()
        for certificate in self:
            first = certificate._ems_steps()[:1]
            if not first:
                raise UserError(_("The certificate type %s has no approval circuit.", certificate.type_id.name))
            certificate.sudo().write({
                'state': 'in_progress', 'step_id': first.id,
                'submission_date': fields.Date.context_today(certificate),
            })
            certificate._ems_post_note(_("Request submitted: it is now with %s.", first._ems_roles_label()))
        self._ems_schedule_task()

    def action_done_step(self):
        """The current step is done: its stamp is recorded (the issuing step also gives the
        certificate its number) and the request moves on - or, after the last step, the PDF is
        generated and sent to the applicant."""
        self._ems_check_state(('in_progress',))
        for certificate in self:
            if self.env.user in certificate._ems_excluded_approvers():
                raise UserError(_("You issued %s: someone else has to approve it.", certificate.display_name))
        self._ems_check_can_act()
        self._ems_check_step_data()
        self._ems_close_applicant_form()
        for certificate in self:
            step = certificate.step_id
            vals = certificate._ems_stamp_vals(step, step.action)
            if step.action == 'issue' and not certificate.name:
                vals.update(certificate._ems_number_vals())
            next_step = certificate._ems_next_step()
            vals.update(step_id=next_step.id, return_reason=False)
            certificate._ems_close_tasks()
            certificate.sudo().write(vals)
            certificate._ems_post_note(_("%(step)s: done by %(user)s.", step=step.name, user=self.env.user.name))
            if next_step:
                certificate._ems_schedule_task()
            else:
                certificate._ems_finish()

    def _ems_stamp_vals(self, step, action):
        """The stamp the current user puts on doing `step` (or attesting, issue #861), under their post."""
        self.ensure_one()
        return {'stamp_ids': [(0, 0, {
            'step_id': step.id, 'action': action, 'name': step.name, 'user_id': self.env.user.id,
            'role_id': self._ems_signer_role(step).id, 'date': fields.Date.context_today(self),
        })]}

    def _ems_number_vals(self, attestation=False):
        """The registry number, in the course current today: CERT for a certificate, DACR for an
        accrediting document (issue #861)."""
        course = self.env['ems.course'].search([('is_current', '=', True)], limit=1)
        return {'name': self._ems_next_number(course, attestation=attestation), 'course_id': course.id}

    def _ems_signer_role(self, step):
        """The position the current user does `step` under (issue #858): theirs among the step's;
        else another of theirs in the circuit (e.g. the Director, as administrator, issuing while
        the Secretary is away); else - an administrator with no position - the step's own."""
        self.ensure_one()
        base = self.env['ems.base']
        user = self.env.user
        for roles in (step.role_ids, self._ems_steps().role_ids):
            held = roles.filtered(lambda role: user in base.role_users(role))
            if held:
                return held[:1]
        return step.role_ids[:1]

    def action_preview_draft(self):
        """The certificate as it stands, before it is issued: for the staff only (issue #858)."""
        self.ensure_one()
        return self.env.ref('ems.action_report_certificate_draft').report_action(self)

    def action_preview_attestation(self):
        """Issue #861: the accrediting document as it would be attested now, for its attester."""
        self.ensure_one()
        return self.env.ref('ems.action_report_certificate_draft').with_context(
            ems_attestation_draft=True).report_action(self)

    def action_attest(self):
        """Issue #861: the Director cannot issue certificates, but may attest. Whoever holds the
        approving step's post, once every mandatory detail and document is in, closes the request
        with an accrediting document instead of a certificate: its own DACR number, their only stamp,
        the same text after "attests"."""
        for certificate in self:
            if not certificate.can_attest:
                raise AccessError(_("Only whoever approves %s can attest it, and only before it is issued.",
                                    certificate.display_name))
        self._ems_check_step_data(action='attest')
        self._ems_close_applicant_form()
        today = fields.Date.context_today(self)
        for certificate in self:
            certificate._ems_close_tasks()
            certificate.sudo().write({
                **certificate._ems_stamp_vals(certificate._ems_approve_steps()[-1:], 'attest'),
                **certificate._ems_number_vals(attestation=True),
                'document_kind': 'attestation', 'step_id': False, 'return_reason': False,
                'submission_date': certificate.submission_date or today,
            })
            certificate._ems_post_note(_("%s attests it: an accrediting document is generated instead of the "
                                         "certificate.", self.env.user.name))
            certificate._ems_finish()

    def action_issue_now(self):
        """Whoever issues the certificate already has every detail: the steps before theirs are
        skipped (their tasks closed, a note says who skipped them) and the certificate is issued
        at once, with the same checks as the issuing step always makes."""
        self._ems_check_state(('draft', 'in_progress'))
        for certificate in self:
            if not certificate.can_issue_now:
                raise AccessError(_("Only whoever issues %s can issue it right away, and only before its "
                                    "issuing step.", certificate.display_name))
        # Every mandatory detail and document, before anything moves.
        self._ems_check_step_data(action='issue')
        today = fields.Date.context_today(self)
        for certificate in self:
            issue_step = certificate._ems_issue_step()
            steps = certificate._ems_steps()
            skipped = steps.filtered(lambda step: step.sequence < issue_step.sequence and (
                certificate.state == 'draft' or step.sequence >= certificate.step_id.sequence))
            vals = {'state': 'in_progress', 'step_id': issue_step.id, 'return_reason': False}
            if certificate.state == 'draft':
                vals['submission_date'] = today
            certificate._ems_close_tasks()
            certificate.sudo().write(vals)
            certificate._ems_post_note(_("%(user)s issues the certificate right away, skipping: %(steps)s.",
                                         user=self.env.user.name, steps=", ".join(skipped.mapped('name')) or "-"))
        self.action_done_step()

    @api.model
    def _ems_next_number(self, course, attestation=False):
        """The certificates' registry (CERT), or - issue #861 - the accrediting documents' own (DACR),
        so neither series has gaps."""
        if attestation:
            return self.env['ems.base'].next_course_number('ems.certificate.attestation', "Accrediting documents",
                                                           'DACR', course)
        return self.env['ems.base'].next_course_number('ems.certificate', "Certificates", 'CERT', course)

    def _ems_is_attestation(self):
        self.ensure_one()
        return self.document_kind == 'attestation'

    def _ems_finish(self):
        """After the last step (or attesting): the final PDF, the request closed and the applicant told."""
        self.ensure_one()
        self._ems_generate_pdf()
        self.sudo().write({'state': 'issued'})
        template = 'ems.email_template_certificate_attested' if self._ems_is_attestation() \
            else 'ems.email_template_certificate_issued'
        self._ems_send(template, attachments=self.certificate_pdf_id)

    def _ems_return(self, reason):
        """Back to the previous step, saying why: its stamp is undone, it has to be done again.
        The certificate keeps its number if it already had one."""
        self._ems_check_state(('in_progress',))
        self._ems_check_can_act()
        self._ems_close_applicant_form()
        for certificate in self:
            previous = certificate._ems_previous_step()
            if not previous:
                raise UserError(_("The request is on its first step: there is no step to return it to."))
            certificate._ems_close_tasks()
            certificate.stamp_ids.filtered(lambda stamp: stamp.step_id == previous).sudo().unlink()
            certificate.sudo().write({'step_id': previous.id, 'return_reason': reason})
            certificate._ems_schedule_task()
            certificate._ems_post_note(Markup("<p>{}</p><p>{}</p>").format(
                _("Returned to \"%s\" by %s:", previous.name, self.env.user.name), reason))

    def _ems_request_documentation(self, message):
        """Ask the applicant for more documentation: by email with the form's link, where they
        answer and attach it. The request waits for them."""
        self._ems_check_state(('in_progress',))
        self._ems_check_can_act()
        self._ems_close_applicant_form()
        self._ems_close_tasks()
        self.sudo().write({'state': 'documentation', 'info_request': message})
        for certificate in self:
            certificate._ems_send('ems.email_template_certificate_info_request')

    def action_documentation_received(self):
        """The documentation arrived some other way (on paper, by email): back to the step."""
        self._ems_check_state(('documentation',))
        self._ems_check_secretariat_or_step()
        self._ems_resume(_("Documentation received: the request is back in process."))

    def _ems_check_secretariat_or_step(self):
        for certificate in self:
            if not certificate.can_manage:
                raise AccessError(_("Only the secretariat or whoever does the current step can do this."))

    def _ems_resume(self, note):
        self.sudo().write({'state': 'in_progress'})
        self._ems_schedule_task()
        for certificate in self:
            certificate._ems_post_note(note)

    def _ems_reject(self, reason):
        """Refuse the request, saying why: the applicant is told."""
        self._ems_check_state(OPEN_STATES)
        self._ems_check_secretariat_or_step()
        self._ems_close_tasks()
        self.sudo().write({'state': 'rejected', 'reject_reason': reason, 'applicant_form_open': False})
        for certificate in self:
            certificate._ems_send('ems.email_template_certificate_rejected')

    def _ems_is_cancellable(self):
        """Until the certificate is issued: afterwards it has a number of the registry."""
        self.ensure_one()
        return self.state == 'draft' or (self.state in OPEN_STATES and not self._ems_is_issued_step_done())

    def _ems_cancel(self, reason=False):
        self._ems_check_secretariat_or_step()
        for certificate in self:
            if not certificate._ems_is_cancellable():
                raise UserError(_("An issued certificate cannot be cancelled: reject it instead."))
        self._ems_close_tasks()
        self.sudo().write({'state': 'cancelled', 'cancel_reason': reason, 'applicant_form_open': False})
        body = _("Request cancelled by %s.", self.env.user.name)
        for certificate in self:
            certificate._ems_post_note(Markup("<p>{}</p><p>{}</p>").format(body, reason) if reason else body)

    def action_reopen(self):
        self._ems_check_state(('cancelled',))
        self._ems_check_secretariat()
        for certificate in self:
            if certificate.submission_date:
                certificate.sudo().write({'state': 'in_progress', 'step_id': certificate._ems_steps()[:1].id,
                                          'cancel_reason': False})
                certificate._ems_schedule_task()
            else:
                certificate.sudo().write({'state': 'draft', 'cancel_reason': False})
            certificate._ems_post_note(_("Request reopened by %s.", self.env.user.name))

    def action_open_wizard(self):
        """Request documentation, return, reject or cancel: a dialog asks for the text first."""
        self.ensure_one()
        mode = self.env.context.get('certificate_wizard_mode')
        titles = {
            'info': _("Request documentation"),
            'return': _("Return to the previous step"),
            'reject': _("Reject request"),
            'cancel': _("Cancel request"),
        }
        return {
            'type': 'ir.actions.act_window',
            'name': titles[mode],
            'res_model': 'ems.certificate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_certificate_id': self.id, 'default_mode': mode},
        }

    # --- former students: the form by link -------------------------------------

    def action_send_form(self):
        """Email a former student the link to the request form (portal.mixin's access token):
        they fill in their details there, no login needed. When the secretariat already wrote every
        mandatory detail, the request also starts its circuit right away: the first step works on it
        while the applicant may still complete or correct it from the link, until the centre
        changes or acts on it (applicant_form_open)."""
        self._ems_check_state(('draft',))
        self._ems_check_secretariat()
        for certificate in self:
            if not certificate.applicant_email:
                raise UserError(_("Fill in the applicant's email first."))
        self.sudo().write({'applicant_form_open': True})
        for certificate in self:
            certificate._ems_send('ems.email_template_certificate_form')
        self.filtered(lambda certificate: certificate._ems_applicant_data_complete())._ems_submit()

    def _ems_applicant_data_complete(self):
        self.ensure_one()
        return not self._ems_missing_applicant_data()

    def action_submit(self):
        """The secretariat fills in the details itself (e.g. a request on paper) and starts the
        circuit without sending the form."""
        self._ems_check_state(('draft',))
        self._ems_check_secretariat()
        self._ems_submit()

    def _ems_form_url(self):
        self.ensure_one()
        return f"{self.get_base_url()}{self.get_portal_url()}"

    # --- tasks and messages ----------------------------------------------------

    def _ems_schedule_task(self):
        """The current step's task, for whoever holds one of its positions. Quietly: they find it in
        their daily summary (developer, 2026-10-31), not in an email of its own."""
        base = self.env['ems.base']
        for certificate in self.filtered(lambda certificate: certificate.state == 'in_progress' and certificate.step_id):
            step = certificate.step_id
            users = step._ems_users() - certificate._ems_excluded_approvers()
            for user in base.task_users(users, step._ems_roles_label()):
                certificate.sudo().with_context(mail_activity_quick_update=True).activity_schedule(
                    act_type_xmlid='ems.mail_activity_certificate_step',
                    summary=_("%(step)s: %(student)s", step=step.name, student=certificate._ems_applicant_name()),
                    user_id=user.id,
                )

    def _ems_close_tasks(self):
        task_type = self.env.ref('ems.mail_activity_certificate_step')
        self.sudo().activity_ids.filtered(lambda activity: activity.activity_type_id == task_type).unlink()

    def _ems_post_note(self, body):
        """An internal note for the staff: nobody follows a request, so it notifies nobody."""
        self.ensure_one()
        self.sudo().with_context(mail_create_nosubscribe=True).message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_note')

    def _ems_recipients(self):
        """Who is emailed about the request: the email the secretariat wrote down for a request it
        registered (a former student), else the student and whoever is kept informed about them."""
        self.ensure_one()
        if self.origin == 'secretariat' and self.applicant_email:
            # A former student who is not in EMS: the centre language.
            return [(self.applicant_email, self.student_id.lang or self.env.company.sudo().ems_lang)]
        recipients = self.student_id.sudo()._ems_informed_recipients().filtered('email')
        return [(recipient.email, recipient.lang or self.student_id.lang) for recipient in recipients]

    def _ems_send(self, template_xmlid, attachments=None):
        """Email the applicant with a template, and say so in the chatter."""
        self.ensure_one()
        template = self.env.ref(template_xmlid)
        recipients = self._ems_recipients()
        for email, lang in recipients:
            email_values = {'email_to': email}
            if attachments:
                email_values['attachment_ids'] = [(4, attachment.id) for attachment in attachments]
            template.with_context(lang=lang or self.env.lang).sudo().send_mail(
                self.id, force_send=False, email_values=email_values)
        if recipients:
            self._ems_post_note(_("%(email)s sent to %(to)s.", email=template.sudo().name,
                                  to=", ".join(email for email, _lang in recipients)))
        else:
            self._ems_post_note(_("%s could not be sent: the applicant has no email address.", template.sudo().name))

    # --- the PDF -------------------------------------------------------------

    def _ems_report_paragraphs(self, draft=False, attestation=None):
        """The certificate's text, one translatable sentence each so every language keeps its own
        word order, in the environment's language (the report renders in the centre's). A `draft`
        (issue #858), before it is issued, names whoever holds the issuing step's post, marks every
        detail still empty with its label and is dated today. An accrediting document (issue #861,
        `attestation`, by default the request's own kind) is said by its attester: "attests" instead
        of "certifies", and its own closing sentence."""
        self.ensure_one()
        env = self.env
        if attestation is None:
            attestation = self._ems_is_attestation()

        def sentence(template, **values):
            bold = {key: Markup('<strong>{}</strong>').format(value or '') for key, value in values.items()}
            return Markup(escape(template)) % bold

        signer_action = 'attest' if attestation else 'issue'
        issue = self._ems_stamps_to_print().filtered(lambda stamp: stamp.action == signer_action)[:1]
        issuer, role, date = issue.user_id, issue.role_id, issue.date
        if draft and not issue:
            if attestation:
                # Whoever previews it is who would attest it, under their post among the approving steps'.
                role = self._ems_signer_role(self._ems_approve_steps()[-1:])
                issuer = env.user if env.user in env['ems.base'].role_users(role) \
                    else env['ems.base'].role_users(role)[:1]
            else:
                role = self._ems_issue_step().role_ids[:1]
                issuer = env['ems.base'].role_users(role)[:1]
            date = fields.Date.context_today(self)
        position = role.with_env(env).name
        # Issue #858: the issuer's real position; a stamp from before it was recorded says secretary.
        first = sentence(env._("%(name)s, %(position)s of %(centre)s,"), name=issuer.name,
                         position=self._ems_position_in_sentence(position), centre=env.company.name) \
            if position else sentence(env._("%(secretary)s, secretary of %(centre)s,"),
                                      secretary=issuer.name, centre=env.company.name)
        paragraphs = [
            first,
            Markup('<strong>{}</strong>').format(env._("ATTESTS:") if attestation else env._("CERTIFIES:")),
        ]
        missing = dict(self.type_id.with_env(env)._ems_text_key_labels()) if draft else None
        paragraphs += self._ems_render_text(self.type_id.with_env(env).certificate_text,
                                            self.with_env(env)._ems_placeholder_values(), missing)
        paragraphs.append(Markup(escape(env._(
            "And for the record, I sign this accrediting document at the request of the person concerned.")
            if attestation else env._(
            "And for the record, I issue this certificate at the request of the person concerned."))))
        city = env.company.city
        date = format_date(env, date)
        paragraphs.append(Markup(escape(f"{city}, {date}" if city else date)))
        return paragraphs

    @api.model
    def _ems_position_in_sentence(self, name):
        """A position inside a sentence: its first letter in lowercase (Director/a -> director/a),
        unless it starts with an acronym (FP coordinator)."""
        if not name or (len(name) > 1 and name[1].isupper()):
            return name or ''
        return name[0].lower() + name[1:]

    def _ems_placeholder_values(self):
        """What each key of the text prints: the common details and the type's, as displayed in the
        environment's language."""
        self.ensure_one()
        values = {'name': self.student_name, 'document': self.student_document, 'study': self.study_id.name}
        for line in self.value_ids:
            values[line.field_id.key] = line.display_value
            if line.field_type == 'company':
                values[f'{line.field_id.key}_vat'] = line.value_company_id.vat or line.value_vat
        return values

    @api.model
    def _ems_render_text(self, text, values, missing=None):
        """The certificate text as paragraphs of escaped HTML: each {key} replaced by its value in
        bold, each [optional part] kept only when every key inside it has a value. A blank line
        separates paragraphs. `missing` ({key: label}, a draft's) marks an empty value by its label."""
        def fill(part):
            pieces, position = [], 0
            for match in PLACEHOLDER.finditer(part):
                pieces.append(escape(part[position:match.start()]))
                value = values.get(match[1])
                if not value and missing and match[1] in missing:
                    pieces.append(Markup('<strong class="o_ems_certificate_missing">[{}]</strong>').format(
                        missing[match[1]]))
                else:
                    pieces.append(Markup('<strong>{}</strong>').format(value or ''))
                position = match.end()
            pieces.append(escape(part[position:]))
            return Markup('').join(pieces)

        def paragraph(block):
            pieces, position = [], 0
            for match in OPTIONAL_PART.finditer(block):
                pieces.append(fill(block[position:match.start()]))
                if all(values.get(key) for key in PLACEHOLDER.findall(match[1])):
                    pieces.append(fill(match[1]))
                position = match.end()
            pieces.append(fill(block[position:]))
            return Markup('').join(pieces)

        blocks = [' '.join(block.split()) for block in re.split(r'\n\s*\n', (text or '').strip())]
        return [paragraph(block) for block in blocks if block]

    def _ems_stamps_to_print(self):
        """The stamps the certificate carries: who issued it and who approved it, or who attested it."""
        self.ensure_one()
        return self.stamp_ids.filtered(lambda stamp: stamp.action in ('issue', 'approve', 'attest')).sorted('id')

    def _ems_report_signatures(self, draft=False, attestation=None):
        """The certificate's signature boxes: each stamp to print, and - a `draft` (issue #858) - one
        per issuing or approving step still to be done, headed by its post and left empty. An
        accrediting document's draft (issue #861) has one box: its attester's."""
        self.ensure_one()
        if attestation is None:
            attestation = self._ems_is_attestation()
        stamps = self._ems_stamps_to_print()
        signatures = [{'stamp': stamp, 'role': stamp.role_id, 'action': stamp.action} for stamp in stamps]
        if draft and attestation:
            if not stamps:
                role = self._ems_signer_role(self._ems_approve_steps()[-1:])
                signatures = [{'stamp': False, 'role': role, 'action': 'attest'}]
        elif draft:
            signatures += [{'stamp': False, 'role': step.role_ids[:1], 'action': step.action}
                           for step in self._ems_steps()
                           if step.action in ('issue', 'approve') and step not in stamps.step_id]
        return signatures

    def _ems_generate_pdf(self):
        """Render the certificate and append the pages of every document marked to be added to it
        (the type's and, issue #861, any other one), images included; keep it on the request,
        replacing any earlier one."""
        self.ensure_one()
        centre_env = self.env['res.company']._ems_centre_env()
        pdf, _content_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.action_report_certificate', self.ids)
        documents = self.sudo().document_ids | self.sudo().other_document_ids
        appended = documents.filtered('append_to_certificate').sorted(lambda line: (line.sequence, line.id))
        pages = [pdf] + [self._ems_annex_pdf(attachment) for attachment in appended.attachment_ids]
        previous = self.certificate_pdf_id
        self.sudo().certificate_pdf_id = self.env['ir.attachment'].sudo().create({
            'name': centre_env._("Accrediting document %s.pdf", self.name) if self._ems_is_attestation()
            else centre_env._("Certificate %s.pdf", self.name),
            'raw': merge_pdf([page for page in pages if page]),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })
        previous.sudo().unlink()

    @api.model
    def _ems_annex_pdf(self, attachment):
        """A document's file as PDF pages: a PDF as it is, an image as one page."""
        if attachment.mimetype == 'application/pdf':
            return attachment.raw
        if attachment.mimetype in ANNEX_IMAGE_MIMETYPES:
            image = Image.open(io.BytesIO(attachment.raw)).convert('RGB')
            output = io.BytesIO()
            image.save(output, format='PDF', resolution=150.0)
            return output.getvalue()
        return False

    # --- portal --------------------------------------------------------------

    @api.model
    def _ems_portal_types(self, student):
        """The certificate types the student may request from the portal: those of their level."""
        level = student.sudo().main_group_id.study_id.level_id or student.sudo().main_group_id.level_id
        if not level:
            return self.env['ems.certificate.type']
        return self.env['ems.certificate.type'].sudo().search([('level_ids', 'in', level.ids)])

    @api.model
    def _ems_parse_portal_form(self, post, certificate_type=None):
        """The applicant's form: the common details as field values, and the type's details as
        {key: column values} (_ems_set_values). Text as written, numbers and dates parsed; an
        unknown study (or one outside the type's levels), a wrong number or date left out. Returns
        (values, details, missing required labels)."""
        certificate_type = certificate_type or self.type_id
        values = {name: (post.get(name) or '').strip()[:200] or False for name in ('student_name', 'student_document')}
        study = post.get('study_id')
        study = self.env['ems.study'].sudo().browse(int(study)).exists() if study and study.isdigit() else False
        levels = certificate_type.level_ids
        values['study_id'] = study.id if study and (not levels or study.level_id in levels) else False
        labels = self.fields_get(APPLICANT_REQUIRED_FIELDS, ['string'])
        missing = [labels[name]['string'] for name in APPLICANT_REQUIRED_FIELDS if not values[name]]
        details = {}
        Value = self.env['ems.certificate.value']
        for field in certificate_type._ems_applicant_fields():
            details[field.key] = column_values = Value._ems_parse_input(field, post)
            if field.applicant_input == 'required' and field.field_type != 'boolean' \
                    and not column_values[Value._ems_input_column(field.field_type)]:
                missing.append(field.name)
        return values, details, missing

    def _ems_portal_documents(self):
        """The documents of the type the applicant may attach."""
        self.ensure_one()
        return self.document_ids.filtered('type_document_id.applicant_uploads')

    def _ems_portal_attach(self, files):
        """Store the files the applicant uploaded. `files` maps a document of the type
        (ems.certificate.type.document id) to its files, and None to other documents: each of those
        becomes a document of its own, named after its file, not added to the certificate unless the
        centre ticks it (issue #861). A document the applicant may not attach is ignored."""
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        Document = self.env['ems.certificate.document'].sudo()
        lines = {line.type_document_id.id: line for line in self._ems_portal_documents()}
        attached = Attachment
        for document_id, uploads in files.items():
            if document_id and document_id not in lines:
                continue
            for upload in uploads:
                line = lines.get(document_id) or Document.create({
                    'certificate_id': self.id, 'other_name': upload.filename})
                attachment = Attachment.create({'name': upload.filename, 'raw': upload.read(),
                                                'res_model': line._name, 'res_id': line.id})
                line.attachment_ids = [(4, attachment.id)]
                attached |= attachment
        return attached

    def _ems_portal_can_edit(self):
        """Whether the applicant's form is still open: before the request starts, or afterwards
        until the centre changes or acts on it."""
        self.ensure_one()
        return self.state == 'draft' or (self.state == 'in_progress' and self.applicant_form_open)

    def _ems_portal_fill(self, values, details, files):
        """The form submitted from the token link: the details and the files. A request still
        waiting for it starts its circuit; one already in it (the form left open) is only
        updated, and the staff are told in the chatter."""
        self.ensure_one()
        if not self._ems_portal_can_edit():
            raise UserError(_("A certificate request that is closed cannot be changed."))
        self.sudo().write(values)
        self._ems_set_values(details)
        self._ems_portal_attach(files)
        if self.state == 'draft':
            self.sudo()._ems_submit()
        else:
            self._ems_post_note(_("The applicant updated their details."))

    def _ems_portal_answer(self, message, files):
        """The applicant's answer to a request for documentation: back to the step it was on."""
        self.ensure_one()
        self._ems_check_state(('documentation',))
        attachments = self._ems_portal_attach(files)
        body = Markup("<p>{}</p>{}").format(
            message or _("New documentation attached."),
            self.env['ems.base'].build_html_list(attachments.mapped('name')) if attachments else Markup(""))
        self.sudo()._ems_resume(Markup("<p>{}</p>{}").format(_("Answer from the applicant:"), body))


class EmsCertificateValue(models.Model):
    """A detail of a certificate request, as its type defines it (issue #851): its value, in the
    column of its data type (VALUE_COLUMNS)."""
    _name = 'ems.certificate.value'
    _description = "Detail of a certificate request, with its value."
    _order = 'certificate_id, sequence, id'

    certificate_id = fields.Many2one(string="Certificate request", comodel_name='ems.certificate', required=True,
                                     ondelete='cascade', index=True)
    field_id = fields.Many2one(string="Detail of the type", comodel_name='ems.certificate.type.field', required=True,
                               ondelete='cascade', readonly=True)
    name = fields.Char(related='field_id.name')
    sequence = fields.Integer(related='field_id.sequence')
    field_type = fields.Selection(related='field_id.field_type')
    value_char = fields.Char(string="Text")
    value_text = fields.Text(string="Long text")
    value_number = fields.Float(string="Number")
    value_date = fields.Date(string="Date")
    value_boolean = fields.Boolean(string="Yes/No")
    value_company_id = fields.Many2one(string="Collaborating company", comodel_name='res.partner',
                                       ondelete='restrict',
                                       domain=[('contact_type', '=', 'company'), ('parent_id', '=', False)])
    value_vat = fields.Char(string="VAT number (as written by the applicant)")
    hint = fields.Char(related='field_id.help')
    display_value = fields.Char(string="Value", compute='_compute_display_value')
    is_pending = fields.Boolean(string="Pending", compute='_compute_is_pending',
                                help="Required by now and still empty.")

    @api.depends('field_type', 'value_char', 'value_text', 'value_number', 'value_date', 'value_boolean',
                 'value_company_id')
    @api.depends_context('lang')
    def _compute_display_value(self):
        for line in self:
            if line.field_type == 'company':
                line.display_value = line.value_company_id.name or line.value_char or False
            elif line.field_type == 'date':
                line.display_value = format_date(self.env, line.value_date) if line.value_date else False
            elif line.field_type == 'boolean':
                line.display_value = _("Yes") if line.value_boolean else _("No")
            elif line.field_type == 'number':
                line.display_value = line._ems_format_number() if line.value_number else False
            else:
                line.display_value = line[line._ems_column()] or False

    @api.depends('certificate_id.state', 'certificate_id.step_id', 'field_id', 'value_char', 'value_text',
                 'value_number', 'value_date', 'value_company_id')
    def _compute_is_pending(self):
        for line in self:
            certificate = line.certificate_id
            by_step = certificate.state in OPEN_STATES and line.field_id._ems_is_required_by(certificate.step_id)
            required = by_step or line.field_id.applicant_input == 'required'
            line.is_pending = required and not line._ems_has_value(linked=by_step)

    def _ems_format_number(self):
        """400 as "400", 7.45 as "7,45" in Catalan: up to two decimals, no trailing zeros, the
        decimal separator of the language."""
        text = f'{self.value_number:.2f}'.rstrip('0').rstrip('.')
        return text.replace('.', self.env['res.lang']._lang_get(self.env.lang or 'en_US').decimal_point)

    @api.constrains('value_number')
    def _check_value_number(self):
        if any(line.value_number < 0 for line in self):
            raise ValidationError(_("A number of a certificate cannot be negative."))

    @api.constrains('value_char', 'value_date')
    def _check_values(self):
        self.certificate_id._ems_check_details()

    @api.model
    def _ems_normalize_school_year(self, text):
        """2024-25 for "2024-25" or "2024-2025"; None when it is not a school year (the second year
        must follow the first)."""
        match = SCHOOL_YEAR.match((text or '').strip())
        if not match:
            return None
        first, second = int(match[1]), match[2]
        following = first + 1
        if int(second) != (following if len(second) == 4 else following % 100):
            return None
        return f'{first}-{following % 100:02d}'

    @api.model
    def _ems_detail_errors(self, values_by_field):
        """What is wrong in a request's details, as messages: `values_by_field` maps each detail of
        the type (ems.certificate.type.field) to its column values. One check for the backend and
        the portal (issue #858)."""
        errors = []
        dates = {}
        for field, values in values_by_field.items():
            if field.field_type == 'school_year' and values.get('value_char') \
                    and not self._ems_normalize_school_year(values['value_char']):
                errors.append(_("%(detail)s: write the school year as 2024-25.", detail=field.name))
            elif field.field_type == 'date':
                dates[field] = values.get('value_date')
        for field, value in dates.items():
            earliest = dates.get(field.after_field_id)
            if value and earliest and value < earliest:
                errors.append(_("%(detail)s cannot be earlier than %(earlier)s.", detail=field.name,
                                earlier=field.after_field_id.name))
        return errors

    def write(self, vals):
        if not self.env.su:
            if self.certificate_id.filtered(lambda certificate: certificate.state not in ('draft',) + OPEN_STATES):
                raise UserError(_("A certificate request that is closed cannot be changed."))
            self.certificate_id._ems_close_applicant_form()
        if vals.get('value_char') and self and all(line.field_type == 'school_year' for line in self):
            vals = dict(vals, value_char=self._ems_normalize_school_year(vals['value_char']) or vals['value_char'])
        return super().write(vals)

    def _ems_column(self):
        self.ensure_one()
        return VALUE_COLUMNS[self.field_type]

    @api.model
    def _ems_input_column(self, field_type):
        """Where the applicant's answer goes: a company's name, as written, in value_char."""
        return 'value_char' if field_type == 'company' else VALUE_COLUMNS[field_type]

    def _ems_has_value(self, linked=False):
        """Whether it is filled in. A yes/no always is. A company counts as filled in by the name
        the applicant wrote, or - `linked` - only once its contact is linked."""
        self.ensure_one()
        if self.field_type == 'boolean':
            return True
        if self.field_type == 'company':
            return bool(self.value_company_id or (not linked and self.value_char))
        return bool(self[self._ems_column()])

    @api.model
    def _ems_parse_input(self, field, post):
        """The applicant's answer for `field` from the posted form (input field_<id>, and
        field_<id>_vat for a company), as column values: text as written, a wrong number or date
        left out."""
        name = f'field_{field.id}'
        raw = (post.get(name) or '').strip()
        if field.field_type == 'company':
            return {'value_char': raw[:200] or False, 'value_vat': (post.get(f'{name}_vat') or '').strip()[:30] or False}
        if field.field_type == 'number':
            try:
                number = float(raw.replace(',', '.'))
            except ValueError:
                number = 0
            return {'value_number': number if 0 < number < float('inf') else 0}
        if field.field_type == 'date':
            try:
                return {'value_date': fields.Date.to_date(raw) if raw else False}
            except ValueError:
                return {'value_date': False}
        if field.field_type == 'boolean':
            return {'value_boolean': bool(raw)}
        limit = 2000 if field.field_type == 'text' else 200
        return {VALUE_COLUMNS[field.field_type]: raw[:limit] or False}

    def action_create_company(self):
        """Create the collaborating company from what the applicant wrote (or find the one with
        that VAT number), and link it."""
        self.ensure_one()
        if not self.value_char:
            raise UserError(_("The applicant did not write the company's name."))
        Partner = self.env['res.partner']
        company = Partner.search([('contact_type', '=', 'company'), ('vat', '=', self.value_vat)], limit=1) \
            if self.value_vat else Partner
        if not company:
            company = Partner.create({'name': self.value_char, 'vat': self.value_vat or False,
                                      'is_company': True, 'contact_type': 'company'})
        self.value_company_id = company


class EmsCertificateDocument(models.Model):
    """A document of a certificate request, with its files: one of its type's (the applicant may
    attach it when the type says so; whoever takes part always may), or any other one someone
    attaches (issue #861: with its own name, and its own choice of going into the certificate)."""
    _name = 'ems.certificate.document'
    _inherit = ['ems.attachment_link_mixin']
    _description = "Document of a certificate request, with its files."
    _order = 'certificate_id, sequence, id'

    certificate_id = fields.Many2one(string="Certificate request", comodel_name='ems.certificate', required=True,
                                     ondelete='cascade', index=True)
    type_document_id = fields.Many2one(string="Document of the type", comodel_name='ems.certificate.type.document',
                                       ondelete='cascade', readonly=True, index=True)
    other_name = fields.Char(string="Name of the document")
    name = fields.Char(string="Document", compute='_compute_name')
    sequence = fields.Integer(string="Sequence", compute='_compute_sequence', store=True)
    append_to_certificate = fields.Boolean(
        string="Add to the certificate", compute='_compute_append_to_certificate', store=True, readonly=False,
        help="Its pages are appended to the certificate's PDF (a PDF as it is, each image as a page).")
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_certificate_document_attachment_rel', column1='document_id',
                                      column2='attachment_id')
    uploaders = fields.Char(string="Attached by", compute='_compute_uploaders')
    required_step_id = fields.Many2one(related='type_document_id.required_step_id', string="Required before")
    is_required = fields.Boolean(string="Required", compute='_compute_is_required')
    is_attached = fields.Boolean(string="Attached", compute='_compute_is_attached')
    can_upload = fields.Boolean(string="Can attach it", compute='_compute_can_upload')

    @api.depends('type_document_id.name', 'other_name')
    def _compute_name(self):
        for line in self:
            line.name = line.type_document_id.name or line.other_name

    @api.depends('type_document_id.sequence')
    def _compute_sequence(self):
        # Another document goes after the type's.
        for line in self:
            line.sequence = line.type_document_id.sequence if line.type_document_id else 10000

    @api.depends('type_document_id.append_to_certificate')
    def _compute_append_to_certificate(self):
        # Another document keeps its own choice, not added unless someone ticks it.
        for line in self:
            line.append_to_certificate = line.type_document_id.append_to_certificate if line.type_document_id \
                else line.append_to_certificate

    @api.depends('type_document_id.applicant_uploads')
    def _compute_uploaders(self):
        for line in self:
            line.uploaders = _("Applicant or centre") if line.type_document_id.applicant_uploads else _("Centre") \
                if line.type_document_id else False

    @api.depends('type_document_id.required_step_id')
    def _compute_is_required(self):
        for line in self:
            line.is_required = bool(line.type_document_id.required_step_id)

    @api.depends('attachment_ids')
    def _compute_is_attached(self):
        for line in self:
            line.is_attached = bool(line.attachment_ids)

    @api.depends('certificate_id.state')
    def _compute_can_upload(self):
        # Whoever takes part in the circuit (the staff who can read the request); the applicant
        # attaches from the portal, under its own checks.
        for line in self:
            line.can_upload = line.certificate_id.state in ('draft',) + OPEN_STATES

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            if any(vals.get('type_document_id') for vals in vals_list):
                raise UserError(_("The documents of the type are added by EMS."))
            self.env['ems.certificate'].browse([vals.get('certificate_id') for vals in vals_list]) \
                ._ems_check_documentation_open()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            other_fields = {'attachment_ids', 'other_name', 'append_to_certificate'}
            if set(vals) - ({'attachment_ids'} if self.type_document_id else other_fields):
                raise UserError(_("Only the files of a document of the type can be changed."))
            self.certificate_id._ems_check_documentation_open()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            if self.filtered('type_document_id'):
                raise UserError(_("A document of the type cannot be removed: attach its files instead."))
            self.certificate_id._ems_check_documentation_open()
        return super().unlink()


class EmsCertificateStamp(models.Model):
    """A finished step of a certificate's circuit: who did it and when. Those of the steps that
    issue and approve are printed on the certificate (ems.report_validation_stamp)."""
    _name = 'ems.certificate.stamp'
    _description = "Stamp of a certificate: a step done, by whom and when."
    _order = 'certificate_id, id'

    certificate_id = fields.Many2one(string="Certificate", comodel_name='ems.certificate', required=True,
                                     ondelete='cascade', index=True)
    step_id = fields.Many2one(string="Step", comodel_name='ems.certificate.type.step', ondelete='set null')
    name = fields.Char(string="Step name", required=True)
    action = fields.Selection(string="Action", selection=STAMP_ACTIONS, required=True)
    user_id = fields.Many2one(string="Done by", comodel_name='res.users', required=True, ondelete='restrict')
    role_id = fields.Many2one(string="Post", comodel_name='ems.role', ondelete='set null',
                              help="The post the step was done under: the certificate names the signer by it.")
    date = fields.Date(string="Date", required=True)


class EmsCertificatePartner(models.Model):
    _inherit = 'res.partner'

    # The contact form hides its details block, and locks the name, from whoever is not admin,
    # Secretary, Head of Studies or the contact's tutor (read_only_user), meant for the students'
    # data; the VET coordinator maintains the collaborating companies (issue #835).
    can_edit_company = fields.Boolean(string="Can edit the collaborating company",
                                      compute='_compute_can_edit_company')

    @api.depends('contact_type')
    @api.depends_context('uid')
    def _compute_can_edit_company(self):
        is_coordinator = self.env.user.has_group('ems.group_vet_coordinator')
        for partner in self:
            partner.can_edit_company = is_coordinator and partner.contact_type == 'company'

    def _ems_certificate_portal_visible(self):
        """Whether the portal shows this partner the Certificates page for the student he is
        looking at: a current student of a level that may request a certificate, to whoever may
        file requests for him (the same rule as convalidations), and to the student himself, who
        at least reads his own."""
        self.ensure_one()
        student = self.get_portal_student()
        return student.contact_type == 'student' \
            and (student == self or self._ems_can_file_requests_for(student)) \
            and bool(self.env['ems.certificate']._ems_portal_types(student))


class ReportEmsCertificateDraft(models.AbstractModel):
    """The draft certificate (issue #858): for the staff only, never for the applicant, even one who
    knows the report's URL and can read the request from the portal."""
    _name = 'report.ems.report_certificate_draft'
    _description = "Draft certificate, for the staff."

    @api.model
    def _get_report_values(self, docids, data=None):
        if not self.env.su and not self.env.user._is_internal():
            raise AccessError(_("Only the centre's staff can see a draft certificate."))
        docs = self.env['ems.certificate'].browse(docids)
        docs.check_access('read')
        # Issue #861: the accrediting document's draft, for whoever would attest it.
        return {'doc_ids': docids, 'doc_model': 'ems.certificate', 'docs': docs,
                'attestation': bool(self.env.context.get('ems_attestation_draft'))}
