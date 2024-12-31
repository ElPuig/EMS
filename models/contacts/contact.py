# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.http import request
from odoo.exceptions import ValidationError

class ems_contact(models.Model):
    _inherit = ['res.partner']
            
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
    car_plate = fields.Char(string="Car Plate")

    @api.onchange('enrollment_ids')
    def _onchange_enrollment_ids(self):	
        # The idea is to populate the enrollment data in both directions:
        #	Up:   if the subjece has a parent, create it if missing.
        #	Down: if the subject has children, create them if missing.		
        #
        # Warning: the added or removed row is not retreived, and there's only access to the original field's data and the 
        # current one, so if more than one action is done (add and remove), it's not possible to know which parent or child 
        # rows must be added or removed. Example: added a child subject, so auto-added its main; the main subject is removed 
        # BUT in the curren't data there's only information about the two childrens... the idea was to remove also all its 
        # children, but it's not possible to know if the main was removed or the children was added! 
        # 
        # So, it's not possible to remove all the children when a parent is removed...
        # TODO: Maybe this limitation can be overcomed by inheriting the listview and customizing some clic methods or events?

        for rec in self:
            ignore = []   
            old_sub = []
            enrollments = {}  
            for item in rec._origin.enrollment_ids:
                old_sub.append(item.subject_id)
                ignore.append(item.subject_id)
                enrollments[item.subject_id] = item        

            added = []                      
            for item in rec.enrollment_ids:
                if item.subject_id not in old_sub:
                    added.append(item.subject_id)
                if item.subject_id not in enrollments:
                    enrollments[item.subject_id] = item                                                         
            
            for sub in added:
                if sub.subject_id in added:
                    # The current one and also its parents should be ignored, to avoid adding already removed childs.                    
                    ignore.append(sub)
                    while sub:
                        if sub not in ignore: ignore.append(sub)
                        sub = sub.subject_id

            for sub in added:
                # For every added enrollment: 
                # If has parent, it must be added (recursive) if not present.                
                if sub not in ignore:
                    parent = sub.subject_id
                    while parent:          
                        if parent not in ignore:
                            ignore.append(parent.id)                                                       
                            rec.write({
                                'enrollment_ids': [(0, 0, {
                                    "student_id": rec.id, 
                                    "group_id": enrollments[sub].group_id,
                                    "subject_id": parent.id,      
                                })]
                            })   
                        parent = parent.subject_id                                                                              

                    # If has childs, they must be added (recursive) if no other childs are present.
                    self._enrollment_populate_descendant(rec, sub, enrollments)                     
    
    def _enrollment_populate_descendant(self, rec, sub, enrollments):
        for ch in sub.subject_ids:
            rec.write({
                'enrollment_ids': [(0, 0, {
                    "student_id": rec.id, 
                    "group_id": enrollments[sub].group_id,
                    "subject_id": ch.id,      
                })]
            }) 
            self._enrollment_populate_descendant(rec, ch, enrollments) 

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

    def open_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.id,						
            'view_id': self.env.ref('ems.view_contact_form').id,
            'view_mode': 'form',
        }

    #def _compute_enrollment_data(self, contact):
		# The idea is to populate the enrollment data in both directions:
		#	Up:   if the subject has a parent, create it if missing.
		#	Down: if the subject has children, create them if missing.		
        
        # subject = self.env["ems.subject"].search([("id", "=", values.get('subject_id'))]) or False 
        # if subject.subject_id:
        #     # Has a parent
        #     enrollment = self.env["ems.enrollment"].search([("subject_id", "=", subject.subject_id.id)]) or False
        #     if len(enrollment) == 0:
        #         # Create the parent entry
        #         current.subject_view_ids.create({
        #             "level": rec.level,
        #             "code": rec.code,
        #             "acronym": rec.acronym,
        #             "name": rec.name,                        
        #             "subject_id": rec.id,
        #             "study_id": study.id,
        #         })

        # if subject.subject_id:
        