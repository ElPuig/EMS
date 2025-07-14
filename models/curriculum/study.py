# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_study(models.Model):
    _name = "ims.study"
    _description = "Study: The concrete type of stidy (kind of bachelor, concrete univeristy grade, etc.)"
    
    code = fields.Char(string="Code", required=True)
    acronym = fields.Char(string="Acronym", required=True)
    name = fields.Char(string="Name", required=True)
    date = fields.Date(string="Release Date", required=True)
    deprecated = fields.Boolean(string="Deprecated", required=True)    
    notes = fields.Text(string="Notes")
    
    follow_ids = fields.One2many(string="Follow-up", comodel_name="ims.tracking", inverse_name="study_id")
    subject_ids = fields.Many2many(string="Subjects", comodel_name="ims.subject") 
    level_id = fields.Many2one(string="Level", comodel_name="ims.level")

    attachment_ids = fields.Many2many(string="Attached files", comodel_name="ir.attachment", domain="[('res_model', '=', 'ims.study')]")
    
    @api.depends('acronym', 'name')
    def _compute_display_name(self):              
        for rec in self:
            rec.display_name = "%s: %s" % (rec.acronym, rec.name)
    
    @api.depends("subject_ids")
    def _compute_subject_ids(self):
        for rec in self:
            for sub in rec.subject_ids:
                rec.write({'subject_ids' : [(4, sub.id)]})


            