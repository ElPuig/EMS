# -*- coding: utf-8 -*-

from odoo import models, fields, api

# NOTE: In order to allow customization (like adding new status types), status starting with 'a_' will be 
#		computed as an 'attendance' snd starting with 'm_' as a 'm_miss' when reporting summary data.
attendance_status = [("a_attended", "Attended"), ("a_delayed", "Delayed"), ("m_miss", "Miss"), ("m_justified", "Justified Miss"), ("a_issue", "Issue")]

class ems_attendance_status(models.Model):
    _name = "ems.attendance_status"
    _description = "Attendance status: information about session per student."

    status = fields.Selection(string="Status", default="a_attended", required=True, selection=attendance_status)
    student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
    image_1920 = fields.Binary(string="Image", related='student_id.image_1920')
    attendance_session_id = fields.Many2one(string="Session", comodel_name="ems.attendance_session")
    attendance_justification_id = fields.Many2one(string="Justification", comodel_name="ems.attendance_justification")    
    
    # This field is used to filter the availabe students within the view (avoiding the selection of repeated students on attendance session form).
    inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 

    # The teacher_id is used just for permission filtering pruposes.
    template_teacher_id = fields.Many2one(string="Template's teacher", related="attendance_session_id.template_teacher_id", store=False)    
    session_teacher_id = fields.Many2one(string="Session's teacher", related="attendance_session_id.session_teacher_id", store=False)    
   
    notes = fields.Text("Notes")
    
    @api.model_create_multi
    def create(self, values):		
        status = super(ems_attendance_status, self).create(values)        
        for s in status:
            if s.status in ['m_miss', 'a_issue'] and (s.student_id.auth_share or not s.student_id.is_adult):
                # NOTE: sudo needed because no teacher can create those manually.
                self.sudo().env['ems.attendance_notification'].create({
                    'attendance_status_id': s.id,
                    'student_id': s.student_id.id                            
                })                            

    @api.depends('attendance_session_id')
    def _compute_attendance_session_display_name(self):
        for rec in self:
            rec.attendance_session_display_name = rec.attendance_session_id.display_name

    @api.depends('attendance_session_id')
    def _compute_inuse_student_ids(self):
        for rec in self:
            rec.inuse_student_ids = False
            if rec.attendance_session_id:
                rec.inuse_student_ids = rec.mapped('attendance_session_id.attendance_status_ids.student_id')

    def report_eval(self, field):
        # NOTE: this is used within the 'details_table' template in order to render custom fields.		
        return eval(field)

    @api.depends('attendance_session_id', 'student_id')
    def _compute_display_name(self):              
        for rec in self:
            rec.display_name = "%s | %s" % (rec.attendance_session_id.display_name, rec.student_id.display_name)