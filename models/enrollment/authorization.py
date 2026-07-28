# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmsAuthorizationTemplate(models.Model):
    _name = 'ems.authorization.template'
    _description = 'Authorization Template'
    _order = 'name'

    name = fields.Char(string='Title', required=True, help="E.g., Image and Sound Use Authorization")
    legal_text = fields.Html(string='Legal Text', required=True)
    is_required = fields.Boolean(string='Mandatory to Respond', default=True)
    acceptance_only = fields.Boolean(
        string='Acceptance Only',
        default=False,
        help="If enabled, this authorization can only be accepted."
    )
    template_download_url = fields.Char(string='Template Download URL', help='URL to download the physical document template.')
    auth_type = fields.Selection([
        ('image', 'Image Rights'),
        ('trip', 'Scholar Trips'),
        ('health', 'Health Data'),
        ('share', 'Share with Family'),
        ('other', 'Other / General')
    ], string="Authorization Type", default='other',
    help="Select the specific type to automatically update the student's file.")

    ems_level_ids = fields.Many2many(
        'ems.level',
        string='Applies to Levels',
        help="Select the levels this applies to."
    )

    ems_study_ids = fields.Many2many(
        'ems.study',
        string='Applies to Studies',
        help="Select the specific studies this applies to. If both Levels and Studies are empty, it applies to all enrollments."
    )
    field_ids = fields.One2many('ems.authorization.field', 'template_id', string='Data Fields')

    @api.model_create_multi
    def create(self, vals_list):
        """A new template retroactively attaches itself to every open enrollment
        it applies to, not just future ones."""
        templates = super().create(vals_list)
        for template in templates:
            template.action_apply_to_open_enrollments()
        return templates

    def action_apply_to_open_enrollments(self):
        """Attach this template's authorization to every still-open (draft/sent)
        enrollment matching its level/study scope, skipping enrollments that
        already have it.

        Matches on level AND study when both are set on the template (an
        AND-of-scopes) — this differs from ``sale.order._get_authorization_commands``,
        which uses OR-of-scopes for the live onchange sync. See
        docs/en/developers/enrollment/authorization.md, "Known gap: two
        different matching semantics" for the details of that inconsistency.
        """
        self.ensure_one()
        domain = [('state', 'in', ['draft', 'sent'])]
        if self.ems_level_ids:
            domain.append(('ems_level_id', 'in', self.ems_level_ids.ids))
        if self.ems_study_ids:
            domain.append(('ems_study_id', 'in', self.ems_study_ids.ids))

        open_enrollments = self.env['sale.order'].search(domain)
        auths_to_create = []
        for enrollment in open_enrollments:
            existing = enrollment.ems_authorization_ids.filtered(lambda a: a.template_id == self)
            if not existing:
                auths_to_create.append({
                    'enrollment_id': enrollment.id,
                    'template_id': self.id,
                    'status': 'pending',
                })
        if auths_to_create:
            self.env['ems.authorization'].create(auths_to_create)

    def action_remove_from_open_enrollments(self):
        """Drop this template's still-pending authorizations from open
        (draft/sent) enrollments. Answered ones (accepted/rejected) are
        never touched, on any enrollment state."""
        self.ensure_one()
        auths_to_delete = self.env['ems.authorization'].search([
            ('template_id', '=', self.id),
            ('status', '=', 'pending'),
            ('enrollment_id.state', 'in', ['draft', 'sent'])
        ])
        auths_to_delete.unlink()

class EmsAuthorizationField(models.Model):
    _name = 'ems.authorization.field'
    _description = 'Authorization Template Field'
    _order = 'sequence, id'

    template_id = fields.Many2one('ems.authorization.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    label = fields.Char(string='Label', required=True)
    field_type = fields.Selection([
        ('char', 'Short Text'),
        ('text', 'Long Text'),
        ('date', 'Date'),
    ], string='Type', default='char', required=True)
    placeholder = fields.Char(string='Placeholder/Example')
    is_required = fields.Boolean(string='Required when accepting', default=True)


class EmsAuthorization(models.Model):
    _name = 'ems.authorization'
    _description = 'Enrollment Authorization'
    _order = 'id'

    enrollment_id = fields.Many2one('sale.order', string='Enrollment', ondelete='cascade', required=True)
    template_id = fields.Many2one('ems.authorization.template', string='Template', required=True, ondelete='restrict')
    course_id = fields.Many2one(related='enrollment_id.ems_course_id', string="Academic Year", readonly=True)

    legal_text = fields.Html(related='template_id.legal_text', string="Legal Text", readonly=True)
    template_download_url = fields.Char(related='template_id.template_download_url', string="Template URL", readonly=True)

    status = fields.Selection([
        ('pending', 'Pending'),
        ('yes', 'Accepted'),
        ('no', 'Rejected')
    ], string='Status', default='pending', required=True)

    acceptance_only = fields.Boolean(
        related='template_id.acceptance_only',
        string='Acceptance Only',
        readonly=True,
        store=False,
    )

    response_date = fields.Datetime(string='Response Date', readonly=True)
    response_uid = fields.Many2one(
        'res.users',
        string='Responded by',
        readonly=True,
        help="User who responded to this authorization (portal student/family or internal staff)."
    )
    signed_document = fields.Binary(string='Document', attachment=True)
    signed_document_name = fields.Char(string='Document Name')
    response_field_ids = fields.One2many('ems.authorization.response', 'authorization_id', string='Field Responses')

    legal_text_rendered = fields.Html(
        string='Legal Text (Rendered)',
        compute='_compute_legal_text_rendered',
        sanitize=False,
    )

    _sql_constraints = [
        ('unique_enrollment_template', 'unique(enrollment_id, template_id)', 'This authorization is already requested in this enrollment.')
    ]

    @api.depends('template_id.legal_text', 'enrollment_id.partner_id.name',
                 'enrollment_id.ems_course_id.name', 'enrollment_id.ems_study_id.name')
    def _compute_legal_text_rendered(self):
        for auth in self:
            text = auth.template_id.legal_text or ''
            replacements = {
                '{{student_name}}': auth.enrollment_id.partner_id.name or '',
                '{{academic_year}}': auth.enrollment_id.ems_course_id.name or '',
                '{{study_name}}': auth.enrollment_id.ems_study_id.name or '',
            }
            for placeholder, value in replacements.items():
                text = text.replace(placeholder, value)
            auth.legal_text_rendered = text

    def write(self, vals):
        """Enforce authorization-response business rules before persisting.

        An acceptance-only authorization can never be rejected. An internal
        user (staff/admin) manually changing the status away from 'pending'
        must attach a signed document; portal users are exempt, since the
        portal flow generates and attaches the response certificate itself
        right after this write (see
        controllers/portal_enrollment.py:portal_enrollment_authorize).
        """
        responding = 'status' in vals and vals['status'] != 'pending'
        if responding:
            for auth in self:
                if vals['status'] == 'no' and auth.template_id.acceptance_only:
                    raise ValidationError(_(
                        "The authorization '%(name)s' can only be accepted, not rejected.",
                        name=auth.template_id.name,
                    ))
                current_doc = vals.get('signed_document', auth.signed_document)
                if not current_doc and self.env.user.has_group('base.group_user'):
                    raise ValidationError(_(
                        "You must attach a signed PDF document to manually "
                        "change the authorization status."))
            vals['response_date'] = fields.Datetime.now()
            vals['response_uid'] = self.env.user.id

        # Clearing the document also clears the response metadata tied to it.
        if 'signed_document' in vals and not vals['signed_document']:
            vals['response_date'] = False
            vals['response_uid'] = False

        return super().write(vals)


class EmsAuthorizationResponse(models.Model):
    _name = 'ems.authorization.response'
    _description = 'Authorization Field Response'

    authorization_id = fields.Many2one('ems.authorization', required=True, ondelete='cascade')
    field_id = fields.Many2one('ems.authorization.field', required=True, ondelete='cascade')
    label = fields.Char(related='field_id.label', string='Label', readonly=True)
    value = fields.Char(string='Value')
