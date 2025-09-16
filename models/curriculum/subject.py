# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, MissingError

class ems_subject(models.Model):
    _name = "ems.subject"
    _description = "Subject: The main item for a student's subject."
    _order = "code asc"
    _sql_constraints = [
        ('unique_code', 'unique (code)', 'duplicated code!')
    ]
    
    code = fields.Char(string="Code", required=True)
    acronym = fields.Char(string="Acronym", required=True)
    name = fields.Char(string="Name", required=True)
    ects = fields.Integer(string="ECTS Credits") 
    internal_hours = fields.Integer(string="Internal hours") 
    external_hours = fields.Integer(string="External hours")   

    total_internal_hours = fields.Integer(string="Total internal hours", compute='_compute_total_internal_hours', recursive=True) # Computed sum(hours / total_hours)
    total_external_hours = fields.Integer(string="Total external hours", compute='_compute_total_external_hours', recursive=True) # Computed sum(hours / total_hours)
    total_hours = fields.Integer(string="Total hours", compute='_compute_total_hours', recursive=True) # Computed sum(hours / total_hours)

    last = fields.Boolean(string="Last", compute='_compute_last') # To know if it's the last sub-subject (needed for views)
    
    notes = fields.Text("Notes")

    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
    # TODO: the teacher is assigned using the "teaching" model. Remove this field when possible.
    #teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]")

    subject_ids = fields.One2many(string="Composite", comodel_name="ems.subject", inverse_name="subject_id", domain="[('id', '!=', id), ('level', '>', level), ('subject_id', '=', False)]")
    subject_id = fields.Many2one(string="Main subject", comodel_name="ems.subject")
    
    outcome_ids = fields.One2many(string="Learning Outcome", comodel_name="ems.outcome", inverse_name="subject_id")
    content_ids = fields.One2many(string="Content", comodel_name="ems.content", inverse_name="subject_id")    

    #criteria_ids = fields.One2many(string="Criteria", comodel_name="ems.criteria", inverse_name="subject_id")

    #The subject_view_ids is used as a view for the subject list
    subject_view_ids = fields.One2many(comodel_name="ems.subject_view", inverse_name="subject_id", compute="_compute_subject_views", store=True)

    # The following fields are computed and used to display the data correctly within the treeview
    level = fields.Integer(string="Level", default=1)
	    
    @api.depends("study_ids")
    def _compute_subject_views(self):	        
        for rec in self:
            self.env['ems.subject_view'].search([('subject_id', '=', rec.id)]).unlink(True)
            if len(rec.study_ids) == 0:
                rec.subject_view_ids.create({                    
                    "subject_id": rec.id
                })                
            else:
                for study in rec.study_ids:                
                    rec.subject_view_ids.create({                        
                        "subject_id": rec.id,
                        "study_id": study.id
                    })  
                     
            for child in rec.subject_ids:
                studies = []
                for study in rec.study_ids:                
                    studies.append(study.id)
                
                child.write({'study_ids' : [(6, 0, studies)]})

    @api.depends("subject_id")
    def _compute_level(self):	        
        for rec in self:
            if rec.subject_id.id != False: rec.level = rec.subject_id.level + 1 

    @api.onchange("subject_id")
    def _onchange_subject_id(self):
        for rec in self:
            rec.study_ids = rec.subject_id.study_ids                    
   
    @api.depends("subject_ids.internal_hours")
    def _compute_total_internal_hours(self):
        for rec in self:
            rec.total_internal_hours = sum((line.internal_hours if line.last else line.total_internal_hours) for line in rec.subject_ids)

    @api.depends("subject_ids.external_hours")
    def _compute_total_external_hours(self):
        for rec in self:
            rec.total_external_hours = sum((line.external_hours if line.last else line.total_external_hours) for line in rec.subject_ids)

    @api.depends("subject_ids.total_hours")
    @api.onchange("internal_hours", "external_hours")
    def _compute_total_hours(self):
        for rec in self:
            th = rec.total_internal_hours + rec.total_external_hours            
            rec.total_hours = rec.internal_hours + rec.external_hours if rec.last or th == 0 else th

    @api.depends("subject_ids")
    def _compute_last(self):
        for rec in self:
            rec.last = (len(rec.subject_ids) == 0)

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if rec.subject_id.id != False: 
                if not rec.code.startswith(rec.subject_id.code):
                    raise ValidationError("The code must start as the parent's code.")
        
    def unlink(self):        
        for rec in self:
            rec.env['ems.subject_view'].search([('subject_id', '=', rec.id)]).unlink(True)
        return super(ems_subject, self).unlink()

    @api.depends('acronym', 'subject_id', 'name')
    def _compute_display_name(self):       
        acronyms = []           
        for rec in self:
            acronyms.clear()
            if rec.acronym:
                acronyms.append(rec.acronym)
                
                parent = rec.subject_id
                while(parent):
                    acronyms.append(parent.acronym)
                    parent = parent.subject_id  
                
                rec.display_name = "%s: %s" % (" ".join(list(reversed(acronyms))), rec.name)
            else:
                rec.display_name = ''
    
    def open_form(self):
        return {
            'name': '%s Edit' % self._description.split(':')[0],
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,						
            'view_id': self.env.ref('ems.view_%s_form' % (self._name.split('.')[1])).id,
            'view_mode': 'form',
            'target': 'new'
        }
    
class ems_subject_view(models.Model):
    _name = "ems.subject_view"
    _description = "View model for displaying subject data within studies (because a subject can be shared along different studies)."
    
    # TODO: FIX --> The view data should be updated if the subject changes, so, should be a related field. 
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
    study_id = fields.Many2one(string="Study", comodel_name="ems.study")
    level = fields.Integer(string="Level", related="subject_id.level")    
    code = fields.Char(string="Code", related="subject_id.code")
    acronym = fields.Char(string="Acronym", related="subject_id.acronym")
    name = fields.Char(string="Name", related="subject_id.name")    
    study_acronym = fields.Char(string="Study's acronym", compute='_compute_study_acronym')
    deprecated = fields.Boolean(string="Deprecated", related="study_id.deprecated")
    
    def unlink(self, avoidCircular=False): 
        # This can be called from the list view, which means the user wants to remove a subject, so both subject_view and subject must be removed.
        # But, this can also be called from subject's internal code, like when computing the subject_view entires, which means that the subject shall NOT be removed.         
        if avoidCircular:
            # The call comes from "subject"
            return super(ems_subject_view, self).unlink()
        else:
            # The call comes from "subject_view"
            try:            
                return self.subject_id.unlink()                                
            except MissingError:
                # Maybe, the subject has been already removed (multiple view entries points to the same subject)...
                return True   
    
    @api.depends('study_id')
    def _compute_study_acronym(self):       
        for rec in self:
            rec.study_acronym =  "%s (%s)" % (rec.study_id.acronym, (rec.study_id.date.year if rec.study_id.date != False else '???'))   

    @api.depends('subject_id', 'study_id', 'name', 'acronym')
    def _compute_display_name(self):       
        acronyms = []           
        for rec in self:
            acronyms.clear()
            if rec.acronym:
                acronyms.append(rec.acronym)
                
                parent = rec.subject_id
                while(parent):
                    acronyms.append(parent.acronym)
                    parent = parent.subject_id  

                rec.display_name = "%s %s: %s" % (rec.study_id.acronym, " ".join(list(reversed(acronyms))), rec.name)              
            else:
                rec.display_name = ''

    def open_form(self):
        return self.subject_id.open_form()
        # return {
        #     'name': 'Subject Edit',
        #     'domain': [],
        #     'res_model': 'ems.subject',
        #     'type': 'ir.actions.act_window',
        #     'view_mode': 'form',
        #     'view_type': 'form',
        #     'res_id': (0 if self == False else self.subject_id.id),
        #     'context': self._context,
        #     'target': 'new',
        # }