# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

employee_types = [
    ("asp", "Administrative and Services Personnel"), 
    ("teacher", "Teacher")
]

class ems_employee_base(models.AbstractModel):
    _inherit = ["hr.employee.base"]
    
    notes = fields.Text(string="Notes")
    employee_type = fields.Selection(string="Employee Type", selection="_get_new_employee_type")
    contract_type_id = fields.Many2one(string="Contract Type", comodel_name="hr.contract.type")
    job_id = fields.Many2one(string="Job Position", comodel_name="hr.job", domain="[('employee_type', '=', employee_type)]")
    teaching_ids = fields.One2many(string="Teaching", comodel_name="ems.teaching", inverse_name="teacher_id")
    attendance_template_ids = fields.Many2many(string="Attendance templates", comodel_name="ems.attendance_template", relation="ems_attendance_template_teacher_rel")
    schedule_attendance_ids = fields.One2many(string="Schedule", comodel_name="resource.calendar.attendance", related="resource_calendar_id.attendance_ids")
   
    #Note: manual relation is needed, otherwise Odoo creates two tables within the BBDD, one for 'hr.employee.public' and one for 'hr.employee.base' 
    role_ids = fields.Many2many(string="Roles", comodel_name="ems.role", relation="hr_employee_public_ems_role_rel", column1="hr_employee_public_id", column2="ems_role_id", domain="[('employee_type', '=', employee_type)]") 
    tutorship_ids = fields.One2many(string="Tutorships", comodel_name="ems.group", inverse_name="tutor_id")

    #This fields are computed in order to display string data within some views.
    roles = fields.Char(string="Role names", compute="_compute_roles_str", store=True)	
    tutorships = fields.Char(string="Tutorship names", compute="_compute_tutorships_str", store=True)	

    # This field is used to set the entire form as read-only; compute_sudo needed to compute on read-only.
    read_only = fields.Boolean(string="Read only", compute="_compute_read_only", compute_sudo=True, store=False)

    # NOTE: gates the Schedule tab's Edit/Import/New buttons (schedule_grid_field.js reads this
    # field from the record, since ir.model.access.csv alone can't drive an OWL widget's own
    # button visibility). 'PDF' export is intentionally NOT gated by this field — every role that
    # can already read a schedule may also export it.
    can_edit_schedule = fields.Boolean(string="Can edit schedule", compute="_compute_can_edit_schedule", compute_sudo=True, store=False)

    def _compute_read_only(self):
        for rec in self:
            rec.read_only = self.check_access_rights('write', raise_exception=False)

    def _compute_can_edit_schedule(self):
        can_edit = self.env.user.has_group('ems.group_department_chief')
        for rec in self:
            rec.can_edit_schedule = can_edit

    def _get_new_employee_type(self):
        return employee_types
    
    @api.onchange('tutorship_ids')
    def _onchange_tutorship_ids(self):
        self.update_tutor_role()
        self._sync_security_groups()

    @api.depends("tutorship_ids")
    def _compute_tutorships_str(self):			
        for rec in self:
            rec.tutorships = ""
            for tutorship in rec.tutorship_ids:
                rec.tutorships = "%s, %s" % (rec.tutorships, tutorship.name) 			
            rec.tutorships = rec.tutorships.lstrip(", ")   

    @api.depends("role_ids")
    def _compute_roles_str(self):			
        for rec in self:
            rec.roles = ""
            for role in rec.role_ids:
                rec.roles = "%s, %s" % (rec.roles, role.name) 			
            rec.roles = rec.roles.lstrip(", ")
    
    @api.onchange('job_id')
    def _onchange_job_id(self):
        self._sync_security_groups()

    @api.onchange('role_ids')
    def _onchange_role_ids(self):
        role_tutor = self.env.ref('ems.role_tutor').ids[0]  
        for rec in self:	             
            is_role_tutor = role_tutor in rec.role_ids.ids 
            is_tutor = len(rec.tutorship_ids) > 0
            if not is_role_tutor and is_tutor:                
                rec.tutorship_ids = False
            elif is_role_tutor and not is_tutor:
                rec.role_ids = [(3, role_tutor)]
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': _("The tutor role cannot be assigned manually, it will be set automatically if any group is added to the 'tutorship' field."),
                        'type': 'notification',
                    }
                }
        self._sync_security_groups()

    def update_tutor_role(self):
        role_tutor = self.env.ref('ems.role_tutor').ids[0]
        for rec in self:
            rec.role_ids = [(4 if len(rec.tutorship_ids) > 0 else 3, role_tutor)] # link if tutor, otherwise unlink

    def _sync_security_groups(self):
        """Sync res.users.groups_id based on role_ids and job_id that have a linked security group."""
        role_groups = self.env['ems.role'].sudo().search([('group_id', '!=', False)]).mapped('group_id')
        job_groups = self.env['hr.job'].sudo().search([('group_id', '!=', False)]).mapped('group_id')
        managed_groups = role_groups | job_groups
        if not managed_groups:
            return
        for rec in self:
            employee = self.env['hr.employee'].sudo().search([('id', '=', rec.id)], limit=1)
            if not employee or not employee.user_id:
                continue
            should_have = rec.role_ids.mapped('group_id') | rec.job_id.group_id
            commands = []
            for g in managed_groups:
                if g in should_have and g not in employee.user_id.groups_id:
                    commands.append((4, g.id))
                elif g not in should_have and g in employee.user_id.groups_id:
                    commands.append((3, g.id))
            if commands:
                employee.user_id.sudo().write({'groups_id': commands})

    def write(self, vals):
        if "tutorship_ids" in vals:
            # NOTE: I don't know why, but unlink (3, ID) does not arrive when unlinked from '_onchange_role_ids' (I tried everything!!!), but a remove... (2, ID)
            for command in vals["tutorship_ids"]:
                if command[0] == 2: command[0] = 3
        res = super(ems_employee_base, self).write(vals)
        if 'role_ids' in vals or 'tutorship_ids' in vals or 'job_id' in vals:
            self._sync_security_groups()
        return res
                        
    @api.constrains("role_ids")
    def check_limit(self):
        for rec in self:
            for role in rec.role_ids:                
                role.check_limit()                
class ems_employee(models.AbstractModel):
    _inherit = ["hr.employee"]

    # Info: groups are needed to allow read-only access to teachers
    employee_type = fields.Selection(string="Employee Type", selection_add = employee_types, groups="base.group_system,hr.group_hr_user,ems.group_teacher", ondelete={
        'asp': 'set default',
        'teacher': 'set default'
    })

    attendance_manager_id = fields.Many2one(groups="hr_attendance.group_hr_attendance_officer,ems.group_teacher")
    activity_ids = fields.One2many(groups="hr.group_hr_user,ems.group_teacher")
    activity_exception_decoration = fields.Selection(groups="hr.group_hr_user,ems.group_teacher")
    activity_exception_icon = fields.Char(groups="hr.group_hr_user,ems.group_teacher")
    activity_state = fields.Selection(groups="hr.group_hr_user,ems.group_teacher")
    activity_summary = fields.Char(groups="hr.group_hr_user,ems.group_teacher")
    activity_type_id = fields.Many2one(groups="hr.group_hr_user,ems.group_teacher")
    activity_type_icon = fields.Char(groups="hr.group_hr_user,ems.group_teacher")

    # Real photo storage - kept here (not on res.users) so employees with no linked user
    # (e.g. ASP/support staff) can still have a photo set by an admin from their own form.
    image_private = fields.Binary(string="Photo", attachment=True)

    # Derived, not directly editable here: mirrors user_id.image_visibility (see user.py, where
    # it's actually set from "My Profile"), falling back to 'all' when there's no linked user.
    image_visibility = fields.Selection(
        [('all', 'All'), ('teachers', 'Only teachers'), ('directive', 'Only directive staff')],
        string="Photo visibility", compute='_compute_image_visibility', store=True)

    # image_1920 becomes derived too: it's what avatar.mixin's avatar_*/image_* fields and every
    # many2one_avatar(_employee) widget in the app read from, so blanking it here is what makes
    # the visibility restriction apply everywhere automatically, with no per-view changes needed
    # except in the "Teachers" kanban, where image_private is shown instead for authorized viewers
    # (see views/community/employee/kanban.xml).
    image_1920 = fields.Binary(compute='_compute_image_1920', inverse='_inverse_image_1920', store=True)

    # Drives the image_private swap in the employee kanban for viewers who are allowed to see
    # the real photo even when image_visibility isn't 'all' (self, admin, or the matching group
    # tier). NOTE: no compute_sudo - it must run as the actual requesting user (has_group() below
    # needs the real self.env.user, not the superuser compute_sudo would elevate to), and teachers
    # already have global read access to hr.employee so no extra privilege is needed to compute it.
    photo_visible_to_current_user = fields.Boolean(compute='_compute_photo_visible_to_current_user')

    @api.depends('user_id.image_visibility')
    def _compute_image_visibility(self):
        for employee in self:
            employee.image_visibility = employee.user_id.image_visibility if employee.user_id else 'all'

    @api.depends('image_private', 'image_visibility')
    def _compute_image_1920(self):
        for employee in self:
            employee.image_1920 = employee.image_private if employee.image_visibility == 'all' else False

    def _inverse_image_1920(self):
        for employee in self:
            if employee.image_1920:
                employee.image_private = employee.image_1920

    # depends_context('uid') is required, not just compute_sudo=False: without it, this
    # non-stored field's cached value is keyed only by record id at the transaction level, so a
    # second read by a *different* user would silently reuse the first user's cached result.
    @api.depends_context('uid')
    def _compute_photo_visible_to_current_user(self):
        user = self.env.user
        is_admin = user.has_group('ems.group_academic_admin')
        is_teacher = user.has_group('ems.group_teacher')
        is_directive = user.has_group('ems.group_head_of_studies')
        for employee in self:
            if is_admin or employee.user_id == user:
                employee.photo_visible_to_current_user = True
            elif employee.image_visibility == 'all':
                employee.photo_visible_to_current_user = True
            elif employee.image_visibility == 'teachers':
                employee.photo_visible_to_current_user = is_teacher
            elif employee.image_visibility == 'directive':
                employee.photo_visible_to_current_user = is_directive
            else:
                employee.photo_visible_to_current_user = False

    def _personal_calendar_name(self):
        self.ensure_one()
        course = self.company_id.current_course_id
        return "%s (%s)" % (self.name, course.name) if course else self.name

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        for employee in employees:
            if employee.employee_type != 'teacher':
                continue
            # NOTE: every teacher gets their OWN calendar, always — 'resource_calendar_id' arrives
            # already pre-filled by resource.mixin's client-side default (the company's shared
            # calendar), so it can never be used to detect "nothing was set yet". Sharing a calendar
            # between teachers would break the 1:1 assumption 'apply_schedule_changes' relies on.
            schedule = self.env['resource.calendar'].create({'name': employee._personal_calendar_name()})
            schedule.seed_from_framework(employee.company_id.default_schedule_framework_id)
            employee.resource_calendar_id = schedule
        return employees

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals:
            for employee in self:
                if employee.resource_calendar_id and not employee.resource_calendar_id.is_framework:
                    employee.resource_calendar_id.name = employee._personal_calendar_name()
        return result

    def unlink(self):
        # NOTE: every teacher has their OWN personal calendar (never a shared or framework one — see
        # create() above), so it has no purpose once the employee is gone. Deleting it also cascades to
        # its attendance lines. Re-check after unlink in case two employees ever ended up pointing at
        # the same calendar, and never touch a framework or a company's own base calendar.
        calendars = self.resource_calendar_id.filtered(lambda calendar: not calendar.is_framework)
        result = super().unlink()
        if calendars:
            company_calendar_ids = self.env['res.company'].sudo().search([]).resource_calendar_id.ids
            still_used = self.env['hr.employee'].with_context(active_test=False).search(
                [('resource_calendar_id', 'in', calendars.ids)]
            ).resource_calendar_id
            orphaned = (calendars - still_used).filtered(lambda calendar: calendar.id not in company_calendar_ids)
            orphaned.unlink()
        return result

    def get_report_role_lines(self):
        """One display line per role_ids entry for the working-schedule PDF header, appending
        context for the two roles that need it: a tutor's own tutored group(s) ('ems.role_tutor'),
        or a department head's own department ('ems.role_dchieff') — there's no per-department link
        for that role today, so the employee's own department_id is reused, per product decision."""
        self.ensure_one()
        role_tutor = self.env.ref('ems.role_tutor', raise_if_not_found=False)
        role_dchieff = self.env.ref('ems.role_dchieff', raise_if_not_found=False)
        lines = []
        for role in self.role_ids:
            label = role.name
            if role_tutor and role == role_tutor and self.tutorship_ids:
                label = "%s: %s" % (label, ", ".join(self.tutorship_ids.mapped('name')))
            elif role_dchieff and role == role_dchieff and self.department_id:
                label = "%s: %s" % (label, self.department_id.name)
            lines.append(label)
        return lines

    def find_head_of_studies(self):
        # NOTE: role_hos/role_dhos both map to the same global group_head_of_studies
        # (no per-employee hierarchy field), so this walks parent_id looking for the
        # nearest ascendant in that group; self-approves if the employee is already in it.
        self.ensure_one()
        group = "ems.group_head_of_studies"
        if self.user_id and self.user_id.has_group(group):
            return self
        employee = self.parent_id
        while employee:
            if employee.user_id and employee.user_id.has_group(group):
                return employee
            employee = employee.parent_id
        return self.env["hr.employee"]