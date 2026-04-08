# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_subject(models.Model):
    _name = "ems.subject"
    _description = "Subject: The main item for a student's subject."    
    _rec_names_search = ['name', 'acronym']
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
    total_hours = fields.Integer(string="Total hours", compute='_compute_total_hours')
            
    outcome_ids = fields.One2many(string="Learning Outcome", comodel_name="ems.outcome", inverse_name="subject_id")
    content_ids = fields.One2many(string="Content", comodel_name="ems.content", inverse_name="subject_id")        
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")       

    notes = fields.Text("Notes")            

    @api.onchange("internal_hours", "external_hours")
    def _compute_total_hours(self):
        for rec in self:
            rec.total_hours = rec.internal_hours + rec.external_hours    

    @api.depends('acronym', 'name')
    def _compute_display_name(self):               
        for rec in self:                
            rec.display_name = "%s: %s" % (rec.acronym, rec.name)
