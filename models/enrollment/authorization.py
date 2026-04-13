# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class EmsAuthorizationTemplate(models.Model):
    _name = 'ems.authorization.template'
    _description = 'Authorization Template'

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
        """
        Override the template creation so that, as soon as it is created,
        it is automatically linked to open enrollments.
        """
        # 1. Create the templates using Odoo's original method
        templates = super(EmsAuthorizationTemplate, self).create(vals_list)
        
        # 2. Apply retroactive logic to each new template
        for template in templates:
            template.action_apply_to_open_enrollments()
            
        return templates

    def action_apply_to_open_enrollments(self):
        """
        Search for pre-enrollments and add this authorization
        if they match the Level and Study criteria.
        """
        self.ensure_one()
        
        # Only search for unconfirmed enrollments (draft = Quotation, sent = Quotation Sent)
        domain = [('state', 'in', ['draft', 'sent'])]
        
        # If the template is restricted to specific levels, filter enrollments by those levels
        if self.ems_level_ids:
            domain.append(('ems_level_id', 'in', self.ems_level_ids.ids))
            
        # Same for studies
        if self.ems_study_ids:
            domain.append(('ems_study_id', 'in', self.ems_study_ids.ids))
            
        # Execute the database search
        open_enrollments = self.env['sale.order'].search(domain)
        
        # Prepare a list of records to create (batch creation is much faster)
        auths_to_create = []
        for enrollment in open_enrollments:
            # As a safety measure, check if this enrollment already has this template
            existing = enrollment.ems_authorization_ids.filtered(lambda a: a.template_id == self)
            if not existing:
                auths_to_create.append({
                    'enrollment_id': enrollment.id,
                    'template_id': self.id,
                    'status': 'pending',
                })
        
        # Create the authorizations if there are valid candidates
        if auths_to_create:
            self.env['ems.authorization'].create(auths_to_create)

    def action_remove_from_open_enrollments(self):
        """
        Search for pending authorizations linked to this template
        in open pre-enrollments (draft/sent) and remove them.
        Signed/Answered authorizations are protected and ignored.
        """
        self.ensure_one()
        
        # Buscamos las autorizaciones que cumplen los criterios de eliminación
        auths_to_delete = self.env['ems.authorization'].search([
            ('template_id', '=', self.id),
            ('status', '=', 'pending'), # Protección vital: solo borramos las pendientes
            ('enrollment_id.state', 'in', ['draft', 'sent'])
        ])
        
        # Si encuentra alguna, la elimina (unlink)
        if auths_to_delete:
            # Opcional: Podrías contar cuántas se borran si quisieras devolver un mensaje,
            # pero el método unlink() directo es la forma más limpia en Odoo.
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

    _sql_constraints = [
        ('unique_enrollment_template', 'unique(enrollment_id, template_id)', 'This authorization is already requested in this enrollment.')
    ]

    def write(self, vals):
        """
        Intercepts the write method to enforce that internal users (admins/staff)
        must attach a document if they manually change the status.
        """
        if 'status' in vals and vals['status'] == 'no':
            for auth in self:
                if auth.template_id.acceptance_only:
                    raise ValidationError(
                        "The authorization '%s' can only be accepted, not rejected." % auth.template_id.name
                    )
                
        # Check if the 'status' is being changed to something other than 'pending'
        if 'status' in vals and vals['status'] != 'pending':
            for auth in self:
                # Get the document from the current save operation, or from the database if it was already there
                current_doc = vals.get('signed_document', auth.signed_document)
                
                # Check if the user is an internal user (staff/admin) and the document is missing
                if not current_doc and self.env.user.has_group('base.group_user'):
                    raise ValidationError("You must attach a signed PDF document to manually change the authorization status.")

        if 'status' in vals and vals['status'] != 'pending':
            vals['response_date'] = fields.Datetime.now()
            vals['response_uid'] = self.env.user.id

        # Si se elimina el documento, limpiar también la fecha de respuesta
        if 'signed_document' in vals and not vals['signed_document']:
            vals['response_date'] = False
            vals['response_uid'] = False

        return super(EmsAuthorization, self).write(vals)


class EmsAuthorizationResponse(models.Model):
    _name = 'ems.authorization.response'
    _description = 'Authorization Field Response'

    authorization_id = fields.Many2one('ems.authorization', required=True, ondelete='cascade')
    field_id = fields.Many2one('ems.authorization.field', required=True, ondelete='cascade')
    label = fields.Char(related='field_id.label', string='Label', readonly=True)
    value = fields.Char(string='Value')