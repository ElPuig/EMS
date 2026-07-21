# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

employee_types = [
    ("asp", "Administrative and Services Personnel"),
    ("teacher", "Teacher")
]

WEEKDAYS = ('0', '1', '2', '3', '4')
# Two hour_from/hour_to values meant to represent the exact same moment can differ by a tiny
# float remainder depending on how each was computed/entered (e.g. a framework's break stored as
# the literal '11.416667' vs a real period's own hour_from computed as '11 + 25/60' ==
# 11.416666666666666) — a strict '<' comparison would misread that hair's-width gap as a real
# overlap. Used by '_get_derived_break_entries' for both the day-span containment check and the
# overlap check; 1/120 hour (30s) safely absorbs that noise without being large enough to treat
# two genuinely distinct, minutes-apart periods as touching.
HOUR_EPSILON = 1 / 120

# Marks write_photo()'s own internal write so hr.employee.write() below skips its own
# guard/push logic for it - otherwise write_photo(employee, ...) writing employee.image_1920
# would re-enter hr.employee.write() with 'image_1920' in vals again, calling write_photo()
# again, forever (RecursionError). Only hr.employee needs this: write_photo() is only ever
# called with an hr.employee or res.partner record (never res.users), and only hr.employee
# has its own write() override that could loop back into write_photo() this way - res.partner
# (models/contacts/contact.py) has no photo-sync logic of its own to re-enter.
EMS_PHOTO_SYNC_CONTEXT_KEY = 'ems_syncing_photo'

_UNSET = object()

# image.mixin's resized copies of image_1920 - each stored as its OWN ir_attachment,
# recomputed automatically whenever image_1920 changes.
_IMAGE_SIZE_FIELDS = ('image_1920', 'image_1024', 'image_512', 'image_256', 'image_128')


def write_photo(record, value):
    """Write `value` into record.image_1920, after deleting every existing image_*
    attachment (1920 down to 128) for this record.

    Odoo never re-detects an ir_attachment's mimetype when overwriting its content in
    place (ir_attachment._inverse_datas computes file_size/checksum/store_fname but never
    touches mimetype - only Model.create() does, via _check_contents). This feature
    writes genuinely different kinds of content into the same fields over time (a real
    photo, or Odoo's own initials-placeholder SVG) - without deleting the old attachments
    first, each one keeps whichever mimetype it had before, and browsers refuse to render
    the new bytes under the stale Content-Type (visible as literal "Binary file" text
    instead of the picture). Deleting them (image_1024/512/256/128 included - they are
    each their own attachment, independently recomputed from image_1920, and independently
    subject to the same stale-mimetype problem) forces every one of them through create()
    on the next write/recompute, which always detects the mimetype fresh."""
    record.env['ir.attachment'].sudo().search([
        ('res_model', '=', record._name),
        ('res_field', 'in', _IMAGE_SIZE_FIELDS),
        ('res_id', 'in', record.ids),
    ]).unlink()
    record.invalidate_recordset(_IMAGE_SIZE_FIELDS)
    raw = record.with_context(**{EMS_PHOTO_SYNC_CONTEXT_KEY: True})
    raw.image_1920 = value
    # image_1024/512/256/128 are related, store=True fields recomputed lazily - only on
    # the next actual read, by whoever that happens to be. Left alone, that read (and the
    # ir_attachment.create() it triggers) could happen well after this call returns, as
    # some other, unprivileged viewer (e.g. the employee themselves opening their own
    # kanban card) - re-triggering ir_attachment._check_contents's SVG-mimetype-forced-to-
    # text/plain restriction for THAT create(), under THEIR privilege level, undoing the
    # work of writing this value under this call's (possibly elevated) one. Reading them
    # now, still as whoever `record` is bound to, forces that create() to happen here
    # instead, once, correctly.
    for field in _IMAGE_SIZE_FIELDS[1:]:
        _ = raw[field]


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
    headed_department_ids = fields.One2many(string="Departments Headed", comodel_name="hr.department", inverse_name="manager_id")
    seminar_department_ids = fields.One2many(string="Seminars Led", comodel_name="hr.department", inverse_name="seminar_head_id")
    directed_company_ids = fields.One2many(string="Companies Directed", comodel_name="res.company", inverse_name="director_id")

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

    def get_derived_break_attendance_data(self):
        """RPC-friendly version of '_get_derived_break_entries()', meant to be fetched
        explicitly by the Schedule tab's widget (orm.call in onWillStart/save, the same
        pattern already used there for 'catalog.subjects'/'get_schedule_hours_summary') —
        deliberately NOT exposed as a form field. An earlier version did exactly that (a
        computed Many2many, hidden, with its own embedded <list> sub-view) and the derived
        break silently never rendered in the widget despite computing correctly server-side
        (proven by the PDF report, which calls the same underlying method directly in
        Python) — an invisible x2many field with its own embedded list doesn't reliably load
        its sub-fields client-side the way a plain Many2one/Boolean field does. Returns
        plain '.read()' dicts (Many2one as a (id, name) tuple, matching the array shape
        'entry.data.non_teaching[1]'/'entry.data.space_id[1]' already expect elsewhere in
        the widget), not 'web_read()' dicts."""
        self.ensure_one()
        return self._get_derived_break_entries().read(
            ['dayofweek', 'hour_from', 'hour_to', 'name', 'non_teaching', 'non_teaching_is_break'])

    def _get_derived_break_entries(self):
        """Fills genuine empty gaps in this teacher's own weekly schedule with a break/patio
        period taken from ANY level's schedule framework — deliberately never tries to guess
        "the" level a teacher belongs to, since a teacher can plausibly teach several levels
        (even within the same day), each with its own break time. For each weekday the
        teacher has at least one real entry (a class, a guard duty, a meeting... anything),
        every candidate break from every framework is checked against that day's own known
        span (earliest hour_from to latest hour_to among the teacher's real entries that
        day) and against every real entry for overlap — a candidate outside that span, or
        overlapping any real entry, is skipped. A gap that doesn't line up with any known
        break simply stays empty; there is no fallback guess. A day with no real entries at
        all has nothing to fill. Two frameworks defining the exact same break (same day and
        hours) collapse into one result, not a visually-duplicated stack."""
        self.ensure_one()
        weekday_entries = self.resource_calendar_id.attendance_ids.filtered(lambda attendance: attendance.dayofweek in WEEKDAYS)
        candidate_breaks = self.env['resource.calendar.attendance'].search([
            ('calendar_id.is_framework', '=', True),
            ('dayofweek', 'in', list(WEEKDAYS)),
            ('non_teaching.is_break', '=', True),
        ])

        breaks = self.env['resource.calendar.attendance']
        seen_slots = set()
        for day in WEEKDAYS:
            day_entries = weekday_entries.filtered(lambda attendance, day=day: attendance.dayofweek == day)
            if not day_entries:
                continue
            day_start = min(day_entries.mapped('hour_from'))
            day_end = max(day_entries.mapped('hour_to'))
            for candidate in candidate_breaks.filtered(lambda attendance, day=day: attendance.dayofweek == day):
                if candidate.hour_from < day_start - HOUR_EPSILON or candidate.hour_to > day_end + HOUR_EPSILON:
                    continue
                overlaps_real_entry = any(
                    min(entry.hour_to, candidate.hour_to) - max(entry.hour_from, candidate.hour_from) > HOUR_EPSILON
                    for entry in day_entries)
                if overlaps_real_entry:
                    continue
                slot = (day, candidate.hour_from, candidate.hour_to)
                if slot in seen_slots:
                    continue
                seen_slots.add(slot)
                breaks |= candidate
        return breaks

    def _get_new_employee_type(self):
        return employee_types
    
    @api.onchange('tutorship_ids')
    def _onchange_tutorship_ids(self):
        self.update_tutor_role()
        self._sync_security_groups()

    @api.depends('department_id')
    def _compute_parent_id(self):
        """Replaces hr.employee.base's native default (department.manager_id for everyone) with
        the Department Chief / Seminar Chief cascade, plus a cross-department cascade for whoever
        chiefs a department themselves (Department Chief of a regular department, or Head of
        Studies/Deputy of a top-level one - see 'ems.department'):

        - Anyone who chiefs ANY department (headed_department_ids) is excluded from every OTHER
          department's own intra-cascade entirely, including their own nominal department_id if
          it differs from what they head (e.g. an employee nominally in "Computer Science" who
          actually heads "VET"). Their own Manager instead comes from whichever headed department
          has a parent department with its own Manager set - that parent's Manager becomes their
          Manager. If a headed department is itself top-level (no parent by definition), the
          company's own Director (res.company.director_id) becomes their Manager instead, unless
          they ARE the Director (self-reference guard, same spirit as the manager_id/seminar_head_id
          one). If none of these applies (no parent chief, no Director set), their own Manager is
          cleared.
        - Otherwise (not chiefing anything): the Seminar Chief's Manager is the Department Chief;
          every other member's Manager is the Seminar Chief, or the Department Chief directly if
          the department has no Seminar Chief.
        """
        for employee in self:
            headed = employee.headed_department_ids
            if headed:
                # Explicitly (re)assigned every time, including to an empty recordset (False) -
                # a transition INTO heading a department (e.g. becoming a top-level Head of
                # Studies with no parent above it yet) must clear whatever manager a PREVIOUS
                # cascade left behind, not silently keep it.
                parent_chief = self.env['hr.employee']
                for department in headed:
                    if department.parent_id and department.parent_id.manager_id:
                        parent_chief = department.parent_id.manager_id
                    elif department.is_top_level:
                        director = department.company_id.director_id
                        if director and director != employee:
                            parent_chief = director
                employee.parent_id = parent_chief
                continue

            department = employee.department_id
            if not department:
                employee.parent_id = False
                continue
            if employee == department.seminar_head_id:
                employee.parent_id = department.manager_id
            elif department.seminar_head_id:
                employee.parent_id = department.seminar_head_id
            else:
                employee.parent_id = department.manager_id

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
        role_dchieff = self.env.ref('ems.role_dchieff').ids[0]
        role_seminar = self.env.ref('ems.role_seminar').ids[0]
        role_hos = self.env.ref('ems.role_hos').ids[0]
        role_dhos = self.env.ref('ems.role_dhos').ids[0]
        role_director = self.env.ref('ems.role_director').ids[0]
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

            is_role_dchieff = role_dchieff in rec.role_ids.ids
            is_department_head = len(rec.headed_department_ids.filtered(lambda d: not d.is_top_level)) > 0
            if is_role_dchieff != is_department_head:
                rec.role_ids = [(4 if is_department_head else 3, role_dchieff)]
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': _("The department chief role cannot be assigned or removed manually, it is set automatically from the department's own form."),
                        'type': 'notification',
                    }
                }

            is_role_seminar = role_seminar in rec.role_ids.ids
            is_seminar_head = len(rec.seminar_department_ids) > 0
            if is_role_seminar != is_seminar_head:
                rec.role_ids = [(4 if is_seminar_head else 3, role_seminar)]
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': _("The Seminar Chief role cannot be assigned or removed manually, it is set automatically from the department's own form."),
                        'type': 'notification',
                    }
                }

            top_level_headed = rec.headed_department_ids.filtered('is_top_level')

            is_role_hos = role_hos in rec.role_ids.ids
            is_hos = len(top_level_headed.filtered(lambda d: d.top_level_role == 'hos')) > 0
            if is_role_hos != is_hos:
                rec.role_ids = [(4 if is_hos else 3, role_hos)]
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': _("The Head of Studies role cannot be assigned or removed manually, it is set automatically from the top-level department's own form."),
                        'type': 'notification',
                    }
                }

            is_role_dhos = role_dhos in rec.role_ids.ids
            is_dhos = len(top_level_headed.filtered(lambda d: d.top_level_role == 'dhos')) > 0
            if is_role_dhos != is_dhos:
                rec.role_ids = [(4 if is_dhos else 3, role_dhos)]
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': _("The Deputy Head of Studies role cannot be assigned or removed manually, it is set automatically from the top-level department's own form."),
                        'type': 'notification',
                    }
                }

            is_role_director = role_director in rec.role_ids.ids
            is_director = len(rec.directed_company_ids) > 0
            if is_role_director != is_director:
                rec.role_ids = [(4 if is_director else 3, role_director)]
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': _("The Director role cannot be assigned or removed manually, it is set automatically from Settings."),
                        'type': 'notification',
                    }
                }
        self._sync_security_groups()

    def update_tutor_role(self):
        role_tutor = self.env.ref('ems.role_tutor').ids[0]
        for rec in self:
            rec.role_ids = [(4 if len(rec.tutorship_ids) > 0 else 3, role_tutor)] # link if tutor, otherwise unlink

    def update_department_head_role(self):
        role_dchieff = self.env.ref('ems.role_dchieff').ids[0]
        for rec in self:
            is_dchieff = len(rec.headed_department_ids.filtered(lambda department: not department.is_top_level)) > 0
            rec.role_ids = [(4 if is_dchieff else 3, role_dchieff)]

    def update_seminar_head_role(self):
        role_seminar = self.env.ref('ems.role_seminar').ids[0]
        for rec in self:
            rec.role_ids = [(4 if len(rec.seminar_department_ids) > 0 else 3, role_seminar)]

    def update_head_of_studies_role(self):
        role_hos = self.env.ref('ems.role_hos').ids[0]
        role_dhos = self.env.ref('ems.role_dhos').ids[0]
        for rec in self:
            top_level_headed = rec.headed_department_ids.filtered('is_top_level')
            is_hos = len(top_level_headed.filtered(lambda department: department.top_level_role == 'hos')) > 0
            is_dhos = len(top_level_headed.filtered(lambda department: department.top_level_role == 'dhos')) > 0
            rec.role_ids = [(4 if is_hos else 3, role_hos), (4 if is_dhos else 3, role_dhos)]

    def update_director_role(self):
        role_director = self.env.ref('ems.role_director').ids[0]
        for rec in self:
            is_director = len(rec.directed_company_ids) > 0
            rec.role_ids = [(4 if is_director else 3, role_director)]

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
        # write_photo() re-enters here to actually store image_1920 (see its own comment) -
        # let that one through untouched, skipping the guard/push logic below entirely.
        if self.env.context.get(EMS_PHOTO_SYNC_CONTEXT_KEY):
            return super().write(vals)

        photo = vals.pop('image_1920', _UNSET)
        if photo is not _UNSET:
            for employee in self:
                if employee.user_id and employee.user_id.image_disabled:
                    raise UserError(_("The profile picture is disabled; it cannot be changed."))

        result = super().write(vals)

        if photo is not _UNSET:
            for employee in self:
                write_photo(employee, photo)

        if 'name' in vals:
            for employee in self:
                if employee.resource_calendar_id and not employee.resource_calendar_id.is_framework:
                    employee.resource_calendar_id.name = employee._personal_calendar_name()

        if photo is not _UNSET:
            for employee in self:
                if employee.user_id:
                    write_photo(employee.user_id.partner_id.sudo(), employee.image_1920)

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
        context for the roles that need it: a tutor's own tutored group(s) ('ems.role_tutor'), a
        department head's own headed department(s) ('ems.role_dchieff'), a Seminar Chief's own
        led department(s) ('ems.role_seminar'), or a Head of Studies/Deputy's own top-level
        department(s) ('ems.role_hos'/'ems.role_dhos'), or the Director's own directed
        company/companies ('ems.role_director')."""
        self.ensure_one()
        role_tutor = self.env.ref('ems.role_tutor', raise_if_not_found=False)
        role_dchieff = self.env.ref('ems.role_dchieff', raise_if_not_found=False)
        role_seminar = self.env.ref('ems.role_seminar', raise_if_not_found=False)
        role_hos = self.env.ref('ems.role_hos', raise_if_not_found=False)
        role_dhos = self.env.ref('ems.role_dhos', raise_if_not_found=False)
        role_director = self.env.ref('ems.role_director', raise_if_not_found=False)
        chief_departments = self.headed_department_ids.filtered(lambda department: not department.is_top_level)
        hos_departments = self.headed_department_ids.filtered(lambda department: department.top_level_role == 'hos')
        dhos_departments = self.headed_department_ids.filtered(lambda department: department.top_level_role == 'dhos')
        lines = []
        for role in self.role_ids:
            label = role.name
            if role_tutor and role == role_tutor and self.tutorship_ids:
                label = "%s: %s" % (label, ", ".join(self.tutorship_ids.mapped('name')))
            elif role_dchieff and role == role_dchieff and chief_departments:
                label = "%s: %s" % (label, ", ".join(chief_departments.mapped('name')))
            elif role_seminar and role == role_seminar and self.seminar_department_ids:
                label = "%s: %s" % (label, ", ".join(self.seminar_department_ids.mapped('name')))
            elif role_hos and role == role_hos and hos_departments:
                label = "%s: %s" % (label, ", ".join(hos_departments.mapped('name')))
            elif role_dhos and role == role_dhos and dhos_departments:
                label = "%s: %s" % (label, ", ".join(dhos_departments.mapped('name')))
            elif role_director and role == role_director and self.directed_company_ids:
                label = "%s: %s" % (label, ", ".join(self.directed_company_ids.mapped('name')))
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