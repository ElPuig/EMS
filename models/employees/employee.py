# -*- coding: utf-8 -*-

import base64

from odoo import SUPERUSER_ID, models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError

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

# Classifies a real entry or a candidate break into "works mornings"/"works afternoons" for
# '_get_derived_break_entries' - computed directly from 'hour_from' rather than trusting the
# stored 'day_period' field, since two different write paths populate that field with two
# different, equally arbitrary thresholds of their own (13h here, matching the Schedule tab
# widget's own 'card.hourFrom < 13' convention in schedule_grid_field.js; 15h in the XML planner
# importer, working_schedule.py's '_parse_schedule_entries') - real data has already been found
# disagreeing with itself at that boundary (a 14:25 entry stored as 'morning' by the importer's
# own rule while genuinely being a teacher's only afternoon work) - not reliable as a single
# source of truth for this classification. Applying ONE consistent rule uniformly to both sides
# of the comparison (a teacher's own entries AND every candidate break) keeps the two immune to
# that pre-existing inconsistency, regardless of what either side's own stored 'day_period' says.
DAY_PERIOD_SPLIT_HOUR = 13

# Marks write_photo()'s own internal write so hr.employee.write() below skips its own
# guard/push logic for it - otherwise write_photo(employee, ...) writing employee.image_1920
# would re-enter hr.employee.write() with 'image_1920' in vals again, calling write_photo()
# again, forever (RecursionError). Only hr.employee needs this: write_photo() is only ever
# called with an hr.employee or res.partner record (never res.users), and only hr.employee
# has its own write() override that could loop back into write_photo() this way - res.partner
# (models/contacts/contact.py) has no photo-sync logic of its own to re-enter.
EMS_PHOTO_SYNC_CONTEXT_KEY = 'ems_syncing_photo'

# Marks a role_ids write coming from one of the 5 internal update_*_role() sync methods below
# (the only legitimate way any of the 7 hierarchy-managed roles may change - see
# check_role_hierarchy() and docs/en/developers/employees/role_hierarchy.md) so
# check_role_hierarchy() skips its own validation for it. Any write NOT carrying this key -
# the employee's own form widget (fixed up first by _onchange_role_ids(), so it never reaches
# the constrains inconsistent in practice), ems.role's own 'employee_ids' reverse field, direct
# write()/API/import/list edit - is validated for real, closing every bypass at once.
EMS_ROLE_SYNC_CONTEXT_KEY = 'ems_syncing_roles'

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
    seminar_department_ids = fields.One2many(string="Seminars Led", comodel_name="hr.department", inverse_name="seminar_chief_id")
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
        # compute_sudo=True (needed so a read-only user can compute this field at all — see
        # the field's own comment) also means `self` runs as superuser here, so
        # self.check_access_rights('write') would always see full rights and this field
        # would always read False regardless of who's actually looking — re-checking
        # against a recordset explicitly bound to the real calling user (self.env.user
        # itself is unaffected by compute_sudo) restores the real per-user answer.
        # _filtered_access, rather than check_access_rights alone, also applies the record rules
        # on top of the model-level ACL: since issue #391 the answer is per record, not per user -
        # the Head of Studies and the TAC coordinator may write a teacher's record but not an ASP
        # one (security/rules/employees.xml). A record still being created carries a NewId, which
        # _check_access deliberately skips the rule pass for, so a brand-new form stays editable.
        writable = self.with_user(self.env.user)._filtered_access('write')
        for employee in self:
            employee.read_only = employee not in writable

    def _compute_can_edit_schedule(self):
        can_edit = self.env.user.has_group('ems.group_department_chief')
        for employee in self:
            employee.can_edit_schedule = can_edit

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
        """Fills this teacher's own weekly schedule with a break/patio period taken from the
        schedule framework(s) of the level(s) they ACTUALLY teach (`teaching_ids.group_id.
        level_id` — kept in sync with the real calendar by `apply_schedule_changes`/
        `sync_from_schedule`, so it reflects what the teacher genuinely teaches right now, not a
        UI convenience field like `source_framework_id`). A teacher spanning several levels whose
        frameworks happen to define the exact same break (e.g. ESO and Batxillerat, at this
        centre) sees it once, same as before — no special-casing needed, the existing per-slot
        dedup below already collapses it; a teacher genuinely spanning DIFFERENT break
        configurations (e.g. ESO and a CCFF program) sees every one of their own relevant
        breaks, still scoped to what they actually teach, never an unrelated program's. Falls
        back to searching EVERY framework, unscoped, only when the teacher has no identifiable
        level at all (no active teaching assignment, or their level(s) have no framework
        configured yet) — the same "no fallback guess beyond an honest best effort" spirit the
        gap/overlap checks below already follow. Developer's own spec (2026-08-11, found via a
        real teacher whose weekly calendar mixed a CCFF program's own break with two unrelated
        ESO breaks that never applied to them): "si el docente solo da clase en CCFF, se muestran
        los patios de CCFF [...] si es de ESO, los patios de la mañana de la ESO [...] si da
        clase en una mezcla [...] debería verse un hueco sin docencia donde encaja un patio."

        Classifies both the teacher's own real entries and every candidate break into "works
        mornings"/"works afternoons" (see DAY_PERIOD_SPLIT_HOUR) using a WHOLE-WEEK span per
        half, not a per-day one: for each half the teacher genuinely works AT ALL during the
        week (on any weekday), every matching break candidate for that half is shown on EVERY
        weekday — including a day the teacher happens to be off entirely. Developer's own spec
        (2026-08-11, replacing an earlier per-day-span design after a real case exposed it: a
        teacher who only ever works afternoons never got their own break shown at all on a day
        their real entries didn't happen to literally span into the break's own hour): "si el
        docente trabaja de mañana, se muestra siempre el patio de la mañana [...] de tarde [...]
        de mañana y tarde, se muestran ambos [...] aunque ese día el docente no trabaje." A break
        candidate is still skipped on any specific day it would overlap one of that day's own
        real entries. A half the teacher never works at all (on any weekday) contributes no
        break. Two frameworks defining the exact same break (same day and hours) collapse into
        one result, not a visually-duplicated stack."""
        self.ensure_one()
        weekday_entries = self.resource_calendar_id.attendance_ids.filtered(lambda attendance: attendance.dayofweek in WEEKDAYS)
        levels = self.teaching_ids.group_id.level_id
        frameworks = self.env['resource.calendar'].search([
            ('is_framework', '=', True), ('level_id', 'in', levels.ids),
        ]) if levels else self.env['resource.calendar']
        candidate_domain = [('dayofweek', 'in', list(WEEKDAYS)), ('non_teaching.is_break', '=', True)]
        candidate_domain.append(('calendar_id', 'in', frameworks.ids) if frameworks else ('calendar_id.is_framework', '=', True))
        candidate_breaks = self.env['resource.calendar.attendance'].search(candidate_domain)

        period_spans = {}
        for is_morning in (True, False):
            period_entries = weekday_entries.filtered(
                lambda attendance, is_morning=is_morning: (attendance.hour_from < DAY_PERIOD_SPLIT_HOUR) == is_morning)
            if period_entries:
                period_spans[is_morning] = (min(period_entries.mapped('hour_from')), max(period_entries.mapped('hour_to')))

        breaks = self.env['resource.calendar.attendance']
        seen_slots = set()
        for day in WEEKDAYS:
            day_entries = weekday_entries.filtered(lambda attendance, day=day: attendance.dayofweek == day)
            for candidate in candidate_breaks.filtered(lambda attendance, day=day: attendance.dayofweek == day):
                span = period_spans.get(candidate.hour_from < DAY_PERIOD_SPLIT_HOUR)
                if not span:
                    continue
                period_start, period_end = span
                if candidate.hour_from < period_start - HOUR_EPSILON or candidate.hour_to > period_end + HOUR_EPSILON:
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

    def _teaching_entries_from_calendar(self):
        """This teacher's current teaching entries, read straight off their own
        'resource_calendar_id.attendance_ids' — the same {'subject_id', 'group_ids', ...} shape
        'ems.teaching.sync_from_schedule()'/'ems.attendance_template.sync_from_schedule_batch()'
        already expect. Extracted from what used to be inline in
        'ems.attendance_template.regenerate_all_from_calendars()' so course transition's own
        teaching resync ('course_transition_wizard._apply_teaching_resync()', added 2026-09-01)
        can reuse the exact same entries without duplicating the dict-building logic — both need
        "what does this teacher's calendar say they teach, right now" as their single source of
        truth. Only rows with a real 'subject_id' count; a non-teaching commitment (guard duty, a
        meeting...) is never a teaching entry."""
        self.ensure_one()
        return [{
            'subject_id': attendance.subject_id.id,
            'group_ids': attendance.group_ids.ids,
            'dayofweek': attendance.dayofweek,
            'hour_from': attendance.hour_from,
            'hour_to': attendance.hour_to,
            'space_id': attendance.space_id.id,
            # 'date_from'/'date_to' — core Odoo's own fields on resource.calendar.attendance,
            # see that model's own NOTE (working_schedule.py) for why they're reused as-is.
            'date_from': attendance.date_from,
            'date_to': attendance.date_to,
        } for attendance in self.resource_calendar_id.attendance_ids if attendance.subject_id]

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
        chiefs a department themselves (Department Chief of a regular department, or Area Manager
        of a top-level one - see 'ems.department'):

        - Anyone who chiefs ANY department (headed_department_ids) is excluded from every OTHER
          department's own intra-cascade entirely, including their own nominal department_id if
          it differs from what they head (e.g. an employee nominally in "Computer Science" who
          actually heads "VET"). Their own Manager instead comes from whichever headed department
          has a parent department - that parent's *effective* Manager (see
          'ems.department._effective_manager()': the nearest ancestor's own Manager, walking up
          through any department that shares its Manager with its parent) becomes their Manager.
          If a headed department is itself top-level (no parent by definition), the company's own
          Director (res.company.director_id) becomes their Manager instead. Either way, a
          candidate that resolves back to the employee themselves is discarded (self-reference
          guard - e.g. someone who is both a top-level Area Manager AND the Department Chief of
          one of its own child departments must never end up as their own Manager). If none of
          these applies (no parent chief, no Director set, or the only candidate was themselves),
          their own Manager is cleared.
        - Otherwise (not chiefing anything): the Seminar Chief's Manager is the Department Chief
          (or, if the department has no Manager of its own, whichever ancestor's Manager it
          resolves to via 'ems.department._effective_manager()'); every other member's Manager is
          the Seminar Chief, or that same effective Manager if the department has no Seminar Chief.
        """
        for employee in self:
            headed = employee.headed_department_ids
            if headed:
                # Explicitly (re)assigned every time, including to an empty recordset (False) -
                # a transition INTO heading a department (e.g. becoming a top-level Area Manager
                # with no parent above it yet) must clear whatever manager a PREVIOUS cascade
                # left behind, not silently keep it.
                parent_chief = self.env['hr.employee']
                for department in headed:
                    if department.is_top_level:
                        candidate = department.company_id.director_id
                    elif department.parent_id:
                        candidate = department.parent_id._effective_manager()
                    else:
                        candidate = self.env['hr.employee']
                    if candidate and candidate != employee:
                        parent_chief = candidate
                employee.parent_id = parent_chief
                continue

            department = employee.department_id
            if not department:
                employee.parent_id = False
                continue
            if employee == department.seminar_chief_id:
                employee.parent_id = department._effective_manager()
            elif department.seminar_chief_id:
                employee.parent_id = department.seminar_chief_id
            else:
                employee.parent_id = department._effective_manager()

    @api.depends("tutorship_ids")
    def _compute_tutorships_str(self):
        for employee in self:
            employee.tutorships = ""
            for tutorship in employee.tutorship_ids:
                employee.tutorships = "%s, %s" % (employee.tutorships, tutorship.name)
            employee.tutorships = employee.tutorships.lstrip(", ")

    @api.depends("role_ids")
    def _compute_roles_str(self):
        for employee in self:
            employee.roles = ""
            for role in employee.role_ids:
                employee.roles = "%s, %s" % (employee.roles, role.name)
            employee.roles = employee.roles.lstrip(", ")
    
    @api.onchange('job_id')
    def _onchange_job_id(self):
        self._sync_security_groups()

    def _ems_role_hierarchy_truth(self):
        """Returns a (role, should_be_assigned, message) tuple per hierarchy-managed role (the
        7 roles whose role_ids membership is derived entirely from department/company/group
        data via update_tutor_role()/update_department_head_role()/update_seminar_chief_role()/
        update_area_manager_role()/update_director_role(), never a legitimate manual edit - see
        docs/en/developers/employees/role_hierarchy.md). Single source of truth for
        '_onchange_role_ids' (in-form UX, below) and 'check_role_hierarchy' (the real
        server-side barrier)."""
        self.ensure_one()
        top_level_headed = self.headed_department_ids.filtered('is_top_level')
        return [
            (self.env.ref('ems.role_tutor'), len(self.tutorship_ids) > 0,
             _("The tutor role cannot be assigned manually, it will be set automatically if any group is added to the 'tutorship' field.")),
            (self.env.ref('ems.role_dchieff'), len(self.headed_department_ids.filtered(lambda d: not d.is_top_level)) > 0,
             _("The department chief role cannot be assigned or removed manually, it is set automatically from the department's own form.")),
            (self.env.ref('ems.role_seminar'), len(self.seminar_department_ids) > 0,
             _("The Seminar Chief role cannot be assigned or removed manually, it is set automatically from the department's own form.")),
            (self.env.ref('ems.role_hos'), len(top_level_headed.filtered(lambda d: d.top_level_role == 'hos')) > 0,
             _("The Head of Studies role cannot be assigned or removed manually, it is set automatically from the top-level department's own form.")),
            (self.env.ref('ems.role_dhos'), len(top_level_headed.filtered(lambda d: d.top_level_role == 'dhos')) > 0,
             _("The Deputy Head of Studies role cannot be assigned or removed manually, it is set automatically from the top-level department's own form.")),
            (self.env.ref('ems.role_secretary'), len(top_level_headed.filtered(lambda d: d.top_level_role == 'secretary')) > 0,
             _("The Secretary role cannot be assigned or removed manually, it is set automatically from the top-level department's own form.")),
            (self.env.ref('ems.role_director'), len(self.directed_company_ids) > 0,
             _("The Director role cannot be assigned or removed manually, it is set automatically from Settings.")),
        ]

    @api.onchange('role_ids')
    def _onchange_role_ids(self):
        for employee in self:
            # Each correction below is itself a role_ids write, immediately re-validated by
            # check_role_hierarchy() - including outside a real Form()-driven onchange (e.g.
            # this method called directly, as several tests do). Marking every correction as
            # a trusted internal sync (like the 5 update_*_role() methods) is what lets ALL
            # mismatches get fixed within this same pass instead of the first correction's own
            # write raising because a LATER role is still mismatched at that intermediate
            # moment - each correction, by construction, only ever moves a role TOWARD its
            # computed truth, so this is safe unconditionally.
            synced = employee.with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True})
            truth = employee._ems_role_hierarchy_truth()
            role_tutor, is_tutor, tutor_message = truth[0]
            messages = []

            # Tutor is special-cased: removing the tag while tutorship_ids is still non-empty
            # cascades into clearing every tutorship instead of reverting the tag - the
            # employee genuinely stops tutoring, rather than being blocked from removing it.
            is_role_tutor = role_tutor.id in employee.role_ids.ids
            if not is_role_tutor and is_tutor:
                synced.tutorship_ids = False
            elif is_role_tutor and not is_tutor:
                synced.role_ids = [(3, role_tutor.id)]
                messages.append(tutor_message)

            # The remaining 6 all follow the same revert-and-warn pattern. Every one is
            # checked in this same pass (no early return) so a save with more than one role
            # simultaneously out of sync gets ALL of them corrected together, not just the
            # first one found.
            for role, should_be_assigned, message in truth[1:]:
                is_assigned = role.id in employee.role_ids.ids
                if is_assigned != should_be_assigned:
                    synced.role_ids = [(4 if should_be_assigned else 3, role.id)]
                    messages.append(message)

            if messages:
                return {
                    'warning': {
                        'title': _("Not allowed"),
                        'message': "\n".join(messages),
                        'type': 'notification',
                    }
                }
        self._sync_security_groups()

    @api.constrains('role_ids')
    def check_role_hierarchy(self):
        """The real, server-side barrier behind '_onchange_role_ids' (in-form UX only, above):
        fires on every write()/create(), from any path (ems.role's own 'employee_ids' reverse
        field, direct write(), API, import, list edit included) - not just the employee form's
        own tag widget. EMS_ROLE_SYNC_CONTEXT_KEY marks the one legitimate way any of these 7
        roles may change (the 5 update_*_role() methods below); everything else is held to the
        same department/company/group-derived truth."""
        if self.env.context.get(EMS_ROLE_SYNC_CONTEXT_KEY):
            return
        for employee in self:
            messages = []
            for role, should_be_assigned, message in employee._ems_role_hierarchy_truth():
                is_assigned = role.id in employee.role_ids.ids
                if is_assigned != should_be_assigned:
                    messages.append(message)
            if messages:
                raise ValidationError("\n".join(messages))

    def update_tutor_role(self):
        role_tutor = self.env.ref('ems.role_tutor').ids[0]
        for employee in self:
            synced = employee.with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True})
            synced.role_ids = [(4 if len(employee.tutorship_ids) > 0 else 3, role_tutor)] # link if tutor, otherwise unlink

    def update_department_head_role(self):
        role_dchieff = self.env.ref('ems.role_dchieff').ids[0]
        for employee in self:
            is_dchieff = len(employee.headed_department_ids.filtered(lambda department: not department.is_top_level)) > 0
            synced = employee.with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True})
            synced.role_ids = [(4 if is_dchieff else 3, role_dchieff)]

    def update_seminar_chief_role(self):
        role_seminar = self.env.ref('ems.role_seminar').ids[0]
        for employee in self:
            synced = employee.with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True})
            synced.role_ids = [(4 if len(employee.seminar_department_ids) > 0 else 3, role_seminar)]

    def update_area_manager_role(self):
        role_hos = self.env.ref('ems.role_hos').ids[0]
        role_dhos = self.env.ref('ems.role_dhos').ids[0]
        role_secretary = self.env.ref('ems.role_secretary').ids[0]
        for employee in self:
            top_level_headed = employee.headed_department_ids.filtered('is_top_level')
            is_hos = len(top_level_headed.filtered(lambda department: department.top_level_role == 'hos')) > 0
            is_dhos = len(top_level_headed.filtered(lambda department: department.top_level_role == 'dhos')) > 0
            is_secretary = len(top_level_headed.filtered(lambda department: department.top_level_role == 'secretary')) > 0
            synced = employee.with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True})
            synced.role_ids = [
                (4 if is_hos else 3, role_hos),
                (4 if is_dhos else 3, role_dhos),
                (4 if is_secretary else 3, role_secretary),
            ]

    def update_director_role(self):
        role_director = self.env.ref('ems.role_director').ids[0]
        for employee in self:
            is_director = len(employee.directed_company_ids) > 0
            synced = employee.with_context(**{EMS_ROLE_SYNC_CONTEXT_KEY: True})
            synced.role_ids = [(4 if is_director else 3, role_director)]

    def _sync_security_groups(self):
        """Sync res.users.groups_id based on role_ids and job_id that have a linked security group."""
        role_groups = self.env['ems.role'].sudo().search([('group_id', '!=', False)]).mapped('group_id')
        job_groups = self.env['hr.job'].sudo().search([('group_id', '!=', False)]).mapped('group_id')
        managed_groups = role_groups | job_groups
        if not managed_groups:
            return
        for employee in self:
            sudo_employee = self.env['hr.employee'].sudo().search([('id', '=', employee.id)], limit=1)
            if not sudo_employee or not sudo_employee.user_id:
                continue
            should_have = employee.role_ids.mapped('group_id') | employee.job_id.group_id
            commands = []
            for g in managed_groups:
                if g in should_have and g not in sudo_employee.user_id.groups_id:
                    commands.append((4, g.id))
                elif g not in should_have and g in sudo_employee.user_id.groups_id:
                    commands.append((3, g.id))
            if commands:
                sudo_employee.user_id.sudo().write({'groups_id': commands})

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
        for employee in self:
            for role in employee.role_ids:
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

    schedule_import_code = fields.Char(
        string="Schedule import code", copy=False,
        help="Raw placeholder code (e.g. 'X1') from a working-schedule import, kept only "
             "while the teacher's real identity is still unknown.")
    pending_identification = fields.Boolean(
        string="Pending identification", compute="_compute_pending_identification", store=True,
        help="A schedule was imported for this teacher before their real identity was known.")

    # Feeds the shared 'ems_archived_reason_ribbon' field widget (form + kanban, same widget
    # used by res.partner - see static/src/js/backend/archived_reason_ribbon_field.js). Every
    # departure reason is ribbon-worthy here (unlike res.partner.contact_type, which needs its
    # own compute to filter down to just alumni/withdrawal/expelled), so a plain related=
    # suffices - see docs/en/developers/employees/employee.md.
    archived_reason_label = fields.Char(
        string="Archived reason", related="departure_reason_id.name",
        groups="hr.group_hr_user,ems.group_teacher")
    archived_reason_color = fields.Char(
        string="Archived reason color", related="departure_reason_id.color",
        groups="hr.group_hr_user,ems.group_teacher")

    @api.depends("schedule_import_code")
    def _compute_pending_identification(self):
        for employee in self:
            employee.pending_identification = bool(employee.schedule_import_code)

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        # NOTE: every teacher gets their OWN calendar, always — 'resource_calendar_id' arrives
        # already pre-filled by resource.mixin's client-side default (the company's shared
        # calendar), so it can never be used to detect "nothing was set yet". Sharing a calendar
        # between teachers would break the 1:1 assumption 'apply_schedule_changes' relies on.
        # See '_ems_create_personal_calendar' for why this is a shared method, not inline here.
        employees._ems_create_personal_calendar()
        return employees

    def _ems_create_personal_calendar(self):
        """Creates and assigns a personal 'resource.calendar' for every teacher in 'self' that
        doesn't already have their OWN one - shared between create() (every new teacher, above)
        and the one-time backfill for a teacher that predates create()'s own auto-calendar
        override (added commit bc29e04b, 18.0.0.20.0, 2026-07-12 - see '__init__.py's
        'post_init_hook' and 'migrations/18.0.0.22.0/post-migrate.py' for the two backfill call
        sites this same method feeds, and 'plans/calendar_driven_attendance_templates.md' for the
        real import bug that surfaced the gap). 'employee_id'/'course_id' (added 2026-08-06) make
        the new calendar a permanent, queryable historical record on its own terms - see
        plans/course_transition_teacher_schedule_archival.md. 'name' is auto-derived from them by
        'resource.calendar's own create() override - no name string built here by hand.

        Deliberately NOT 'not employee.resource_calendar_id' - 'resource.mixin.resource_calendar_id'
        carries a field-level 'default=lambda self: self.env.company.resource_calendar_id', which
        applies on EVERY create() (server-side calls included, not just through a view), so a
        brand-new teacher already arrives with a truthy (but shared, non-personal)
        'resource_calendar_id' before this method ever runs - a plain truthiness check would
        silently skip them, leaving them sharing the company's own calendar (found the hard way
        while testing this method: two teachers created back-to-back ended up on the exact same
        calendar, tripping 'apply_schedule_changes' co-teaching and getting a
        'ValueError: Expected singleton' from 'get_employee()'s own reverse-search fallback).
        Checking 'employee_id != employee' instead correctly tells apart "no calendar at all"
        (backfill's real scenario) and "the shared company default" (create()'s own scenario) from
        "a genuine pre-existing PERSONAL calendar" (skipped, matching a personal calendar's own
        'employee_id' back-reference, set by this same method) - safe to call on any recordset
        mixing all three cases."""
        for employee in self.filtered(lambda employee: employee.employee_type == 'teacher' and employee.resource_calendar_id.employee_id != employee):
            schedule = self.env['resource.calendar'].create({
                'employee_id': employee.id,
                'course_id': employee.company_id.current_course_id.id,
            })
            schedule.seed_from_framework(employee.company_id.default_schedule_framework_id)
            employee.resource_calendar_id = schedule

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
                employee.resource_calendar_id._refresh_personal_name()
            self._refresh_stale_avatar_placeholder()

        if photo is not _UNSET:
            for employee in self:
                if employee.user_id:
                    write_photo(employee.user_id.partner_id.sudo(), employee.image_1920)

        return result

    def _refresh_stale_avatar_placeholder(self):
        """Regenerate the initials placeholder for any employee in `self` whose
        `image_1920` already holds a self-generated SVG, so a rename doesn't leave it
        showing the OLD initial.

        Two, otherwise unrelated, code paths bake a real SVG into the normally-empty
        `image_1920` instead of leaving it to the live `avatar.mixin` compute the rest
        of the app relies on: native Odoo's own `hr.employee.create()` (every new
        employee with no photo, teacher/ASP or not - includes every pending-
        identification teacher, always created with a placeholder name that is renamed
        later during Google account creation) and this module's own "Disable profile
        picture" (`res.users.image_disabled`, see `user.py`). Both always use
        `_avatar_generate_svg()`, which always produces SVG - and `fields.Image`'s
        upload pipeline (PIL-based) cannot store a genuinely uploaded SVG photo, so
        sniffing the content this way never risks overwriting a real photo.

        Deliberately generates from the EMPLOYEE's own (just-changed) name rather than
        delegating to user.py's own `_refresh_photo_placeholder()` (which sources the
        linked partner's name instead) - the two can differ, and it is the employee's
        name that just changed here.
        """
        stale = self.filtered(
            lambda employee: employee.image_1920
            and base64.b64decode(employee.image_1920).lstrip().startswith(b'<?xml'))
        for employee in stale:
            # with_user(SUPERUSER_ID): see user.py's _refresh_photo_placeholder for why
            # a plain .sudo() does not, on its own, clear ir_attachment's SVG-mimetype-
            # forced-to-text/plain check - without it, whoever renamed this employee
            # (not necessarily privileged enough to write ir.ui.view) would get a
            # mislabeled attachment the browser refuses to render as an image.
            synced = employee.with_user(SUPERUSER_ID)
            placeholder = synced._avatar_generate_svg()
            write_photo(synced, placeholder)
            if employee.user_id:
                write_photo(employee.user_id.sudo().with_user(SUPERUSER_ID).partner_id, placeholder)

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

    def action_mark_as_identified(self):
        """Manually clear the pending-identification placeholder.

        Covers the case where a teacher was created from a schedule-import
        placeholder code (X1/X2...) but will never get a Google Workspace/EMS
        account created through this employee record (e.g. already has one on
        a different, unmerged record; or genuinely doesn't need one) - the
        only other way pending_identification is cleared is as a side effect
        of a Google account actually being created/adopted (see
        google_workspace_integration.py's _gw_clear_pending_identification).
        Idempotent: does nothing if the employee is not pending.
        """
        for employee in self:
            if not employee.schedule_import_code:
                continue
            employee.message_post(body=_(
                "Identity confirmed manually: this employee was created as a "
                "pending-identification placeholder from schedule-import code '%s'."
            ) % employee.schedule_import_code)
            employee.schedule_import_code = False

    def get_report_role_lines(self):
        """One display line per role_ids entry for the working-schedule PDF header, appending
        context for the roles that need it: a tutor's own tutored group(s) ('ems.role_tutor'), a
        department head's own headed department(s) ('ems.role_dchieff'), a Seminar Chief's own
        led department(s) ('ems.role_seminar'), or an Area Manager's own top-level department(s)
        ('ems.role_hos'/'ems.role_dhos'/'ems.role_secretary'), or the Director's own directed
        company/companies ('ems.role_director')."""
        self.ensure_one()
        role_tutor = self.env.ref('ems.role_tutor', raise_if_not_found=False)
        role_dchieff = self.env.ref('ems.role_dchieff', raise_if_not_found=False)
        role_seminar = self.env.ref('ems.role_seminar', raise_if_not_found=False)
        role_hos = self.env.ref('ems.role_hos', raise_if_not_found=False)
        role_dhos = self.env.ref('ems.role_dhos', raise_if_not_found=False)
        role_secretary = self.env.ref('ems.role_secretary', raise_if_not_found=False)
        role_director = self.env.ref('ems.role_director', raise_if_not_found=False)
        chief_departments = self.headed_department_ids.filtered(lambda department: not department.is_top_level)
        hos_departments = self.headed_department_ids.filtered(lambda department: department.top_level_role == 'hos')
        dhos_departments = self.headed_department_ids.filtered(lambda department: department.top_level_role == 'dhos')
        secretary_departments = self.headed_department_ids.filtered(lambda department: department.top_level_role == 'secretary')
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
            elif role_secretary and role == role_secretary and secretary_departments:
                label = "%s: %s" % (label, ", ".join(secretary_departments.mapped('name')))
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