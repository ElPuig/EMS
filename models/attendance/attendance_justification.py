# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _lt

JUSTIFICATION_CAPTION = _lt("Absence justified by: ")
SEVERE_DELAY_CAPTION = _lt("Severe delay justified by: ")
PREVISION_CAPTION = _lt("Absence expected by: ")

# Written by the system, never by the user: a session linking its lines to a justification (and
# the affected teachers that link recomputes). Every other change needs the tutor's permission.
SYSTEM_FIELDS = {'attendance_session_line_ids', 'session_teacher_ids'}


class EmsAttendanceJustification(models.Model):
    """A proof of attendance covering a period, shared by one or several students (issue #795:
    a strike, a competition), with a single reason, notes and set of files."""
    _name = "ems.attendance_justification"
    _description = "Attendance justification: contains the data about an abscence justification (proof of attendance)."
    _inherit = ['ems.base', 'ems.datetime_utils', 'ems.attachment_mixin']

    start_date = fields.Datetime(string="Start date", required=True)
    end_date = fields.Datetime(string="End date", required=True)
    teacher_id = fields.Many2one(string="Justified by", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True, ondelete='cascade')
    student_ids = fields.Many2many(
        string="Students", comodel_name="res.partner", relation="ems_attendance_justification_student_rel",
        column1="justification_id", column2="student_id", domain="[('contact_type', '=', 'student')]",
        required=True)
    attachment_ids = fields.Many2many(string="Attached files", comodel_name="ir.attachment", domain="[('res_model', '=', 'ems.attendance_justification')]")

    # NOTE: Many2many needed in order to update values (when Many2one used, removed values when changing filters removes also the status entries).
    # NOTE: relation name should be forced to <63 chars (PSQL restriction).
    attendance_session_line_ids = fields.Many2many(string="Affected sessions", comodel_name="ems.attendance_session_line")
    session_teacher_ids = fields.Many2many(string="Affected teachers", comodel_name="hr.employee", compute='_compute_session_teacher_ids', store=True, readonly=False)
    # Issue #795 (follow-up): why the absences are justified. The first reason by sequence (health)
    # is the default; "Other" asks for details, "Strike" covers the student's whole day.
    reason_id = fields.Many2one(
        string="Reason", comodel_name="ems.attendance_justification_reason", required=True,
        ondelete='restrict', default=lambda self: self._default_reason_id())
    requires_details = fields.Boolean(related='reason_id.requires_details')
    full_day = fields.Boolean(related='reason_id.full_day')
    details = fields.Text(string="Details")
    notes = fields.Text("Notes")
    # A full-day reason picks one day: the period becomes that whole day, in the company's timezone.
    day = fields.Date(string="Day", compute='_compute_day', inverse='_inverse_day')

    # Form helpers, never stored.
    # Picking groups adds their students to the list, then clears itself (_onchange_add_group_ids).
    add_group_ids = fields.Many2many(
        string="Add groups", comodel_name="ems.group", store=False,
        help="Adds every student of these groups to the list. Remove afterwards the ones who must not be justified.")
    # The pickers' domains, as text: for an administrator the allowed students are the whole
    # centre, too many ids to send to the browser.
    student_domain = fields.Char(compute='_compute_domains')
    group_domain = fields.Char(compute='_compute_domains')
    overlap_student_ids = fields.Many2many(
        string="Already justified", comodel_name="res.partner", compute='_compute_overlap_student_ids')
    student_summary = fields.Char(string="Students (summary)", compute='_compute_student_summary')

    @api.depends('attendance_session_line_ids')
    def _compute_session_teacher_ids(self):
        for justification in self:
            tt_id = justification.attendance_session_line_ids.mapped('attendance_session_id.template_teacher_ids.id')
            st_id = justification.attendance_session_line_ids.mapped('attendance_session_id.session_teacher_id.id')
            regs = list(set(tt_id + st_id))

            # Storing both sets but removing dupes
            justification.session_teacher_ids = [(6, 0, regs)]

    @api.depends('teacher_id')
    def _compute_domains(self):
        # The students (and main groups) of every group the justifying teacher acts as tutor of:
        # their own, or those of the tutors below them (hr.employee.tutor_scope_user_ids, issue #483).
        is_admin = self.get_user_is_admin()
        for justification in self:
            student_domain = [('contact_type', '=', 'student')]
            group_domain = [('group_type', '=', 'main')]
            if not is_admin:
                user_id = justification.teacher_id.user_id.id
                student_domain.append(('main_group_id.tutor_id.tutor_scope_user_ids', '=', user_id))
                group_domain.append(('tutor_id.tutor_scope_user_ids', '=', user_id))
            justification.student_domain = str(student_domain)
            justification.group_domain = str(group_domain)

    @api.depends('student_ids', 'start_date', 'end_date')
    def _compute_overlap_student_ids(self):
        for justification in self:
            justification.overlap_student_ids = justification._overlapping_students(justification.student_ids._origin)

    @api.depends('student_ids')
    def _compute_student_summary(self):
        for justification in self:
            students = justification.student_ids
            justification.student_summary = students.name if len(students) == 1 else (
                _("%s students", len(students)) if students else False)

    @api.depends('start_date')
    def _compute_day(self):
        for justification in self:
            justification.day = justification.start_date and justification.utc_to_local_date(justification.start_date)

    def _inverse_day(self):
        # Only for a full-day reason: otherwise the day just follows the period's start (the form
        # sends it back on save) and must not turn the period into a whole day. One write: the
        # constraints must see both dates changed.
        for justification in self._with_full_day():
            justification.write(justification._whole_day_vals(justification.day))

    def _with_full_day(self):
        return self.filtered(lambda justification: justification.day and justification.full_day)

    def _whole_day_vals(self, day):
        """The period of a whole local day, as naive UTC datetimes (from 00:00 to 23:59:59)."""
        start = self.time_float_to_utc_datetime(day, 0.0)
        end = self.time_float_to_utc_datetime(day + timedelta(days=1), 0.0) - timedelta(seconds=1)
        return {'start_date': self.datetime_to_odoo(start), 'end_date': self.datetime_to_odoo(end)}

    def _default_reason_id(self):
        return self.env['ems.attendance_justification_reason'].search([], limit=1)

    def _default_teacher_id(self):
        return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

    @api.constrains('student_ids', 'start_date', 'end_date')
    def _check_time_overlap(self):
        for justification in self:
            if not justification.student_ids:
                raise ValidationError(_("A justification needs at least one student."))
            if justification.start_date >= justification.end_date:
                raise ValidationError(_("The completion date must be later than the start date."))
            overlapping = justification._overlapping_students(justification.student_ids)
            if overlapping:
                raise ValidationError(_(
                    "These students have another justification which overlaps with the current one: %(students)s",
                    students=", ".join(overlapping.mapped('name'))))

    @api.constrains('reason_id', 'details')
    def _check_details(self):
        for justification in self:
            if justification.requires_details and not (justification.details or '').strip():
                raise ValidationError(_("Describe the reason in the details: %(reason)s", reason=justification.reason_id.name))

    @api.constrains('reason_id', 'start_date', 'end_date')
    def _check_full_day(self):
        for justification in self.filtered('full_day'):
            period = {'start_date': justification.start_date, 'end_date': justification.end_date}
            if period != justification._whole_day_vals(justification.day):
                raise ValidationError(_("A justification for %(reason)s covers one whole day: pick the day.",
                                        reason=justification.reason_id.name))

    @api.onchange('day', 'reason_id')
    def _onchange_day(self):
        # A full-day reason: the period becomes the whole day picked (or the one it started on).
        for justification in self._with_full_day():
            justification.update(justification._whole_day_vals(justification.day))

    @api.onchange('reason_id')
    def _onchange_reason_id(self):
        for justification in self.filtered(lambda justification: not justification.requires_details):
            justification.details = False

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        # Only tutors (and administrators) justify: every other teacher reads the justifications
        # covering their sessions, without New, Edit or Delete, which create()/write()/unlink()
        # would refuse anyway (their ACL is the teachers' one).
        result = super().get_view(view_id, view_type, **options)
        if self.get_user_is_admin() or self.get_user_is_tutor():
            return result
        return self.view_without_operations(
            result, ['ems.view_attendance_justification_list', 'ems.view_attendance_justification_form'],
            ('create', 'edit', 'delete'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "user_is_admin" in fields_list and  "user_is_tutor" in fields_list:
            # This happens when opening the form, when storing fires again but field per field
            if not (res["user_is_admin"] or res["user_is_tutor"]):
                raise UserError(_("Only tutors can justify student's attendances."))
        return res

    @api.onchange('add_group_ids')
    def _onchange_add_group_ids(self):
        for justification in self:
            if not justification.add_group_ids:
                continue
            students = self.env['res.partner'].search([
                ('contact_type', '=', 'student'),
                ('main_group_id', 'in', justification.add_group_ids._origin.ids),
            ]) - justification.student_ids._origin
            # A student already justified over this period would block saving: not added, and told.
            skipped = justification._overlapping_students(students)
            justification.student_ids |= students - skipped
            justification.add_group_ids = False
            if skipped:
                return {'warning': {
                    'title': _("Students not added"),
                    'message': _(
                        "They already have a justification overlapping this period: %(students)s",
                        students=", ".join(skipped.mapped('name'))),
                }}

    @api.model
    def _justifiable_lines(self, students, start_date, end_date):
        """The session lines the period covers, per student id: what a justification of these
        students over that period links. One search for every student (a justification can cover
        whole groups, issues #656 and #795)."""
        # NOTE: Because changing dates is allowed, already justified abscences must be included
        # 		(already justified will fail due overlapping check).
        # NOTE: sudo() for the students' tutor (or an admin): most sessions within the period are
        #       taught by other teachers, whose headers the teacher record rules hide - the search
        #       below filters on them, so it silently skipped those absences (issue #469).
        lines = self.env["ems.attendance_session_line"]
        if self._user_may_justify(students):
            lines = lines.sudo()
        # A severe delay counts as an absence, so it can be justified too (issue #578); a
        # mild delay only when it is one already justified (a justified severe delay).
        found = lines.search([
            '|',
            ("status_id", "in", [self.env.ref(f"ems.attendance_status_{key}").id for key in ("miss", "delayed_severe", "justified")]),
            '&',
            ("status_id", "=", self.env.ref("ems.attendance_status_delayed").id),
            ("attendance_justification_id", "!=", False),
            ("student_id", "in", students.ids),
            ("attendance_session_id.date", ">=", start_date),
            ("attendance_session_id.date", "<=", end_date)
        ])
        result = {student.id: self.env["ems.attendance_session_line"] for student in students}
        for line in found:
            session = line.attendance_session_id
            if not (session.end_date <= start_date or end_date < session.start_date):
                result[line.student_id.id] |= line.sudo(False)
        return result

    def _covered_lines(self):
        """Every session line this justification covers, for all its students."""
        self.ensure_one()
        students = self.student_ids._origin
        if not (students and self.start_date and self.end_date):
            return self.env["ems.attendance_session_line"]
        lines = self._justifiable_lines(students, self.start_date, self.end_date)
        return self.env["ems.attendance_session_line"].union(*lines.values())

    # NOTE: only fired from the form, to preview the affected sessions before saving.
    @api.onchange("student_ids", "start_date", "end_date")
    def _onchange_attendance_session_line_ids(self):
        for justification in self:
            justification.attendance_session_line_ids = [(6, 0, justification._covered_lines().ids)]

    @api.depends('student_ids', 'start_date', 'end_date')
    def _compute_display_name(self):
        for justification in self:
            if not (justification.student_ids and justification.start_date and justification.end_date):
                justification.display_name = False
                continue
            start = justification.utc_datetime_to_local(justification.start_date)
            end = justification.utc_datetime_to_local(justification.end_date)
            hours = {'start': f"{start.hour:02d}:{start.minute:02d}", 'end': f"{end.hour:02d}:{end.minute:02d}"}
            justification.display_name = _(
                "%(students)s (from %(start)s to %(end)s)", students=justification.student_summary, **hours)

    def _overlapping_students(self, students):
        """Those of `students` already holding another justification that overlaps this one's
        period. sudo: an overlap the user cannot read (another tutor's) still counts."""
        self.ensure_one()
        if not (students and self.start_date and self.end_date):
            return self.env['res.partner']
        others = self.sudo().search([
            ('student_ids', 'in', students.ids),
            ('id', '!=', self._origin.id),
            ('start_date', '<', self.end_date),
            ('end_date', '>', self.start_date),
        ])
        return (others.student_ids & students).sudo(False)

    def _user_may_justify(self, students):
        """An administrator, or someone acting as tutor of every one of these students: their own
        tutor, or a Head of Studies/Director above them (tutor_scope_user_ids, issue #483)."""
        if self.env.su or self.get_user_is_admin():
            return True
        if not students or students.filtered(lambda student: not student.tutor_id):
            return False
        # Checked once per tutor: a whole group shares one.
        return all(self.user_acts_as_tutor(tutor) for tutor in students.tutor_id)

    def _check_permissions(self, message):
        if not self._user_may_justify(self.student_ids):
            raise UserError(message)

    @api.model
    def get_current_justification_by_student(self, start_date, end_date):
        """The justification covering each student over that period, by student id (previsions).
        sudo: the teacher taking the roll-call usually can't read the tutor's justification yet."""
        justifications = self.sudo().search([("start_date", "<", end_date), ("end_date", ">", start_date)])
        return {student.id: justification for justification in justifications for student in justification.student_ids}

    # NOTE: 'vals' must already be plain ems.attendance_session_line create()/write() vals - the
    # caller normalizes an existing record via its own 'ems.attendance_session_line._justification_
    # vals()' before calling this, this method never branches on the caller's own shape.
    def perform_justification(self, vals, prevision=False):
        vals = dict(vals)

        # A severe delay counts as an absence: justifying it turns it into a mild delay, so the
        # student is still recorded as having attended late (issue #578).
        severe_delay = not prevision and vals.get("status_id") == self.env.ref("ems.attendance_status_delayed_severe").id
        if severe_delay:
            text = SEVERE_DELAY_CAPTION
            status = self.env.ref("ems.attendance_status_delayed")
        else:
            text = PREVISION_CAPTION if prevision else JUSTIFICATION_CAPTION
            status = self.env.ref("ems.attendance_status_justified")
        notes = "" if vals["notes"] is None or vals["notes"] == False else vals["notes"] + "\n"

        # Must ensure that no field is beeing removed, just edited, otherwise line creation could fail if called from attendance_session.
        vals["status_id"] = status.id
        vals["notes"] = notes + text + self.teacher_id.display_name
        vals["attendance_prevision_id" if prevision else "attendance_justification_id"] = self
        return vals

    def remove_justification(self, line):
        # Given an attendance_session_line, changes the values to remove a justification (does not write).
        # NOTE: this method uses always line as a model, removing a justification always work with already existing lines.
        # A justified severe delay (now a mild one) goes back to being a severe delay.
        delayed = line.status_id == self.env.ref("ems.attendance_status_delayed")
        return {
            "status_id": self.env.ref("ems.attendance_status_delayed_severe" if delayed else "ems.attendance_status_miss").id,
            "notes": False,
            "attendance_justification_id": None,
            "attendance_prevision_id": None
        }

    @api.model_create_multi
    def create(self, vals_list):
        # NOTE: don't worry, wont be saved if there's an exception (wihtin transaction)
        for vals in vals_list:
            # A full-day reason created from code with only the day: the period is that whole day
            # (the form already sends both, from _onchange_day). The NOT NULL columns can't wait for
            # the inverse, which runs after the insert.
            if vals.get('day') and not vals.get('start_date'):
                vals.update(self._whole_day_vals(fields.Date.to_date(vals.pop('day'))))
        records = super().create(vals_list)
        unjustified = self.env.ref("ems.attendance_status_miss") | self.env.ref("ems.attendance_status_delayed_severe")
        for justification, vals in zip(records, vals_list):
            justification._check_permissions(_("Only the student's tutor can justify its attendances."))
            if 'attendance_session_line_ids' not in vals:
                justification.attendance_session_line_ids = justification._covered_lines()
            for line in justification.attendance_session_line_ids:
                if line.status_id in unjustified:
                    line.write(justification.perform_justification(line._justification_vals()))
        return records

    def write(self, vals):
        message = _("Only the student's tutor can update its attendance justifications.")
        # A session linking its lines is system bookkeeping (issue #432): no permission check, and
        # no read of attendance_session_line_ids, which the record rules may refuse.
        by_user = bool(set(vals) - SYSTEM_FIELDS)
        if by_user:
            # Both before (the students taken out) and after (the ones added).
            self._check_permissions(message)
        lines_change = bool({'start_date', 'end_date', 'student_ids'} & set(vals))
        old_lines_map = {justification.id: justification.attendance_session_line_ids for justification in self} if lines_change else {}

        updated = super().write(vals)
        if by_user:
            self._check_permissions(message)
        if lines_change:
            for justification in self:
                if 'attendance_session_line_ids' not in vals:
                    super(EmsAttendanceJustification, justification).write(
                        {'attendance_session_line_ids': [(6, 0, justification._covered_lines().ids)]})
                old_lines = old_lines_map[justification.id]
                new_lines = justification.attendance_session_line_ids
                for old_line in old_lines - new_lines:
                    old_line.write(justification.remove_justification(old_line))
                for new_line in new_lines - old_lines:
                    new_line.write(justification.perform_justification(new_line._justification_vals()))
        return updated

    def unlink(self):
        self._check_permissions(_("Only the student's tutor can remove its attendance justifications."))

        # A justified severe delay is a mild delay by now.
        justified = self.env.ref("ems.attendance_status_justified") | self.env.ref("ems.attendance_status_delayed")
        for justification in self:
            for line in justification.attendance_session_line_ids:
                if line.status_id in justified:
                    line.write(justification.remove_justification(line))

        return super().unlink()
