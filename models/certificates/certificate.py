# -*- coding: utf-8 -*-

import io

from markupsafe import Markup, escape
from PIL import Image

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_date
from odoo.tools.pdf import merge_pdf

from .certificate_type import STEP_ACTIONS

# States in which the request is in somebody's hands: a step, or the applicant's answer.
OPEN_STATES = ('in_progress', 'documentation')

# What the applicant fills in, on the portal or through the form link. The student's details are
# mandatory; the company's are optional, since the applicant rarely has them (the agreement they
# keep does not carry the company's VAT number nor the dates): the step that completes the data does.
APPLICANT_REQUIRED_FIELDS = ('student_name', 'student_document', 'study_id', 'fct_school_year')
APPLICANT_OPTIONAL_FIELDS = ('company_name', 'company_vat', 'period_start', 'period_end', 'hours',
                             'agreement_reference')

# What the workplace training needs before the circuit can go past a 'complete' step.
COMPANY_REQUIRED_FIELDS = ('training_company_id', 'period_start', 'period_end', 'hours')

# Written only by the circuit's own methods (with sudo).
CIRCUIT_FIELDS = {'state', 'step_id', 'name', 'course_id', 'stamp_ids', 'certificate_pdf_id', 'origin'}

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
    kind = fields.Selection(related='type_id.kind')
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
    step_role_id = fields.Many2one(string="Pending", related='step_id.role_id')
    step_action = fields.Selection(related='step_id.action')
    origin = fields.Selection(string="Requested from", readonly=True, default='secretariat', selection=[
        ('portal', 'Portal'),
        ('secretariat', 'Secretariat'),
    ])
    submission_date = fields.Date(string="Request date", readonly=True, copy=False)
    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True, ondelete='restrict',
                                 index=True, domain=[('contact_type', 'in', ('student', 'alumni', 'withdrawal'))])
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
    fct_school_year = fields.Char(string="School year of the training", help="E.g. 2024-2025.")

    # The workplace training.
    training_company_id = fields.Many2one(string="Collaborating company", comodel_name='res.partner', ondelete='restrict',
                                 domain=[('contact_type', '=', 'company'), ('parent_id', '=', False)])
    company_name = fields.Char(string="Company (as written by the applicant)")
    company_vat = fields.Char(string="Company VAT number (as written by the applicant)")
    period_start = fields.Date(string="From")
    period_end = fields.Date(string="To")
    hours = fields.Integer(string="Hours")
    agreement_reference = fields.Char(string="Agreement registration number",
                                      help="The registration number of the agreement in sBID (or qBID).")
    document_ids = fields.One2many(string="Required documentation", comodel_name='ems.certificate.document',
                                   inverse_name='certificate_id', copy=False)
    other_attachment_ids = fields.Many2many(string="Other documentation", comodel_name='ir.attachment',
                                            relation='ems_certificate_other_attachment_rel',
                                            column1='certificate_id', column2='attachment_id',
                                            help="Optional documents anyone taking part may attach. They are not "
                                                 "added to the certificate.")

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

    @api.depends('step_id')
    def _compute_step_user_ids(self):
        base = self.env['ems.base']
        users_by_role = {role: base.role_users(role) for role in self.step_id.role_id}
        for certificate in self:
            certificate.step_user_ids = users_by_role.get(certificate.step_id.role_id, self.env['res.users'])

    def _search_step_user_ids(self, operator, value):
        if operator not in ('=', 'in'):
            raise NotImplementedError(f"Unsupported search on step_user_ids: {operator}")
        user_ids = value if isinstance(value, (list, tuple)) else [value]
        roles = self.env['ems.role'].sudo().search([('employee_ids.user_id', 'in', user_ids)])
        return [('step_id.role_id', 'in', roles.ids)]

    @api.depends('state', 'step_id')
    @api.depends_context('uid')
    def _compute_is_pending_for_me(self):
        is_admin = self._ems_is_admin()
        is_secretariat = self._ems_is_secretariat()
        for certificate in self:
            holds_step = self.env.user in certificate.step_user_ids
            mine = certificate.state == 'in_progress' and (is_admin or holds_step)
            certificate.is_pending_for_me = mine
            certificate.can_act = mine
            certificate.can_manage = is_secretariat or holds_step

    def _search_is_pending_for_me(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(f"Unsupported search on is_pending_for_me: {operator} {value!r}")
        domain = [('state', '=', 'in_progress')]
        if not self._ems_is_admin():
            domain.append(('step_user_ids', '=', self.env.uid))
        if (operator == '=') == value:
            return domain
        return ['!', '&'] + domain if len(domain) == 2 else ['!'] + domain

    @api.depends('step_id', 'type_id.step_ids')
    def _compute_is_first_step(self):
        for certificate in self:
            certificate.is_first_step = certificate.step_id == certificate._ems_steps()[:1]

    @api.depends('name', 'student_id', 'type_id')
    def _compute_display_name(self):
        for certificate in self:
            label = f"{certificate.type_id.name or ''} - {certificate.student_id.display_name or ''}"
            certificate.display_name = f"{certificate.name} - {label}" if certificate.name else label

    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        for certificate in self:
            if certificate.period_start and certificate.period_end and certificate.period_end < certificate.period_start:
                raise ValidationError(_("The training cannot end before it starts."))

    @api.constrains('hours')
    def _check_hours(self):
        if any(certificate.hours < 0 for certificate in self):
            raise ValidationError(_("The hours cannot be negative."))

    # --- CRUD ----------------------------------------------------------------

    @api.onchange('student_id')
    def _onchange_student_id(self):
        """Prefill the applicant's details from the contact: what EMS already knows."""
        for certificate in self.filtered('student_id'):
            certificate.update(certificate._ems_student_defaults(certificate.student_id))

    @api.model
    def _ems_student_defaults(self, student):
        """What EMS knows about the student for the applicant's details and the email."""
        student = student.sudo()
        return {
            'student_name': student.name,
            'student_document': student.document_id,
            'study_id': student.main_group_id.study_id.id,
            'applicant_email': student.email,
        }

    @api.model_create_multi
    def create(self, vals_list):
        # Nobody follows a request: the applicant is emailed on the circuit's own terms, and a
        # follower would get every internal note too.
        certificates = super(EmsCertificate, self.with_context(mail_create_nosubscribe=True)).create(vals_list)
        certificates._ems_sync_documents()
        certificates._ems_link_other_attachments()
        return certificates

    def write(self, vals):
        if not self.env.su:
            if CIRCUIT_FIELDS & set(vals):
                raise UserError(_("The state of a certificate request only changes through its buttons."))
            if self.filtered(lambda certificate: certificate.state not in ('draft',) + OPEN_STATES):
                raise UserError(_("A certificate request that is closed cannot be changed."))
        res = super().write(vals)
        if 'type_id' in vals:
            self._ems_sync_documents()
        if 'other_attachment_ids' in vals:
            self._ems_link_other_attachments()
        return res

    def _ems_link_other_attachments(self):
        for certificate in self:
            certificate.other_attachment_ids._ems_link_to(certificate)

    def _ems_sync_documents(self):
        """One line per document the type requires, to attach it to. A request whose type changes
        (only possible before it is submitted) gets the new type's lines."""
        for certificate in self:
            required = certificate.type_id._ems_required_documents()
            lines = certificate.document_ids
            lines.filtered(lambda line: line.type_document_id not in required).sudo().unlink()
            missing = required - lines.type_document_id
            self.env['ems.certificate.document'].sudo().create([{
                'certificate_id': certificate.id, 'type_document_id': document.id,
            } for document in missing])

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
                                    request=certificate.display_name, position=certificate.step_role_id.name or '-'))

    def _ems_check_state(self, expected):
        labels = dict(self._fields['state']._description_selection(self.env))
        for certificate in self:
            if certificate.state not in expected:
                raise UserError(_("This request cannot be processed in its current state (%s).")
                                % labels[certificate.state])

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

    def _ems_is_issued_step_done(self):
        """Whether the certificate already has its number and the issuer's stamp."""
        self.ensure_one()
        return bool(self.stamp_ids.filtered(lambda stamp: stamp.action == 'issue'))

    def _ems_check_applicant_data(self):
        labels = self.fields_get(APPLICANT_REQUIRED_FIELDS, ['string'])
        for certificate in self:
            missing = [labels[name]['string'] for name in APPLICANT_REQUIRED_FIELDS if not certificate[name]]
            if missing:
                raise UserError(_("Fill in the applicant's details first: %s.", ", ".join(missing)))

    def _ems_check_step_data(self):
        """What the current step needs before it is done: the applicant's details always; the
        workplace training from the step that completes it on (and at the latest when issuing);
        every document the type requires before issuing."""
        self._ems_check_applicant_data()
        labels = self.fields_get(COMPANY_REQUIRED_FIELDS, ['string'])
        for certificate in self:
            action = certificate.step_id.action
            if certificate.kind == 'fct' and action in ('complete', 'issue'):
                missing = [labels[name]['string'] for name in COMPANY_REQUIRED_FIELDS if not certificate[name]]
                if missing:
                    raise UserError(_("Fill in the workplace training first: %s.", ", ".join(missing)))
            missing_documents = certificate.document_ids.filtered(lambda line: not line.attachment_ids)
            if action == 'issue' and missing_documents:
                raise UserError(_("Attach the required documentation before issuing the certificate: %s.",
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
            certificate._ems_post_note(_("Request submitted: it is now with %s.", first.role_id.name))
        self._ems_schedule_task()

    def action_done_step(self):
        """The current step is done: its stamp is recorded (the issuing step also gives the
        certificate its number) and the request moves on - or, after the last step, the PDF is
        generated and sent to the applicant."""
        self._ems_check_state(('in_progress',))
        self._ems_check_can_act()
        self._ems_check_step_data()
        today = fields.Date.context_today(self)
        for certificate in self:
            step = certificate.step_id
            vals = {}
            if step.action == 'issue' and not certificate.name:
                course = self.env['ems.course'].search([('is_current', '=', True)], limit=1)
                vals.update(name=certificate._ems_next_number(course), course_id=course.id)
            vals['stamp_ids'] = [(0, 0, {'step_id': step.id, 'action': step.action, 'name': step.name,
                                         'user_id': self.env.user.id, 'date': today})]
            next_step = certificate._ems_next_step()
            vals.update(step_id=next_step.id, return_reason=False)
            certificate._ems_close_tasks()
            certificate.sudo().write(vals)
            certificate._ems_post_note(_("%(step)s: done by %(user)s.", step=step.name, user=self.env.user.name))
            if next_step:
                certificate._ems_schedule_task()
            else:
                certificate._ems_finish()

    @api.model
    def _ems_next_number(self, course):
        return self.env['ems.base'].next_course_number('ems.certificate', "Certificates", 'CERT', course)

    def _ems_finish(self):
        """After the last step: the final PDF, the request closed and the applicant told."""
        self.ensure_one()
        self._ems_generate_pdf()
        self.sudo().write({'state': 'issued'})
        self._ems_send('ems.email_template_certificate_issued', attachments=self.certificate_pdf_id)

    def _ems_return(self, reason):
        """Back to the previous step, saying why: its stamp is undone, it has to be done again.
        The certificate keeps its number if it already had one."""
        self._ems_check_state(('in_progress',))
        self._ems_check_can_act()
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
        self.sudo().write({'state': 'rejected', 'reject_reason': reason})
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
        self.sudo().write({'state': 'cancelled', 'cancel_reason': reason})
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
        they fill in their details there, no login needed."""
        self._ems_check_state(('draft',))
        self._ems_check_secretariat()
        for certificate in self:
            if not certificate.applicant_email:
                raise UserError(_("Fill in the applicant's email first."))
            certificate._ems_send('ems.email_template_certificate_form')

    def action_submit(self):
        """The secretariat fills in the details itself (e.g. a request on paper) and starts the
        circuit without sending the form."""
        self._ems_check_state(('draft',))
        self._ems_check_secretariat()
        self._ems_submit()

    def _ems_form_url(self):
        self.ensure_one()
        return f"{self.get_base_url()}{self.get_portal_url()}"

    # --- collaborating company -----------------------------------------------

    def action_create_company(self):
        """Create the collaborating company from what the applicant wrote, and link it."""
        self.ensure_one()
        if not self.company_name:
            raise UserError(_("The applicant did not write the company's name."))
        Partner = self.env['res.partner']
        company = Partner.search([('contact_type', '=', 'company'), ('vat', '=', self.company_vat)], limit=1) \
            if self.company_vat else Partner
        if not company:
            company = Partner.create({'name': self.company_name, 'vat': self.company_vat or False,
                                      'is_company': True, 'contact_type': 'company'})
        self.training_company_id = company

    # --- tasks and messages ----------------------------------------------------

    def _ems_schedule_task(self):
        """The current step's task, for whoever holds its position. Quietly: they find it in
        their daily summary (developer, 2026-10-31), not in an email of its own."""
        base = self.env['ems.base']
        for certificate in self.filtered(lambda certificate: certificate.state == 'in_progress' and certificate.step_id):
            step = certificate.step_id
            for user in base.task_users(base.role_users(step.role_id), step.role_id.name):
                certificate.sudo().with_context(mail_activity_quick_update=True).activity_schedule(
                    act_type_xmlid='ems.mail_activity_certificate_step',
                    summary=_("%(step)s: %(student)s", step=step.name, student=certificate.student_id.display_name),
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
            return [(self.applicant_email, self.student_id.lang)]
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

    def _ems_report_paragraphs(self):
        """The certificate's text, one translatable sentence each so every language keeps its own
        word order, in the environment's language (the report renders in the centre's)."""
        self.ensure_one()
        env = self.env

        def sentence(template, **values):
            bold = {key: Markup('<strong>{}</strong>').format(value or '') for key, value in values.items()}
            return Markup(escape(template)) % bold

        issue = self._ems_stamps_to_print().filtered(lambda stamp: stamp.action == 'issue')[:1]
        paragraphs = [
            sentence(env._("%(secretary)s, secretary of %(centre)s,"), secretary=issue.user_id.name,
                     centre=env.company.name),
            Markup('<strong>{}</strong>').format(env._("CERTIFIES:")),
        ]
        if self.kind == 'fct':
            company = self.training_company_id
            paragraphs.append(sentence(
                env._("That %(student)s, with identity document %(document)s, a student of %(study)s, did %(hours)s "
                      "hours of workplace training (FCT) in the school year %(year)s at the company %(company)s, "
                      "with VAT number %(vat)s, from %(start)s to %(end)s.")
                if company.vat else
                env._("That %(student)s, with identity document %(document)s, a student of %(study)s, did %(hours)s "
                      "hours of workplace training (FCT) in the school year %(year)s at the company %(company)s, "
                      "from %(start)s to %(end)s."),
                student=self.student_name, document=self.student_document, study=self.study_id.name,
                hours=self.hours, year=self.fct_school_year, company=company.name, vat=company.vat,
                start=format_date(env, self.period_start), end=format_date(env, self.period_end)))
            paragraphs.append(
                sentence(env._("Source: the training agreement registered in sBID with number %(number)s, a copy of "
                               "which is attached."), number=self.agreement_reference)
                if self.agreement_reference else
                Markup(escape(env._("Source: the training agreement, a copy of which is attached."))))
        paragraphs.append(Markup(escape(env._(
            "And for the record, I issue this certificate at the request of the person concerned."))))
        city = env.company.city
        date = format_date(env, issue.date)
        paragraphs.append(Markup(escape(f"{city}, {date}" if city else date)))
        return paragraphs

    def _ems_stamps_to_print(self):
        """The stamps the certificate carries: who issued it and who approved it."""
        self.ensure_one()
        return self.stamp_ids.filtered(lambda stamp: stamp.action in ('issue', 'approve')).sorted('id')

    def _ems_generate_pdf(self):
        """Render the certificate and append the pages of the required documents the type adds to
        it, images included; keep it on the request, replacing any earlier one."""
        self.ensure_one()
        centre_env = self.env['res.company']._ems_centre_env()
        pdf, _content_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.action_report_certificate', self.ids)
        appended = self.document_ids.sudo().filtered('append_to_certificate').sorted('sequence')
        pages = [pdf] + [self._ems_annex_pdf(attachment) for attachment in appended.attachment_ids]
        previous = self.certificate_pdf_id
        self.sudo().certificate_pdf_id = self.env['ir.attachment'].sudo().create({
            'name': centre_env._("Certificate %s.pdf", self.name),
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
    def _ems_parse_portal_form(self, post):
        """The applicant's form as field values: the text as written, dates and hours parsed, an
        unknown study or a wrong date left out. Returns (values, missing required labels)."""
        values = {}
        for name in ('student_name', 'student_document', 'fct_school_year', 'company_name', 'company_vat',
                     'agreement_reference'):
            values[name] = (post.get(name) or '').strip() or False
        study = post.get('study_id')
        values['study_id'] = int(study) if study and study.isdigit() \
            and self.env['ems.study'].sudo().browse(int(study)).exists() else False
        for name in ('period_start', 'period_end'):
            try:
                values[name] = fields.Date.to_date(post.get(name)) if post.get(name) else False
            except ValueError:
                values[name] = False
        hours = (post.get('hours') or '').strip()
        values['hours'] = int(hours) if hours.isdigit() else 0
        labels = self.fields_get(APPLICANT_REQUIRED_FIELDS, ['string'])
        missing = [labels[name]['string'] for name in APPLICANT_REQUIRED_FIELDS if not values[name]]
        return values, missing

    def _ems_portal_documents(self):
        """The required documents the applicant may attach: theirs, or anyone's."""
        self.ensure_one()
        return self.document_ids.filtered(lambda line: line.type_document_id._ems_applicant_may_upload())

    def _ems_portal_attach(self, files):
        """Store the files the applicant uploaded. `files` maps a required document of the type
        (ems.certificate.type.document id) to its files, and None to the optional ones; a document
        the applicant may not attach is ignored."""
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        lines = {line.type_document_id.id: line for line in self._ems_portal_documents()}
        attached = Attachment
        for document_id, uploads in files.items():
            line = lines.get(document_id) if document_id else None
            if document_id and not line:
                continue
            target = line or self
            attachments = Attachment.create([{
                'name': upload.filename, 'raw': upload.read(), 'res_model': target._name, 'res_id': target.id,
            } for upload in uploads])
            field = 'attachment_ids' if line else 'other_attachment_ids'
            target.sudo()[field] = [(4, attachment.id) for attachment in attachments]
            attached |= attachments
        return attached

    def _ems_portal_fill(self, values, files):
        """The form submitted from the token link: the details, the files, and the circuit starts."""
        self.ensure_one()
        self._ems_check_state(('draft',))
        self.sudo().write(values)
        self._ems_portal_attach(files)
        self.sudo()._ems_submit()

    def _ems_portal_answer(self, message, files):
        """The applicant's answer to a request for documentation: back to the step it was on."""
        self.ensure_one()
        self._ems_check_state(('documentation',))
        attachments = self._ems_portal_attach(files)
        body = Markup("<p>{}</p>{}").format(
            message or _("New documentation attached."),
            self.env['ems.base'].build_html_list(attachments.mapped('name')) if attachments else Markup(""))
        self.sudo()._ems_resume(Markup("<p>{}</p>{}").format(_("Answer from the applicant:"), body))


class EmsCertificateDocument(models.Model):
    """A document the request's type requires, with the files attached for it. Only who the type
    says may attach them: the applicant (from the portal), the holders of its positions, or anyone
    taking part when it names nobody; the administrator always."""
    _name = 'ems.certificate.document'
    _description = "Required document of a certificate request, with its files."
    _order = 'certificate_id, sequence, id'

    certificate_id = fields.Many2one(string="Certificate request", comodel_name='ems.certificate', required=True,
                                     ondelete='cascade', index=True)
    type_document_id = fields.Many2one(string="Required document", comodel_name='ems.certificate.type.document',
                                       required=True, ondelete='cascade', readonly=True)
    name = fields.Char(related='type_document_id.name')
    sequence = fields.Integer(related='type_document_id.sequence')
    append_to_certificate = fields.Boolean(related='type_document_id.append_to_certificate')
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_certificate_document_attachment_rel', column1='document_id',
                                      column2='attachment_id')
    uploaders = fields.Char(string="Attached by", compute='_compute_uploaders')
    is_attached = fields.Boolean(string="Attached", compute='_compute_is_attached')
    can_upload = fields.Boolean(string="Can attach it", compute='_compute_can_upload')

    @api.depends('type_document_id.applicant_uploads', 'type_document_id.role_ids')
    def _compute_uploaders(self):
        for line in self:
            document = line.type_document_id
            if document._ems_anyone():
                line.uploaders = _("Anyone")
                continue
            names = ([_("Applicant")] if document.applicant_uploads else []) + document.role_ids.mapped('name')
            line.uploaders = ", ".join(names)

    @api.depends('attachment_ids')
    def _compute_is_attached(self):
        for line in self:
            line.is_attached = bool(line.attachment_ids)

    @api.depends('certificate_id.state', 'type_document_id.role_ids')
    @api.depends_context('uid')
    def _compute_can_upload(self):
        is_admin = self.certificate_id._ems_is_admin()
        base = self.env['ems.base']
        users_by_role = {}
        for line in self:
            document = line.type_document_id
            if line.certificate_id.state not in ('draft',) + OPEN_STATES:
                line.can_upload = False
            elif is_admin or document._ems_anyone():
                line.can_upload = True
            else:
                for role in document.role_ids - document.role_ids.browse(list(users_by_role)):
                    users_by_role[role.id] = base.role_users(role)
                line.can_upload = any(self.env.user in users_by_role[role.id] for role in document.role_ids)

    def write(self, vals):
        if not self.env.su:
            if set(vals) - {'attachment_ids'}:
                raise UserError(_("Only the files of a required document can be changed."))
            for line in self:
                if not line.can_upload:
                    raise AccessError(_("You cannot attach %(document)s: it is attached by %(who)s.",
                                        document=line.name, who=line.uploaders))
        res = super().write(vals)
        if 'attachment_ids' in vals:
            for line in self:
                line.attachment_ids._ems_link_to(line)
        return res


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
    action = fields.Selection(string="Action", selection=STEP_ACTIONS, required=True)
    user_id = fields.Many2one(string="Done by", comodel_name='res.users', required=True, ondelete='restrict')
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
