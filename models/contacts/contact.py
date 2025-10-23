# -*- coding: utf-8 -*-

from odoo import models, fields, api
from ..shared import utils
import datetime

class ems_contact(models.Model):
    _inherit = ['res.partner'] # NOTE: unable to inherit also from ems.utils, I got an error like 'TypeError: Many2many fields ResPartner.channel_ids and res.partner.channel_ids use the same table and columns'.
            
    # view-oriented fields:
    # level_id and study_id are used for form view purposes (linked dropdowns: level > study > group) and will be computed on save.
    level_id = fields.Many2one(string='Level', comodel_name='ems.level')    
    study_id = fields.Many2one(string='Studies', comodel_name='ems.study') 
    tutor_id = fields.Many2one(string='Tutor', related="main_group_id.tutor_id") # Related field: auto-computed and auto-refreshed within the form.
    
    # model-data fields:
    main_group_id = fields.Many2one(string='Main Group', comodel_name='ems.group')     
    enrollment_ids = fields.One2many(string='Enrollment', comodel_name='ems.enrollment', inverse_name='student_id')
    contact_type = fields.Selection(string='Contact Type', selection=[('provider', 'Provider'), ('student', 'Student')])   
    student_email = fields.Char(string="Student email")	
    student_id = fields.Char(string="Student ID")
    medical_id = fields.Char(string="Medical ID")
    birth_date = fields.Date(string="Birth Date")
    birth_country_id = fields.Many2one(string="Birth Country", comodel_name='res.country')
    citizenship_id =  fields.Many2one(string="Citizenship", comodel_name='res.country')
    auth_image = fields.Boolean(string="Image Rights")
    auth_trip = fields.Boolean(string="Scholar Trips")
    auth_healt = fields.Boolean(string="Health Data")
    auth_share = fields.Boolean(string="Share with family", help="If marked, the student (even if adult) allows to share its educational progression with its family.")
    car_plate = fields.Char(string="Car Plate")
    is_adult = fields.Boolean(string="Adult", compute="_compute_is_adult", store=False)

    # NOTE: this field is computed when loaded within a form or list
    read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)

    @api.depends('birth_date')
    def _compute_is_adult(self):	
        for rec in self:	
            birth_date = rec.birth_date
            age = datetime.date.today() - birth_date		
            rec.is_adult = (age.days / 365 >= 18)

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
        # Note: values is a list of dicts (method fired only once)
        for entry in values:
            self._compute_group_data(entry) 
        contact = super(ems_contact, self).create(values)

        #self._compute_enrollment_data(contact)
        return contact
    
    def write(self, values):
        # Fired when the model is updated (Source: https://www.cybrosys.com/blog/how-to-override-create-write-and-unlink-methods-in-odoo-17)
        # Note: values is a dict (method fired once per entry)
        self._compute_group_data(values)
        contact =  super(ems_contact, self).write(values)

        #self._compute_enrollment_data(contact)
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
        is_admin = utils.ems_utils.get_user_is_admin(self)
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