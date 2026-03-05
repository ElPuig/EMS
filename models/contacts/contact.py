# -*- coding: utf-8 -*-

from odoo import models, fields, api
from ..shared import base
import datetime
from dateutil.relativedelta import relativedelta

class ems_student_benefit(models.Model):
    _name = 'ems.student.benefit'
    _description = 'Student Benefits and Exemptions'
    
    student_id = fields.Many2one('res.partner', string="Student", required=True, ondelete='cascade')
    
    benefit_type = fields.Selection([
        # Bonificaciones
        ('large_family_gen', 'Large Family (General)'),
        ('single_parent_gen', 'Single Parent (General)'),
        ('scholarship', 'Ministry Scholarship'),
        # Exenciones
        ('large_family_spec', 'Large Family (Special)'),
        ('single_parent_spec', 'Single Parent (Special)'),
        ('disability', 'Disability (>33%)'),
        ('other', 'Other Exemption')
    ], string="Type", required=True)
    
    category = fields.Selection([
        ('bonification', 'Bonification (Partial)'),
        ('exemption', 'Exemption (Total)')
    ], string="Category", compute="_compute_category", store=True)

    document = fields.Binary(string="Document", required=True)
    document_name = fields.Char(string="File Name")
    renewal_date = fields.Date(string="Renewal/Review Date")
    notes = fields.Char(string="Notes")

    @api.depends('benefit_type')
    def _compute_category(self):
        for rec in self:
            if not rec.benefit_type:
                # If no type is selected, there is no Bonification or Exemption.
                rec.category = False
            elif rec.benefit_type in ['large_family_gen', 'single_parent_gen', 'scholarship']:
                rec.category = 'bonification'
            else:
                rec.category = 'exemption'

    @api.onchange('benefit_type')
    def _onchange_benefit_type(self):
        if self.benefit_type:
            today = fields.Date.today()
            
            # Scholarship case: 9 months
            if self.benefit_type == 'scholarship':
                self.renewal_date = today + relativedelta(months=9)
            # Other cases: 2 years
            else:
                self.renewal_date = today + relativedelta(years=2)

class ems_contact(models.Model):
    _inherit = ['res.partner'] # NOTE: unable to inherit also from ems.base, I got an error like 'TypeError: Many2many fields ResPartner.channel_ids and res.partner.channel_ids use the same table and columns'.
            
    # view-oriented fields:
    # level_id and study_id are used for form view purposes (linked dropdowns: level > study > group) and will be computed on save.
    level_id = fields.Many2one(string='Level', comodel_name='ems.level')    
    study_id = fields.Many2one(string='Studies', comodel_name='ems.study') 
    tutor_id = fields.Many2one(string='Tutor', related="main_group_id.tutor_id") # Related field: auto-computed and auto-refreshed within the form.
    
    # model-data fields:
    main_group_id = fields.Many2one(string='Main Group', comodel_name='ems.group')     
    enrollment_ids = fields.One2many(string='Enrollment', comodel_name='ems.enrollment', inverse_name='student_id')
    contact_type = fields.Selection(string='Contact Type', selection=[('provider', 'Provider'), ('student', 'Student'), ('family', 'Family')])   
    family_relation = fields.Char(string="Family relation")
    student_email = fields.Char(string="Student email")	
    student_id = fields.Char(string="Student ID")
    medical_id = fields.Char(string="Medical ID")
    birth_date = fields.Date(string="Birth Date")
    birth_country_id = fields.Many2one(string="Birth Country", comodel_name='res.country')
    citizenship_id =  fields.Many2one(string="Citizenship", comodel_name='res.country')
    #auth_image = fields.Boolean(string="Image Rights")
    #auth_trip = fields.Boolean(string="Scholar Trips")
    #auth_healt = fields.Boolean(string="Health Data")
    #auth_share = fields.Boolean(string="Share with family", help="If marked, the student (even if adult) allows to share its educational information with its family.")
    auth_image = fields.Boolean(string="Image Rights", compute="_compute_auth_booleans")
    auth_trip = fields.Boolean(string="Scholar Trips", compute="_compute_auth_booleans")
    auth_healt = fields.Boolean(string="Health Data", compute="_compute_auth_booleans")
    auth_share = fields.Boolean(string="Share with family", compute="_compute_auth_booleans", help="If marked, the student (even if adult) allows to share its educational information with its family.")
    car_plate = fields.Char(string="Car Plate")
    is_adult = fields.Boolean(string="Adult", compute="_compute_is_adult", store=False)

    # Fields to store student Benefits:
    benefit_ids = fields.One2many(string='Benefits & Exemptions', comodel_name='ems.student.benefit', inverse_name='student_id')
    benefit_status = fields.Selection([
        ('none', 'None'),
        ('bonification', 'Bonification'),
        ('exemption', 'Exemption')
    ], string="Benefits", compute="_compute_benefit_status", store=True)

    ems_authorization_ids = fields.Many2many(
        'ems.authorization',
        compute='_compute_ems_authorization_ids',
        string='Authorizations'
    )

    # NOTE: this field is computed when loaded within a form or list
    read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)

    @api.depends('ems_authorization_ids')
    def _compute_auth_booleans(self):
        for student in self:
            # 1. Por defecto, todo a False
            image, trip, health, share = False, False, False, False
            
            # 2. Revisamos las autorizaciones del alumno
            for auth in student.ems_authorization_ids:
                if auth.status == 'yes': # ¡Aquí usamos la clave interna!
                    # Si está aceptada, marcamos el booleano correspondiente
                    if auth.template_id.auth_type == 'image':
                        image = True
                    elif auth.template_id.auth_type == 'trip':
                        trip = True
                    elif auth.template_id.auth_type == 'health':
                        health = True
                    elif auth.template_id.auth_type == 'share':
                        share = True
            
            # 3. Asignamos los valores finales al alumno
            student.auth_image = image
            student.auth_trip = trip
            student.auth_healt = health
            student.auth_share = share

    def _compute_ems_authorization_ids(self):
        for partner in self:
            # Buscamos las matrículas (sale.order) de este alumno y sacamos sus autorizaciones
            enrollments = self.env['sale.order'].search([('partner_id', '=', partner.id)])
            partner.ems_authorization_ids = enrollments.mapped('ems_authorization_ids')

    @api.depends('benefit_ids', 'benefit_ids.category')
    def _compute_benefit_status(self):
        for rec in self:
            if not rec.benefit_ids:
                rec.benefit_status = 'none'
            else:
                categories = rec.benefit_ids.mapped('category')
                # Priority 1: If there is an exemption, the status will be Exemption.
                if 'exemption' in categories:
                    rec.benefit_status = 'exemption'
                # Priority 2: If there is a bonus, the status will be Exemption.
                elif 'bonification' in categories:
                    rec.benefit_status = 'bonification'
                # If there are lines but no defined category
                else:
                    rec.benefit_status = 'none'

    @api.depends('birth_date')
    def _compute_is_adult(self):	
        for rec in self:	
            rec.is_adult = (relativedelta(datetime.date.today(), rec.birth_date).years >= 18)

    @api.onchange('level_id')
    def _onchange_level_id(self):	
        for rec in self:			
            rec.study_id = False
        
    @api.onchange('study_id')
    def _onchange_study_id(self):	
        for rec in self:			
            rec.main_group_id = False
     
    @api.model_create_multi
    def create(self, values):
        # Fired when the model is created (Source: https://www.cybrosys.com/blog/how-to-override-create-write-and-unlink-methods-in-odoo-17)
        # NOTE: values is a list of dicts (method fired only once) 
        for entry in values:
            self._compute_group_data(entry) 
            
            # NOTE: I don't know why, but the 'contact_type' value does not arrive for contact data (contact within student 
            #       form) so the value will be manually setup here.
            if 'parent_id' in entry and entry['parent_id']:
                parent = self.env['res.partner'].browse(entry['parent_id'])
                if parent.contact_type == 'student':
                    entry['contact_type'] = 'family'
                elif parent.contact_type == 'provider':
                    entry['contact_type'] = 'provider'
        
        contact = super(ems_contact, self).create(values)

        return contact
    
    def write(self, values):
        # Fired when the model is updated (Source: https://www.cybrosys.com/blog/how-to-override-create-write-and-unlink-methods-in-odoo-17)
        # Note: values is a dict (method fired once per entry)
        self._compute_group_data(values)
        contact =  super(ems_contact, self).write(values)

        return contact

    def _compute_group_data(self, values):
        # Avoids incongruences between the main_group, level and studies.     
        if 'main_group_id' in values and values.get('main_group_id'):   
            group = self.env["ems.group"].search([("id", "=", values.get('main_group_id'))]) or False                 
            values["level_id"] = group.level_id.id
            values["study_id"] = group.study_id.id

        elif 'study_id' in values and values.get('study_id'):
            study = self.env["ems.study"].search([("id", "=", values.get('study_id'))]) or False            
            values["level_id"] = study.level_id.id

    def _get_read_only_user(self):
        is_admin = base.ems_base.get_user_is_admin(self)
        is_tutor = False
        for t in self.env.user.employee_ids:
            if t.id != False and len(t.tutorship_ids) > 0:
                if self.tutor_id == t:
                    is_tutor = True                    
                    break
        return not (is_admin or is_tutor)
    
    def open_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.id,						
            'view_id': self.env.ref('ems.view_contact_form').id,
            'view_mode': 'form',
        }   