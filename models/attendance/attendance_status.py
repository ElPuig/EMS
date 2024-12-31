# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

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
	notes = fields.Text("Notes")

	# this field is used to filter the availabe students within the view (avoiding the selection of repeated students on attendance session form).
	inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 

	@api.depends('attendance_session_id')
	def _compute_inuse_student_ids(self):
		for rec in self:
			rec.inuse_student_ids = False
			if rec.attendance_session_id:
				rec.inuse_student_ids = rec.mapped('attendance_session_id.attendance_status_ids.student_id')
	
	def report_eval(self, field):
		# Note: this is used within the 'details_table' template in order to render custom fields.		
		return eval(field)


	@api.depends('attendance_session_id', 'student_id')
	def _compute_display_name(self):              
		for rec in self:
            # rec.display_name = "%s | %s | %s" % (rec.attendance_schedule_id.display_name, rec.date, rec.space_id.name)
			rec.display_name = "%s | %s" % (rec.attendance_session_id.display_name, rec.student_id.display_name)
    

class ems_absence_bulk_justification_wizard(models.TransientModel):
    _name = 'ems.absence_bulk_justification_wizard'
    _description = 'Attendance: Bulk justification wizard'
    
    initial_selection = fields.Many2many(
        'ems.attendance_status',
        string='Initial selection',
        default=lambda self: self._get_default_initial_selection()
    )
    
    def _get_default_initial_selection(self):
        return self.env['ems.attendance_status'].browse(
            self.env.context.get('active_ids', [])
        )

    # Filters
    # name_filter = fields.Char(string='Student name contains')
    # email_filter = fields.Char(string='Student email contains')
    student_id = fields.Many2one(
        'res.partner',  
        string='Select student',
        domain="[('contact_type', '=', 'student')]",
    )
    date_start = fields.Date(string='Date (from)')
    date_end = fields.Date(string='Date (to)')

    # Filtered results
    statuses_ids = fields.Many2many(
        'ems.attendance_status',
        string='Attendance results',
        relation='bulk_justification_wizard_filtered_attendance_status_rel',
        column1='wizard_id',
        column2='attendance_status_id'
    )

    # Selected filtered results
    selected_statuses_ids = fields.Many2many(
        'ems.attendance_status',
        string='Selected absences',
        relation='bulk_justification_wizard_selected_attendance_status_rel',
        column1='wizard_id',
        column2='attendance_status_id'
    )

    @api.onchange('student_id', 'date_start', 'date_end')
    def _onchange_filters(self):
        if any([self.student_id, self.date_start, self.date_end]):
            self._filter_statuses()

    def _filter_statuses(self):
        domain = []
        # if self.name_filter:
        #     domain.append(('student_id.name', 'ilike', self.name_filter))
        # if self.email_filter:
        #     domain.append(('student_id.email', 'ilike', self.email_filter))
        if self.student_id:
             domain.append(('student_id', '=', self.student_id.id))
        if self.date_start:
            domain.append(('attendance_session_id.date', '>=', self.date_start))
        if self.date_end:
            domain.append(('attendance_session_id.date', '<=', self.date_end))

        #Only getting unjustified absences
        domain.append(('status','=', 'm_miss'))

        self.statuses_ids = self.env['ems.attendance_status'].search(domain)
        return {
            'type': 'ir.actions.do_nothing',
        }
    
    def action_select_all(self):        
        self.selected_statuses_ids = self.statuses_ids
        #TODO: Mirar qué acción devolver para que no se pierdan los valores filtrados
        return {}

    def action_deselect_all(self):
        self.selected_statuses_ids = False
        #TODO: Mirar qué acción devolver para que no se pierdan los valores filtrados
        return {}

    def action_confirm(self):
        self.ensure_one()
        if not self.selected_statuses_ids:
            raise UserError(_('You must select at least one element'))

        _logger.info(f"Selected {len(self.selected_statuses_ids)} absences to be bulk action treated")

        for attendance_status in self.selected_statuses_ids:
            _logger.info(f"Justifying -> ID: {attendance_status.id}, Nombre: {attendance_status.student_id.name}")
            #Justify every status to "m_justified"
            attendance_status.status = "m_justified"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%d absences justified') % len(self.selected_statuses_ids),
                'sticky': False,
                'next': { 
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            },
        }