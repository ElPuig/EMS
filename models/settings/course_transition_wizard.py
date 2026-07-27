# -*- coding: utf-8 -*-

import base64
import csv
import io
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Actions the preview predicts for each student of the scope. They are the wizard's
# whole vocabulary: every student in scope ends up in exactly one of them.
TRANSITION_ACTIONS = [
    ('graduate', 'Graduate'),
    ('graduate_continue', 'Graduates and continues'),
    ('place', 'Place in destination group'),
    ('unplaced', 'Enrolled without group'),
    ('missing', 'No destination'),
]


class ems_course_transition_wizard(models.TransientModel):
    _name = "ems.course_transition_wizard"
    _description = "Course transition wizard: closes the outgoing course and opens the next one."

    source_course_id = fields.Many2one(string="Outgoing course", comodel_name="ems.course",
        readonly=True, default=lambda self: self._default_source_course())
    target_course_id = fields.Many2one(string="Incoming course", comodel_name="ems.course",
        required=True, default=lambda self: self._default_target_course())
    # Scope. Studies do not finish at the same time, so a run transitions only the ones
    # it is given; everything below is bounded by this, the global flip excepted.
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study",
        default=lambda self: self._default_study_ids())
    archive_declined_applicants = fields.Boolean(string="Archive applicants without a confirmed enrollment",
        help="Summer withdrawals: applicants who never confirmed their enrollment for the incoming course.")
    backup_done = fields.Boolean(string="I have taken a backup",
        help="The operational cleanup cannot be undone. Apply stays disabled until this is ticked.")
    state = fields.Selection(string="State", selection=[
        ('draft', 'Draft'),
        ('preview', 'Preview'),
        ('done', 'Done'),
    ], default='draft', required=True)

    line_ids = fields.One2many(string="Preview", comodel_name="ems.course_transition_wizard.line",
        inverse_name="wizard_id")
    blocking_html = fields.Html(string="Blockers", readonly=True)
    warning_html = fields.Html(string="Warnings", readonly=True)
    has_blockers = fields.Boolean(string="Has blockers", readonly=True)

    graduate_count = fields.Integer(string="Graduates", readonly=True)
    graduate_continue_count = fields.Integer(string="Graduates continuing at the centre", readonly=True)
    place_count = fields.Integer(string="To place", readonly=True)
    unplaced_count = fields.Integer(string="Enrolled without group", readonly=True)
    missing_count = fields.Integer(string="Without destination", readonly=True)
    incomplete_evaluation_count = fields.Integer(string="Incomplete evaluations", readonly=True)
    template_count = fields.Integer(string="Attendance templates to archive", readonly=True)
    delete_count = fields.Integer(string="Records to delete", readonly=True)
    declined_applicant_count = fields.Integer(string="Applicants without enrollment", readonly=True)

    audit_file = fields.Binary(string="Transition log (CSV)", readonly=True)
    audit_file_name = fields.Char()
    result_html = fields.Html(string="Result", readonly=True)

    will_flip = fields.Boolean(string="Flips the course", readonly=True,
        help="Whether this run leaves no active study behind and therefore switches the current course.")
    pending_study_ids = fields.Many2many(string="Studies left pending", comodel_name="ems.study",
        relation="ems_course_transition_wizard_pending_study_rel", readonly=True)

    @api.model
    def _default_source_course(self):
        return self.env.company.current_course_id \
            or self.env['ems.course'].search([('is_current', '=', True)], limit=1)

    @api.model
    def _default_target_course(self):
        return self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)

    @api.model
    def _default_study_ids(self):
        # Only studies that are still pending and actually have groups: a deprecated or
        # empty study would otherwise keep the global flip hostage forever.
        return self.env['ems.study'].search([('transition_state', '=', 'active')]).filtered(
            lambda study: self.env['ems.group'].search_count([('study_id', '=', study.id)]))

    # --- scope helpers -------------------------------------------------------

    def _scope_students(self):
        """Every student of the studies being transitioned. The capture is by group
        (not by enrollment), so latecomers and stranded students are included."""
        self.ensure_one()
        return self.env['res.partner'].search([
            ('contact_type', '=', 'student'),
            ('main_group_id.study_id', 'in', self.study_ids.ids)])

    def _scope_groups(self):
        self.ensure_one()
        return self.env['ems.group'].search([('study_id', 'in', self.study_ids.ids)])

    def _scope_graduates(self):
        """Students the graduation wizard already marked for THIS outgoing course.

        A mark carrying another course belongs to a different transition and is left
        alone. Single source of truth for the preview, the blocker and the apply, so
        the three can never disagree on who is graduating.
        """
        self.ensure_one()
        return self._scope_students().filtered(
            lambda student: student.exit_type == 'graduation'
            and student.exit_course_id == self.source_course_id)

    def _continuing_graduates(self, order_index):
        """Graduates who keep studying at the centre next course.

        Finishing a study and enrolling into another one are independent facts, not a
        contradiction: a CFGM graduate moving up to a CFGS, or a CFGS graduate starting
        a second one — even in another family — is both at once. Nothing marks them:
        the tutor only knows about the graduation and the enrollment arrives on its own
        through the GEDAC assignment, so the wizard derives the case at run time from
        the two facts it already has.

        ANY non-cancelled enrollment counts, not only the confirmed ones: an offer still
        in draft/sent may be confirmed in September, and archiving the student now would
        leave that confirmation with nobody to place.
        """
        self.ensure_one()
        return self._scope_graduates().filtered(lambda student: student.id in order_index)

    def _leaving_graduates(self, order_index):
        """Graduates who really leave the centre: the ones step 2 turns into alumni."""
        self.ensure_one()
        return self._scope_graduates() - self._continuing_graduates(order_index)

    def _target_orders_by_partner(self):
        """Every non-cancelled enrollment for the incoming course, indexed by partner.

        Read once and passed around: asking per student instead would fire one query
        for each of them, and a real transition spans well over a thousand.
        """
        self.ensure_one()
        index = {}
        for order in self.env['sale.order'].search([
                ('ems_course_id', '=', self.target_course_id.id),
                ('state', '!=', 'cancel')]):
            index.setdefault(order.partner_id.id, order)
        return index

    def _incoming_orders(self):
        """Confirmed enrollments for the incoming course in the studies being
        transitioned. They are what steps 3-4 execute, and they reach further than
        _scope_students(): an applicant entering the centre has no group yet, so the
        scope-by-group capture cannot see them.
        """
        self.ensure_one()
        return self.env['sale.order'].search([
            ('ems_course_id', '=', self.target_course_id.id),
            ('ems_study_id', 'in', self.study_ids.ids),
            ('state', '=', 'sale')])

    def _last_round_sessions(self, groups=None):
        """The last existing round of every group·subject of 'groups', the scope by
        default. 'round' is a single-digit Selection, so a plain string comparison
        keeps the latest."""
        self.ensure_one()
        if groups is None:
            groups = self._scope_groups()
        latest = {}
        for session in self.env['ems.grade_session'].search([
                ('group_id', 'in', groups.ids)]):
            key = (session.group_id.id, session.subject_id.id)
            if key not in latest or session.round > latest[key].round:
                latest[key] = session
        return self.env['ems.grade_session'].browse([s.id for s in latest.values()])

    def _unclosed_origin_studies(self):
        """Studies this run pulls a student OUT of, whose evaluation is still open.

        The placement freezes the history of the year that ends on the way out of the
        group (ems.student.year_record.freeze_on_leaving), so an origin study still
        evaluating would be frozen with half its grades in it. Only studies OUTSIDE the
        scope are examined: the ones inside are already covered by the last-round blocker.
        """
        self.ensure_one()
        origins = self.env['ems.study']
        for order in self._incoming_orders():
            origin = order.partner_id.main_group_id.study_id
            if origin and origin not in self.study_ids and origin.transition_state != 'transitioned':
                origins |= origin
        return origins.filtered(lambda study: any(
            session.state != 'final' for session in self._last_round_sessions(
                self.env['ems.group'].search([('study_id', '=', study.id)]))))

    # --- preview -------------------------------------------------------------

    def _collect_blockers(self, order_index):
        """Conditions that make the transition unsafe. Returns a list of messages;
        an empty list means Apply may run."""
        self.ensure_one()
        blockers = []
        if not self.target_course_id or self.target_course_id == self.source_course_id:
            blockers.append(_("The incoming course must exist and be different from the outgoing one."))

        not_final = self._last_round_sessions().filtered(lambda session: session.state != 'final')
        if not_final:
            blockers.append(_("The last round is not finalised in %s evaluation session(s): %s.")
                            % (len(not_final), ", ".join(not_final.mapped('display_name')[:10])))

        # This run places students coming from a study it is not transitioning, and their
        # history is frozen as they leave: refuse rather than freeze it half-way.
        unclosed = self._unclosed_origin_studies()
        if unclosed:
            blockers.append(_("This run places students coming from study(ies) whose last round is "
                              "not finalised: %s. Close their evaluations, or transition them in "
                              "this same run, so their academic history is not frozen half-way.")
                            % ", ".join(unclosed.mapped('display_name')))
        return blockers

    def _incomplete_evaluation_lines(self):
        """Subject lines of the last round whose evaluation is not closed.

        The criterion depends on the course (see the D9 decision in
        docs/en/developers/settings/course_transition_wizard.md): the work placement
        (EM) only exists in the LAST course of a study, when students actually go to a
        company. Since the planning may still give a non-zero external weight to earlier
        courses, 'has_final' is False for all of them and would report every first-course
        student as incomplete. Promotion there is decided by the internal grade alone.
        """
        self.ensure_one()
        lines = self.env['ems.grade_subject_line']
        for session in self._last_round_sessions():
            group = session.group_id
            if group.course >= group.study_id._ems_last_course():
                lines |= session.grade_subject_line_ids.filtered(lambda line: not line.has_final)
            else:
                lines |= session.grade_subject_line_ids.filtered(lambda line: not line.internal_is_complete)
        return lines

    def _scope_templates(self):
        """Attendance templates whose groups belong to the studies in scope."""
        self.ensure_one()
        return self.env['ems.attendance_template'].search([
            ('group_ids.study_id', 'in', self.study_ids.ids)])

    def _mixed_templates(self):
        """Templates that ALSO cover groups outside the scope. They are left alone:
        archiving one would take away the schedule of a study still running."""
        self.ensure_one()
        return self._scope_templates().filtered(
            lambda template: any(group.study_id not in self.study_ids for group in template.group_ids))

    def _templates_to_archive(self):
        self.ensure_one()
        return self._scope_templates() - self._mixed_templates()

    def _declined_applicants(self, order_index):
        """Applicants of the studies in scope who never confirmed an enrollment."""
        self.ensure_one()
        applicants = self.env['res.partner'].search([
            ('contact_type', '=', 'applicant'),
            ('study_id', 'in', self.study_ids.ids)])
        return applicants.filtered(
            lambda applicant: applicant.id not in order_index
            or order_index[applicant.id].state != 'sale')

    def _delete_count(self):
        """How many operational records step 8 would delete, for the scope."""
        self.ensure_one()
        students = self._scope_students()
        groups = self._scope_groups()
        sessions = self.env['ems.grade_session'].search([('group_id', 'in', groups.ids)])
        return sum([
            self.env['ems.enrollment'].search_count([('student_id', 'in', students.ids)]),
            len(sessions),
            len(sessions.mapped('grade_outcome_line_ids')),
            len(sessions.mapped('grade_subject_line_ids')),
            self.env['ems.attendance_session_line'].search_count([('student_id', 'in', students.ids)]),
        ])

    def _build_lines(self, order_index):
        """One preview line per student of the scope, with the action the apply
        would take. Graduation is checked first, and splits in two: a graduate who
        leaves is never placed, one who continues is never archived.

        'graduate_continue' is derived here and nowhere else — it is a computed label,
        not something anybody marks. The destination group only shows once the order is
        confirmed: an unconfirmed offer has no placement to predict yet.
        """
        self.ensure_one()
        vals_list = []
        graduates = self._scope_graduates()
        continuing = self._continuing_graduates(order_index)
        seen = self.env['res.partner']
        for student in self._scope_students():
            order = order_index.get(student.id)
            if student in continuing:
                action = 'graduate_continue'
                group = order.ems_group_id if order.state == 'sale' else self.env['ems.group']
            elif student in graduates:
                action, group = 'graduate', self.env['ems.group']
            elif not order:
                action, group = 'missing', self.env['ems.group']
            elif order.ems_group_id:
                action, group = 'place', order.ems_group_id
            else:
                action, group = 'unplaced', self.env['ems.group']
            seen |= student
            vals_list.append({
                'student_id': student.id,
                'study_id': student.main_group_id.study_id.id,
                'source_group_id': student.main_group_id.id,
                'action': action,
                'destination_group_id': group.id,
            })
        # Newcomers: applicants and returning ex-students enrolling into a study in
        # scope. They are placed by the very same steps, so the preview has to own up
        # to them instead of only showing who is already inside.
        for order in self._incoming_orders():
            if order.partner_id in seen:
                continue
            seen |= order.partner_id
            vals_list.append({
                'student_id': order.partner_id.id,
                'study_id': order.ems_study_id.id,
                'source_group_id': order.partner_id.main_group_id.id,
                'action': 'place' if order.ems_group_id else 'unplaced',
                'destination_group_id': order.ems_group_id.id,
            })
        return vals_list

    def _pending_studies(self):
        """Studies that would stay active after this run — what holds the flip back."""
        self.ensure_one()
        return self.env['ems.study'].search([
            ('transition_state', '=', 'active'),
            ('id', 'not in', self.study_ids.ids)]).filtered(
            lambda study: self.env['ems.group'].search_count([('study_id', '=', study.id)]))

    def _collect_warnings(self):
        """Informative findings. They never block: they are what the operator has to
        have seen before ticking the backup checkbox."""
        self.ensure_one()
        warnings = []
        if self.graduate_continue_count:
            names = self.line_ids.filtered(
                lambda line: line.action == 'graduate_continue').mapped('student_id.display_name')
            warnings.append(_("%s graduate(s) stay at the centre: they keep their graduation on "
                              "record but are neither converted to alumni nor archived: %s.")
                            % (self.graduate_continue_count, ", ".join(names)))
        if self.missing_count:
            names = self.line_ids.filtered(lambda line: line.action == 'missing').mapped(
                'student_id.display_name')
            warnings.append(_("%s student(s) with no enrollment for the incoming course: %s.")
                            % (self.missing_count, ", ".join(names)))
        if self.unplaced_count:
            warnings.append(_("%s enrollment(s) confirmed without a destination group: they will be skipped.")
                            % self.unplaced_count)
        incoming_drafts = self.env['sale.order'].search_count([
            ('ems_course_id', '=', self.target_course_id.id),
            ('ems_study_id', 'in', self.study_ids.ids),
            ('state', 'in', ('draft', 'sent'))])
        if incoming_drafts:
            warnings.append(_("%s enrollment(s) for the incoming course are still in draft or sent. "
                              "They are NOT cancelled: those students simply have no destination "
                              "until they confirm, and will be placed on their own when they do.")
                            % incoming_drafts)
        outgoing = self.env['sale.order'].search([
            ('ems_course_id', '=', self.source_course_id.id),
            ('ems_study_id', 'in', self.study_ids.ids)])
        to_lock = len(outgoing.filtered(lambda order: order.state == 'sale' and not order.locked))
        to_cancel = len(outgoing.filtered(lambda order: order.state in ('draft', 'sent')))
        if to_lock:
            warnings.append(_("%s confirmed enrollment(s) of the outgoing course will be locked "
                              "against further edits.") % to_lock)
        if to_cancel:
            warnings.append(_("%s never-confirmed enrollment(s) of the outgoing course will be "
                              "cancelled.") % to_cancel)
        if self.incomplete_evaluation_count:
            warnings.append(_("%s subject grade(s) without a closed evaluation in the last round.")
                            % self.incomplete_evaluation_count)
        mixed = self._mixed_templates()
        if mixed:
            warnings.append(_("%s attendance template(s) also cover groups outside the scope "
                              "and will NOT be archived: %s.")
                            % (len(mixed), ", ".join(mixed.mapped('display_name')[:10])))
        if self.template_count:
            warnings.append(_("%s attendance template(s) will be archived.") % self.template_count)
        if self.delete_count:
            warnings.append(_("%s operational record(s) will be deleted. This cannot be undone.")
                            % self.delete_count)
        if self.archive_declined_applicants and self.declined_applicant_count:
            warnings.append(_("%s applicant(s) without a confirmed enrollment will be archived.")
                            % self.declined_applicant_count)
        if self.will_flip:
            warnings.append(_("No study is left pending: this run switches the current course to %s.")
                            % self.target_course_id.display_name)
        else:
            warnings.append(_("The current course will NOT change yet; %s study(ies) stay pending: %s.")
                            % (len(self.pending_study_ids),
                               ", ".join(self.pending_study_ids.mapped('display_name')[:10])))
        return warnings

    def _as_html(self, messages):
        if not messages:
            return ""
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % message for message in messages)

    def action_preview(self):
        """Dry run: writes nothing outside the wizard itself."""
        self.ensure_one()
        if not self.study_ids:
            raise UserError(_("Please select at least one study."))

        order_index = self._target_orders_by_partner()
        self.line_ids.unlink()
        self.line_ids = [(0, 0, vals) for vals in self._build_lines(order_index)]
        actions = self.line_ids.mapped('action')
        pending = self._pending_studies()
        self.write({
            'graduate_count': actions.count('graduate'),
            'graduate_continue_count': actions.count('graduate_continue'),
            'place_count': actions.count('place'),
            'unplaced_count': actions.count('unplaced'),
            'missing_count': actions.count('missing'),
            'incomplete_evaluation_count': len(self._incomplete_evaluation_lines()),
            'template_count': len(self._templates_to_archive()),
            'delete_count': self._delete_count(),
            'declined_applicant_count': len(self._declined_applicants(order_index)),
            'pending_study_ids': [(6, 0, pending.ids)],
            'will_flip': not pending,
        })
        blockers = self._collect_blockers(order_index)
        self.write({
            'blocking_html': self._as_html(blockers),
            'has_blockers': bool(blockers),
            'warning_html': self._as_html(self._collect_warnings()),
            'state': 'preview',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # --- apply ---------------------------------------------------------------

    def _apply_history(self, students):
        """Step 0 — freeze the academic history of the whole scope.

        It gates everything that follows: step 8 deletes the live grade and attendance
        records, so nothing may be converted or cleaned until the history that replaces
        them exists. A failure here aborts the transition instead of leaving the year
        half-transitioned. Sudo: the generator reads grade and attendance models the
        academic admin does not necessarily own.
        """
        self.ensure_one()
        try:
            self.env['ems.student.year_record'].sudo().generate_for_students(
                students, self.source_course_id)
        except Exception as error:
            raise UserError(_(
                "The academic history could not be generated, so the transition was "
                "aborted and nothing has been changed: %s") % error)

    def _apply_graduates(self, graduates):
        """Steps 1, 2 and 2b — alumni, portal and archive.

        The order is load-bearing: the conversion detaches the student from its group,
        the revoke needs the portal user gone before the archive, and Odoo refuses to
        archive a contact still linked to an active portal user. A student whose revoke
        failed is reported and left active rather than raising, so one broken portal
        account cannot roll back a batch of hundreds. Returns the issues to audit.
        """
        self.ensure_one()
        issues = []
        if not graduates:
            return issues
        # The graduation wizard already wrote it, but the mark is permanent and the
        # conversion reads it to tell an alumnus from a withdrawal: make sure.
        graduates.write({'has_graduated': True})
        graduates._ems_convert_to_ex_student()
        for graduate in graduates:
            issues += graduate._ems_revoke_student_portal()['issues']
            if graduate._has_active_portal_user():
                issues.append(_("%s: portal access could not be revoked, kept active")
                              % graduate.display_name)
            else:
                graduate.write({'active': False})
        return issues

    def _apply_continuing_graduates(self, graduates):
        """Step 2c — the graduates who stay at the centre.

        They keep 'has_graduated' (permanent) and the year record step 0 has just
        frozen, but receive none of the exit treatment: no alumni conversion, no portal
        revoke, no archive. Clearing the exit metadata is what stops an active student
        of the incoming course from carrying the exit date of the study it has just
        finished; _ems_convert_to_student() already does exactly that and leaves
        'has_graduated' alone.

        MUST run after _apply_history(): year_record._generate_one() stamps how the
        student left the outgoing course by reading 'exit_course_id', which this clears.
        """
        self.ensure_one()
        if graduates:
            graduates._ems_convert_to_student()

    def _apply_placement(self):
        """Steps 3 and 4 — destination group, then subject enrollments.

        Both are the one bulk call to sale.order._ems_apply_destination_placement(),
        already idempotent and already ordered (the ems.enrollment domain demands a
        'student', so the conversion has to come first). An enrollment confirmed
        without a destination group is skipped by the helper and was reported as
        'unplaced' in the preview. Returns how many students were placed.
        """
        self.ensure_one()
        placed = 0
        for order in self._incoming_orders():
            if not order.ems_group_id:
                continue
            student = order.partner_id
            # An applicant, or an ex-student coming back, has to be a student again
            # before it can hold subject enrollments.
            if student.contact_type in ('applicant', 'alumni', 'withdrawal'):
                student._ems_convert_to_student()
            order._ems_apply_destination_placement()
            placed += 1
        return placed

    def _apply_cleanup(self, students):
        """Steps 7 and 8 — archive the attendance templates and delete the operational
        records of the year that has just ended.

        IRREVERSIBLE, and the reason step 0 has to have completed: the academic history
        is what replaces everything deleted here.

        It runs BEFORE the placement on purpose. _ems_clear_operational_records() deletes
        every ems.enrollment of the student with no group filter (it was written for a
        withdrawal, where the student leaves the centre altogether), so running it after
        steps 3-4 would delete the very enrollments the transition had just created.
        """
        self.ensure_one()
        self._templates_to_archive().write({'active': False})
        students._ems_clear_operational_records()
        groups = self._scope_groups()
        # Subject enrollments go by group as well, for the same reason grade sessions do
        # below: a student already pulled out by the run of its destination study is no
        # longer in _scope_students(), and its enrollments here would linger forever.
        self.env['ems.enrollment'].sudo().with_context(ems_bypass_grade_guard=True).search(
            [('group_id', 'in', groups.ids)]).unlink()
        # Grade sessions go by group, not by student: UNIQUE(group_id, subject_id, round)
        # carries no course, so next year's first round could not be created while the
        # outgoing one is still there. The cascade takes the outcome and subject lines
        # with it, and is_locked resets naturally.
        self.env['ems.grade_session'].sudo().search([('group_id', 'in', groups.ids)]).unlink()
        # The delegate of a group that has just been emptied. The helper above only
        # clears it through the student's own main_group_id, which a graduate no longer
        # has at this point — step 1 detached it.
        groups.sudo().write({'delegate_id': False})

    def _apply_transition_flip(self):
        """Step 5 — mark the scope as transitioned and, when nothing is left pending,
        flip the whole centre onto the incoming course. Returns whether it flipped.

        'is_current' is deliberately not written here: res.company.write() syncs it
        from current_course_id, clearing the flag on every other course before setting
        the new one. ems.course guards uniqueness with a Python @api.constrains rather
        than a SQL constraint, so that clear-then-set order is mandatory — and it stays
        in the one place that already owns it.
        """
        self.ensure_one()
        self.study_ids.write({'transition_state': 'transitioned'})
        if self._pending_studies():
            return False
        self.env.company.current_course_id = self.target_course_id
        # The incoming course is the running one now, so it is nobody's "next course".
        self.target_course_id.is_enrollment_default = False
        # A fresh year: every study is pending again for the next transition.
        self.env['ems.study'].search([]).write({'transition_state': 'active'})
        return True

    def _apply_outgoing_enrollments(self):
        """Step 6 — close the enrollments of the outgoing course.

        A confirmed enrollment is a legal record: it is locked against further edits,
        never cancelled. The ones that never made it past draft/sent are cancelled.
        Only the outgoing course is touched — a draft for the INCOMING course belongs
        to a latecomer who can still confirm it and be placed on their own.
        """
        self.ensure_one()
        orders = self.env['sale.order'].search([
            ('ems_course_id', '=', self.source_course_id.id),
            ('ems_study_id', 'in', self.study_ids.ids)])
        confirmed = orders.filtered(lambda order: order.state == 'sale' and not order.locked)
        confirmed.action_lock()
        pending = orders.filtered(lambda order: order.state in ('draft', 'sent'))
        pending._action_cancel()
        return len(confirmed), len(pending)

    def _build_audit_csv(self):
        """Student → destination group, the map a selective manual roll-back needs."""
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["student", "student_id", "study", "action", "source_group", "destination_group"])
        for line in self.line_ids:
            writer.writerow([
                line.student_id.display_name, line.student_id.student_id or "",
                line.study_id.display_name or "", line.action or "",
                line.source_group_id.name or "", line.destination_group_id.name or "",
            ])
        return base64.b64encode(output.getvalue().encode("utf-8-sig")).decode()

    def _apply_audit(self, flipped, issues, locked, cancelled):
        """Step 9 — a permanent trace of the run.

        Logged on the company's PARTNER: res.company itself carries no chatter
        (mail.thread is not among its inherits) and its partner is where the company's
        conversation already lives. Posted as an internal note, so it never notifies a
        follower about an operation that only concerns the staff.
        """
        self.ensure_one()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audit_file = self._build_audit_csv()
        self.audit_file_name = "course_transition_%s.csv" % stamp

        summary = [
            _("Studies: %s") % ", ".join(self.study_ids.mapped('acronym')),
            _("Graduated and archived: %s") % self.graduate_count,
            _("Graduated and continuing at the centre: %s") % self.graduate_continue_count,
            _("Placed: %s") % self.place_count,
            _("Without destination: %s") % self.missing_count,
            _("Enrollments locked: %s") % locked,
            _("Enrollments cancelled: %s") % cancelled,
            _("Records deleted: %s") % self.delete_count,
            _("Current course switched: %s") % (_("yes") if flipped else _("no")),
        ]
        if issues:
            summary.append(_("Issues: %s") % "; ".join(issues))
        body = "<p><strong>%s</strong> (%s → %s)</p><ul>%s</ul>" % (
            _("Course transition applied"),
            self.source_course_id.display_name, self.target_course_id.display_name,
            "".join("<li>%s</li>" % item for item in summary))

        attachment = self.env['ir.attachment'].create({
            'name': self.audit_file_name,
            'datas': self.audit_file,
            'res_model': 'res.partner',
            'res_id': self.env.company.partner_id.id,
        })
        self.env.company.partner_id.message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_note',
            attachment_ids=attachment.ids)
        self.result_html = body

    def action_apply(self):
        self.ensure_one()
        if self.state != 'preview':
            raise UserError(_("Run the preview before applying the transition."))
        if self.has_blockers:
            raise UserError(_("The transition cannot be applied while there are blockers."))
        if not self.backup_done:
            raise UserError(_("Please confirm that a backup has been taken before applying the transition."))

        order_index = self._target_orders_by_partner()
        students = self._scope_students()
        graduates = self._leaving_graduates(order_index)
        continuing = self._continuing_graduates(order_index)

        self._apply_history(students)
        issues = self._apply_graduates(graduates)
        self._apply_continuing_graduates(continuing)
        self._apply_cleanup(students)
        self._apply_placement()
        flipped = self._apply_transition_flip()
        locked, cancelled = self._apply_outgoing_enrollments()
        self._apply_audit(flipped, issues, locked, cancelled)

        self.state = 'done'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ems_course_transition_wizard_line(models.TransientModel):
    _name = "ems.course_transition_wizard.line"
    _description = "Course transition wizard line: the action predicted for one student."
    _order = "action, student_id"

    wizard_id = fields.Many2one(comodel_name="ems.course_transition_wizard", ondelete="cascade")
    student_id = fields.Many2one(string="Student", comodel_name="res.partner")
    study_id = fields.Many2one(string="Study", comodel_name="ems.study")
    source_group_id = fields.Many2one(string="Current group", comodel_name="ems.group")
    destination_group_id = fields.Many2one(string="Destination group", comodel_name="ems.group")
    action = fields.Selection(string="Action", selection=TRANSITION_ACTIONS)
