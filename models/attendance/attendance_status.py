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
    
    # This field is used to filter the availabe students within the view (avoiding the selection of repeated students on attendance session form).
    inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 

    # The teacher_id is used just for permission filtering pruposes.
    template_teacher_id = fields.Many2one(string="Template's teacher", related="attendance_session_id.template_teacher_id", store=False)    
    session_teacher_id = fields.Many2one(string="Session's teacher", related="attendance_session_id.session_teacher_id", store=False)    
   
    notes = fields.Text("Notes")
    
    def status_is_notificable(self):
        # TODO: load from EMS settings.
        return self.status in ['m_miss', 'a_issue']    

    def write(self, vals):
        super(ems_attendance_status, self).write(vals)
        self._update_notification()   

    def _update_notification(self):
        session = self.attendance_session_id

        # NOTE: Original data must be compared with the current one in order to update properly.            
        previous_issue_status = False
        issue_tutor = session.get_issue_tutor(self.student_id.tutor_id)
        if issue_tutor: 
            issue_student = session.get_issue_student(issue_tutor, self.student_id)
            if issue_student:
                previous_issue_status = session.get_issue_status(self.id)

         # NOTE: Possible scenarios when updating an attendance status:
                #       1. From issue to non-issue:
                #           1.1. If not notified yet, just remove.
                #           1.2. If notified, a rectification should be send to the family.
                #       2. From issue to issue:
                #           2.1. If not notified yet, update the notification data.
                #           2.2. If notified, a rectification should be send to the family.
                #       3. From non-issue to issue:
                #           3.1. Add the notification with the regular timeout. 
                #       4. From non-issue to non-issue:
                #           4.1. Do nothing.
       
        if previous_issue_status:            
            if not previous_issue_status.pending:
                # 1.2 & 2.2. If notified, a rectification should be send to the family.                 
                # TODO: rectification mail
                # TODO: rectification mail
                fake = 0
            else:
                if not self.status_is_notificable():
                    # 1.1. If not notified yet, just remove.
                    # NOTE: button_cancel source: https://github.com/OCA/queue/blob/18.0/queue_job/models/queue_job.py
                    previous_issue_status.notification_id.button_cancel()
                    previous_issue_status.unlink()
                else:
                    # 2.1. If not notified yet, update the notification data.
                    previous_issue_status.write({
                        "attendance_status": self.status
                    })
        elif self.status_is_notificable():
            # 3.1. Add the notification with the regular timeout. 
            # TODO: do not notify to the families after certain timeout (eg: is from a few days ago).
            status_by_tutor = dict()
            session.collect_issue_status_data(self.id, status_by_tutor)
            session.create_notification_entries(status_by_tutor)

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

    @api.depends('attendance_session_id', 'student_id')
    def _compute_display_name(self):              
        for rec in self:
            rec.display_name = "%s | %s" % (rec.attendance_session_id.display_name, rec.student_id.display_name)

    def report_eval(self, field):
        # NOTE: this is used within the 'details_table' template in order to render custom fields.		
        return eval(field)