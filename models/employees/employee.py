# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

employee_types = [
    ("asp", "Administrative and Services Personnel"), 
    ("teacher", "Teacher")
]

class ims_employee_base(models.AbstractModel):
    _inherit = ["hr.employee.base"]
    
    notes = fields.Text(string="Notes")
    employee_type = fields.Selection(string="Employee Type", selection="_get_new_employee_type")
    contract_type_id = fields.Many2one(string="Contract Type", comodel_name="hr.contract.type")
    job_id = fields.Many2one(string="Job Position", comodel_name="hr.job", domain="[('employee_type', '=', employee_type)]")
    teaching_ids = fields.One2many(string="Teaching", comodel_name="ims.teaching", inverse_name="teacher_id")	
   
    #Note: manual relation is needed, otherwise Odoo creates two tables within the BBDD, one for 'hr.employee.public' and one for 'hr.employee.base' 
    role_ids = fields.Many2many(string="Roles", comodel_name="ims.role", relation="hr_employee_public_ims_role_rel", column1="hr_employee_public_id", column2="ims_role_id", domain="[('employee_type', '=', employee_type)]") 
    tutorship_ids = fields.One2many(string="Tutorships", comodel_name="ims.group", inverse_name="tutor_id")

    #This fields are computed in order to display string data within some views.
    roles = fields.Char(string="Role names", compute="_compute_roles_str", store=True)	
    tutorships = fields.Char(string="Tutorship names", compute="_compute_tutorships_str", store=True)	

    def _get_new_employee_type(self):
        return employee_types

    @api.depends("tutorship_ids")
    @api.onchange('tutorship_ids')
    def _onchange_tutorship_ids(self):	
        for rec in self:
            role_tutor = self.env.ref('ims.role_tutor').ids[0]
            if len(rec.tutorship_ids) > 0:                
                rec.write({'role_ids' : [(4, role_tutor)]})
            else:
                rec.write({'role_ids' : [(3, role_tutor)]})

    @api.onchange('teaching_ids')
    def _onchange_teaching_ids(self):	
        # Same as contact's _onchange_enrollment_ids
        for rec in self:
            ignore = []   
            old_sub = []
            teaching = {}  
            for item in rec._origin.teaching_ids:
                old_sub.append(item.subject_id)
                ignore.append(item.subject_id)
                teaching[item.subject_id] = item        

            added = []                      
            for item in rec.teaching_ids:
                if item.subject_id not in old_sub:
                    added.append(item.subject_id)
                if item.subject_id not in teaching:
                    teaching[item.subject_id] = item                                                         
           
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
                                'teaching_ids': [(0, 0, {
                                    "teacher_id": rec.id, 
                                    "group_id": teaching[sub].group_id,
                                    "subject_id": parent.id,      
                                })]
                            })   
                        parent = parent.subject_id                                                                              

                    # If has childs, they must be added (recursive) if no other childs are present.
                    self._teaching_populate_descendant(rec, sub, teaching)                     
    
    def _teaching_populate_descendant(self, rec, sub, teaching):
        for ch in sub.subject_ids:
            rec.write({
                'teaching_ids': [(0, 0, {
                    "teacher_id": rec.id, 
                    "group_id": teaching[sub].group_id,
                    "subject_id": ch.id,      
                })]
            }) 
            self._teaching_populate_descendant(rec, ch, teaching) 
    
    @api.constrains("role_ids")
    def check_limit(self):
        for rec in self:
            for role in rec.role_ids:                
                role.check_limit()                
				
    @api.depends("role_ids")
    def _compute_roles_str(self):			
        for rec in self:
            rec.roles = ""
            for role in rec.role_ids:
                rec.roles = "%s, %s" % (rec.roles, role.name) 			
            rec.roles = rec.roles.lstrip(", ")

    
    @api.depends("tutorship_ids")
    def _compute_tutorships_str(self):			
        for rec in self:
            rec.tutorships = ""
            for tutorship in rec.tutorship_ids:
                rec.tutorships = "%s, %s" % (rec.tutorships, tutorship.name) 			
            rec.tutorships = rec.tutorships.lstrip(", ")

class ims_employee(models.AbstractModel):
    _inherit = ["hr.employee"]

    # Info: groups is needed to avoid warnings
    employee_type = fields.Selection(string="Employee Type", selection_add = employee_types, groups="base.group_system,hr.group_hr_user", ondelete={
        'asp': 'set default',
        'teacher': 'set default'
    })