# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

employee_types = [
    ("asp", "Administrative and Services Personnel"),
    ("teacher", "Teacher")
]

# Reentrancy guard shared with models/employees/user.py's res.users._sync_partner_photo: the
# employee->user and user->employee photo syncs below call into each other, and without this
# flag a single photo edit could bounce back and forth indefinitely.
EMS_PHOTO_SYNC_CONTEXT_KEY = 'ems_syncing_photo'

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
    # it's actually set from "My Profile"), falling back to 'public' when there's no linked user.
    image_visibility = fields.Selection(
        [('public', 'Public'), ('private', 'Private (only directive staff)'),
         ('no_photo', 'No photo (erase permanently)')],
        string="Photo visibility", compute='_compute_image_visibility', store=True)

    # image_1920 becomes derived too: it's what avatar.mixin's avatar_*/image_* fields and every
    # many2one_avatar(_employee) widget in the app read from, so setting it to the initials
    # placeholder here (not blanking it) is what makes the restriction apply everywhere
    # automatically - including res.users/res.partner (see user.py's write()), which have no
    # further fallback of their own to rely on. Authorized viewers still see the real photo, but
    # only in the "Teachers" kanban and the employee form, where effective_photo is swapped in
    # (see views/community/employee/{kanban,form}.xml).
    image_1920 = fields.Binary(compute='_compute_image_1920', inverse='_inverse_image_1920', store=True)

    # Falls back to the linked user's own photo when the employee has no image_private of their
    # own - matching core Odoo's own hr.employee._compute_avatar fallback (an employee with no
    # photo of their own shows their user's avatar instead), which this feature must not regress:
    # plenty of employees only ever had a photo on their res.users/res.partner record, never
    # copied onto hr.employee. Reads the partner's OWN image_private (the true, unfiltered photo -
    # see contact.py), not its image_1920, which can itself hold the initials placeholder once
    # this feature has touched it. This is the single source both image_1920 and the kanban/form
    # "show the real photo to an authorized viewer" swap read from - never image_private directly.
    effective_photo = fields.Binary(compute='_compute_effective_photo', compute_sudo=True)

    # Drives the effective_photo swap in the employee kanban/form for viewers who are allowed to
    # *see* the real photo even when image_visibility isn't 'public' (self, admin, or directive
    # staff and above) - not the same as being allowed to *change* it, see can_edit_photo below.
    # NOTE: no compute_sudo - it must run as the actual requesting user (has_group() below needs
    # the real self.env.user, not the superuser compute_sudo would elevate to), and teachers
    # already have global read access to hr.employee so no extra privilege is needed to compute it.
    photo_visible_to_current_user = fields.Boolean(compute='_compute_photo_visible_to_current_user')

    # Only directive staff and above (or admin) may upload/replace an employee's photo - NOT the
    # employee themselves (unlike photo_visible_to_current_user, self is deliberately excluded
    # here). See write()'s sudo bypass below, which is what actually enforces this at the ORM
    # level; this field only drives which widget the employee form shows as editable.
    can_edit_photo = fields.Boolean(compute='_compute_can_edit_photo')

    @api.depends('user_id.image_visibility')
    def _compute_image_visibility(self):
        for employee in self:
            employee.image_visibility = employee.user_id.image_visibility if employee.user_id else 'public'

    @api.depends('image_private', 'user_id.partner_id.image_private')
    def _compute_effective_photo(self):
        for employee in self:
            employee.effective_photo = employee.image_private or (
                employee.user_id.partner_id.sudo().image_private if employee.user_id else False)

    @api.depends('effective_photo', 'image_visibility', 'name')
    def _compute_image_1920(self):
        for employee in self:
            if employee.image_visibility == 'public':
                employee.image_1920 = employee.effective_photo
            else:
                # 'private' or 'no_photo': same visual result - the difference is that
                # 'no_photo' has also erased image_private for real (see user.py's write()), so
                # effective_photo naturally ends up empty there and the swap below has nothing
                # to restore even for an authorized viewer.
                employee.image_1920 = employee._avatar_generate_svg() if employee.name else False

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
        is_directive = user.has_group('ems.group_head_of_studies')
        for employee in self:
            if is_admin or employee.user_id == user or employee.image_visibility == 'public':
                employee.photo_visible_to_current_user = True
            else:
                employee.photo_visible_to_current_user = is_directive

    @api.depends_context('uid')
    def _compute_can_edit_photo(self):
        can_edit = self.env.user.has_group('ems.group_head_of_studies')  # implies director/admin
        for employee in self:
            employee.can_edit_photo = can_edit

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
        if (set(vals) == {'image_private'} and not self.env.su
                and not self.env.context.get(EMS_PHOTO_SYNC_CONTEXT_KEY)
                and self.env.user.has_group('ems.group_head_of_studies')):
            # Directive staff (Head of Studies and above) may upload/replace any
            # employee's photo even without general write access to hr.employee (still
            # read-only otherwise, same as any teacher) - mirrors the same sudo-bypass
            # pattern already used for "My Profile" (res.users._inverse_image_private),
            # just for a different authorized group instead of "myself". Scoped to a vals
            # dict containing ONLY image_private so this cannot be used to smuggle a
            # write to any other field on hr.employee.
            return self.sudo().write(vals)

        result = super().write(vals)
        if 'name' in vals:
            for employee in self:
                if employee.resource_calendar_id and not employee.resource_calendar_id.is_framework:
                    employee.resource_calendar_id.name = employee._personal_calendar_name()
        if 'image_private' in vals and not self.env.context.get(EMS_PHOTO_SYNC_CONTEXT_KEY):
            # Keep the linked user's account photo in sync too - without this, editing an
            # employee's photo directly (the only way for anyone but the employee
            # themselves to set it - see above) never reached res.users/res.partner,
            # which is what Discuss/the top bar/the org chart/ems.notice.sent_by actually
            # read (see user.py's _sync_partner_photo for why).
            for employee in self:
                if employee.user_id:
                    employee.user_id.with_context(
                        **{EMS_PHOTO_SYNC_CONTEXT_KEY: True})._sync_partner_photo()
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