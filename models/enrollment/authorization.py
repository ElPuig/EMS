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
    apply_on = fields.Selection([
        ('enrollment', 'Enrollment process'),
        ('standalone', 'Sent during the course'),
    ], string='Applies on', default='enrollment', required=True,
    help="Enrollment process: automatically attached to every open enrollment matching "
         "the scope below. Sent during the course: never attached automatically, it only "
         "reaches a student through the 'Send Authorizations' assistant - for forms that "
         "appear once the academic year has already started and its enrollments are closed.")
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
        it applies to, not just future ones - unless it is a standalone one, which
        never takes part in the enrollment process at all (see apply_on)."""
        templates = super().create(vals_list)
        for template in templates.filtered(lambda t: t.apply_on == 'enrollment'):
            template.action_apply_to_open_enrollments()
        return templates

    def _matches_scope(self, level, study):
        """AND-of-scopes: this template applies to a given level/study pair unless a
        scope it restricts on (ems_level_ids/ems_study_ids) is set and doesn't contain
        the given value. An empty scope field applies to everything on that dimension.
        Shared by action_apply_to_open_enrollments() (template -> matching enrollments),
        sale.order._get_authorization_commands() (enrollment -> matching templates) and
        ems.authorization.send.wizard's 'template_scope' target (template -> matching
        students) so they can never drift apart again - see
        docs/en/developers/enrollment/authorization.md.
        """
        self.ensure_one()
        if self.ems_level_ids and level not in self.ems_level_ids:
            return False
        if self.ems_study_ids and study not in self.ems_study_ids:
            return False
        return True

    def action_apply_to_open_enrollments(self):
        """Attach this template's authorization to every still-open (draft/sent)
        enrollment matching its level/study scope (AND-of-scopes, see
        _matches_scope()), skipping enrollments that already have it.
        """
        self.ensure_one()
        if self.apply_on != 'enrollment':
            return
        open_enrollments = self.env['sale.order'].search(
            [('state', 'in', ['draft', 'sent'])]
        ).filtered(lambda enrollment: self._matches_scope(
            enrollment.ems_level_id, enrollment.ems_study_id))
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
        if self.apply_on != 'enrollment':
            return
        auths_to_delete = self.env['ems.authorization'].search([
            ('template_id', '=', self.id),
            ('status', '=', 'pending'),
            ('enrollment_id.state', 'in', ['draft', 'sent'])
        ])
        auths_to_delete.unlink()

    def action_send_to_scope(self):
        """Open the send assistant preloaded with these templates, targeting every
        enrolled student their own level/study scope matches."""
        return {
            'type': 'ir.actions.act_window',
            'name': _("Send Authorizations"),
            'res_model': 'ems.authorization.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_ids': [(6, 0, self.ids)],
                'default_target': 'template_scope',
            },
        }

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
    _order = 'course_id desc, partner_id, id'

    def init(self):
        """Standalone counterpart of the 'unique_enrollment_template' _sql_constraints
        below: a student may only ever be asked one template once per academic year
        outside an enrollment. Partial (WHERE enrollment_id IS NULL) because an
        enrollment-bound row is already keyed by its own enrollment, and because a
        cancelled enrollment may legitimately coexist with an active one for the same
        (student, course) - sale_order_unique_enrollment_per_course excludes cancelled
        orders, so a blanket (partner, course, template) index would not even build on
        real data. Same technique as sale.order.init().
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ems_authorization_unique_standalone
            ON ems_authorization (partner_id, course_id, template_id)
            WHERE enrollment_id IS NULL
        """)

    # An authorization reaches a student one of two ways: through the enrollment
    # process, or sent on its own during the school year (issue #443), once the
    # running course's enrollment is already closed and cannot carry it. So the
    # student and the academic year - not the enrollment - are what identifies the
    # record; enrollment_id only says which route created it.
    partner_id = fields.Many2one(
        'res.partner',
        string='Student',
        index=True,
        ondelete='cascade',
        domain="[('contact_type', 'in', ('student', 'applicant'))]",
    )
    course_id = fields.Many2one(
        'ems.course',
        string='Academic Year',
        index=True,
        ondelete='restrict',
        help="Academic year for this enrollment.",
    )
    enrollment_id = fields.Many2one('sale.order', string='Enrollment', ondelete='cascade')
    template_id = fields.Many2one('ems.authorization.template', string='Template', required=True, ondelete='restrict')

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

    study_name = fields.Char(
        string='Study',
        compute='_compute_study_name',
        help="The study this authorization is about, for display and for the legal text's "
             "{{study_name}} placeholder.",
    )
    legal_text_rendered = fields.Html(
        string='Legal Text (Rendered)',
        compute='_compute_legal_text_rendered',
        sanitize=False,
    )

    _sql_constraints = [
        ('unique_enrollment_template', 'unique(enrollment_id, template_id)', 'This authorization is already requested in this enrollment.')
    ]

    @api.depends('partner_id.name', 'template_id.name')
    def _compute_display_name(self):
        for auth in self:
            auth.display_name = ' - '.join(
                part for part in (auth.partner_id.name, auth.template_id.name) if part)

    @api.depends('enrollment_id.ems_study_id.name', 'partner_id.main_group_id.study_id.name',
                 'partner_id.study_id.name')
    def _compute_study_name(self):
        """The enrollment's own study when there is one; otherwise the study of the group
        the student is actually sitting in (ems.group.study_id via main_group_id), which is
        the authoritative "what is this student attending now". res.partner.study_id comes
        last: it is the form-oriented mirror and, on an applicant, it means the study the
        student is heading TO, not the one being taught."""
        for auth in self:
            auth.study_name = (auth.enrollment_id.ems_study_id.name
                               or auth.partner_id.main_group_id.study_id.name
                               or auth.partner_id.study_id.name or '')

    @api.depends('template_id.legal_text', 'partner_id.name', 'course_id.name', 'study_name')
    def _compute_legal_text_rendered(self):
        for auth in self:
            text = auth.template_id.legal_text or ''
            replacements = {
                '{{student_name}}': auth.partner_id.name or '',
                '{{academic_year}}': auth.course_id.name or '',
                '{{study_name}}': auth.study_name or '',
            }
            for placeholder, value in replacements.items():
                text = text.replace(placeholder, value)
            auth.legal_text_rendered = text

    @api.constrains('partner_id', 'course_id')
    def _check_target(self):
        """Every authorization is addressed to one student for one academic year, whether
        it hangs off an enrollment or was sent standalone.

        Deliberately not `required=True` on the two fields: they were introduced on an
        already-populated table, and Odoo attempts the column's SET NOT NULL during
        _auto_init - before migrations/18.0.0.25.0/post-migrate.py can backfill them.
        sql.set_not_null() swallows that failure with a warning, so the constraint would
        silently be absent on every upgraded database and present on every fresh one,
        which is exactly the environment divergence CLAUDE.md's Migrations section warns
        about. A Python constraint covers both paths identically.
        """
        for auth in self:
            if not auth.partner_id:
                raise ValidationError(_("An authorization must be addressed to a student."))
            if not auth.course_id:
                raise ValidationError(_(
                    "The authorization '%(name)s' needs an academic year.",
                    name=auth.template_id.name,
                ))

    @api.onchange('enrollment_id')
    def _onchange_enrollment_id(self):
        for auth in self.filtered('enrollment_id'):
            auth.partner_id = auth.enrollment_id.partner_id
            auth.course_id = auth.enrollment_id.ems_course_id

    @api.model_create_multi
    def create(self, vals_list):
        """Enrollment-bound rows inherit their student and academic year from the
        enrollment, so neither the one2many sync nor a wizard has to restate them."""
        for vals in vals_list:
            self._fill_target_from_enrollment(vals)
        return super().create(vals_list)

    def write(self, vals):
        """Enforce authorization-response business rules before persisting.

        An acceptance-only authorization can never be rejected. An internal
        user (staff/admin) manually changing the status away from 'pending'
        must attach a signed document; portal users are exempt, since the
        portal flow generates and attaches the response certificate itself
        right after this write (see
        controllers/portal_enrollment.py:portal_enrollment_authorize).
        """
        if vals.get('enrollment_id'):
            self._fill_target_from_enrollment(vals, force=True)
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

    def _fill_target_from_enrollment(self, vals, force=False):
        """Copy partner_id/course_id out of vals' enrollment, in place."""
        if not vals.get('enrollment_id'):
            return
        enrollment = self.env['sale.order'].browse(vals['enrollment_id'])
        if force or not vals.get('partner_id'):
            vals['partner_id'] = enrollment.partner_id.id
        if force or not vals.get('course_id'):
            vals['course_id'] = enrollment.ems_course_id.id

    def _certificate_filename(self):
        """Name of the response certificate PDF. A standalone authorization has no
        enrollment code to name the file after, so it falls back to the academic year."""
        self.ensure_one()
        return 'Cert_%s_%s.pdf' % (self.enrollment_id.name or self.course_id.name,
                                   self.template_id.name[:30])


class EmsAuthorizationResponse(models.Model):
    _name = 'ems.authorization.response'
    _description = 'Authorization Field Response'

    authorization_id = fields.Many2one('ems.authorization', required=True, ondelete='cascade')
    field_id = fields.Many2one('ems.authorization.field', required=True, ondelete='cascade')
    label = fields.Char(related='field_id.label', string='Label', readonly=True)
    value = fields.Char(string='Value')
