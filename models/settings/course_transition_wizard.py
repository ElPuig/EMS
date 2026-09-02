# -*- coding: utf-8 -*-

import base64
import csv
import io
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..shared.attendance_mixin import EMS_BYPASS_TEMPLATE_LOCK_KEY

# Actions the preview predicts for each student of the scope. They are the wizard's
# whole vocabulary: every student in scope ends up in exactly one of them.
TRANSITION_ACTIONS = [
    ('graduate', 'Graduates and leaves'),
    ('graduate_continue', 'Graduates and continues'),
    ('graduate_pending', 'Graduates, pending confirmation'),
    ('place', 'Joins its group for the next course'),
    ('place_later', 'Joins when its own study transitions'),
    ('pending', 'Enrollment pending confirmation'),
    ('unplaced', 'Enrollment with no destination group'),
    ('missing', 'No enrollment for the next course'),
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

    graduate_count = fields.Integer(string="Graduates leaving the centre", readonly=True)
    graduate_continue_count = fields.Integer(string="Graduates continuing at the centre", readonly=True)
    graduate_pending_count = fields.Integer(string="Graduates pending confirmation", readonly=True)
    place_count = fields.Integer(string="Joining their group", readonly=True)
    place_later_count = fields.Integer(string="Joining when their study transitions", readonly=True)
    pending_count = fields.Integer(string="Enrollments pending confirmation", readonly=True)
    unplaced_count = fields.Integer(string="Enrollments with no destination group", readonly=True)
    missing_count = fields.Integer(string="Without an enrollment", readonly=True)
    orphan_count = fields.Integer(string="Students with no group at all", readonly=True)
    incomplete_evaluation_count = fields.Integer(string="Incomplete evaluations", readonly=True)
    template_count = fields.Integer(string="Attendance templates to archive", readonly=True)
    calendar_block_count = fields.Integer(string="Teacher calendar blocks to archive", readonly=True)
    delete_count = fields.Integer(string="Records to delete", readonly=True)

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

    def _orphan_students(self):
        """Active students that belong to no run at all, whatever studies are picked.

        The scope is captured through main_group_id, so a student without one is invisible
        to every step: no year record is frozen for them and their operational records are
        never cleaned. It is pre-existing data quality — an Esfer@ import that found no
        group, a manual edit — but the transition is where it stops being recoverable,
        because afterwards they are indistinguishable from the hundreds of students a run
        legitimately leaves without a group.

        'study_id' is what tells the two apart: _apply_detach_unplaced keeps it on purpose
        when it detaches somebody, so a student with neither is one nobody ever placed.
        """
        self.ensure_one()
        return self.env['res.partner'].search([
            ('contact_type', '=', 'student'),
            ('main_group_id', '=', False),
            ('study_id', '=', False)])

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

        Only a CONFIRMED enrollment counts here: an offer still in draft/sent has
        nobody to place yet, and belongs to _pending_graduates() instead.
        """
        self.ensure_one()
        return self._scope_graduates().filtered(
            lambda student: order_index.get(student.id)
            and order_index[student.id].state == 'sale')

    def _pending_graduates(self, order_index):
        """Graduates holding an offer nobody has confirmed yet.

        They can be neither placed (there is nothing to place) nor turned into alumni:
        #357 archives every alumnus, and res.partner.write() refuses to archive a
        contact with an active portal user — so an alumnus is by construction someone
        without portal, and without portal they could never confirm the offer from
        /my/gestion-matriculas. Step 2d makes them applicants instead.
        """
        self.ensure_one()
        return self._scope_graduates().filtered(
            lambda student: order_index.get(student.id)
            and order_index[student.id].state != 'sale')

    def _leaving_graduates(self, order_index):
        """Graduates who really leave the centre: the ones step 2 turns into alumni."""
        self.ensure_one()
        return self._scope_graduates() - self._continuing_graduates(order_index) \
            - self._pending_graduates(order_index)

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

        # A confirmed enrollment with no destination group used to be a warning saying it
        # would be skipped. The outcome was not recoverable through the UI, so it refuses.
        unplaced = self._incoming_orders().filtered(lambda order: not order.ems_group_id)
        if unplaced:
            blockers.append(_("%s confirmed enrollment(s) have no destination group and nobody "
                              "would be placed by them: %s. Fill the group in — the \"Suggest "
                              "destination group\" action of the \"Students without destination\" "
                              "report does it in bulk — and preview again.")
                            % (len(unplaced), ", ".join(unplaced.mapped('partner_id.display_name')[:10])))

        # A student of a study that enrolls through the enrollment flow and has NO
        # enrollment at all is either a leaver nobody registered or somebody forgotten.
        # Both have to be settled BEFORE the freeze: after it the student has no group,
        # which makes graduating them impossible (the graduation wizard needs the group
        # to tell whether they are in the last course). Studies that do not use the flow
        # are left as a warning: there a missing enrollment is the expected state until
        # the September Esfer@ re-import.
        stranded = self.line_ids.filtered(
            lambda line: line.action == 'missing' and line.study_id.uses_enrollment_flow)
        if stranded:
            blockers.append(_("%s student(s) have no enrollment at all for the incoming course, "
                              "and their study enrolls through it: %s. Either register their "
                              "withdrawal or send them an enrollment proposal — a draft one is "
                              "enough — and preview again.")
                            % (len(stranded), ", ".join(stranded.mapped('student_id.display_name')[:10])))

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

    def _migrating_calendar_blocks(self):
        """Every active resource.calendar.attendance row, on any teacher's real (non-framework)
        personal calendar, whose own group_ids belongs to a study in scope - the calendar-side
        mirror of _scope_templates()'s domain, read directly from the calendar block itself rather
        than trusted purely via the template it happens to back. Deliberately independent of
        _templates_to_archive(): a teacher can build their own schedule bypassing the normal sync
        (see plans/course_transition_teacher_schedule_archival.md, decision 3), so a calendar block
        genuinely in scope is not guaranteed to have a perfectly-matching template/schedule line -
        this is what makes resource.calendar the authoritative source for "what does this teacher's
        calendar say they're teaching," independent of whether the template side agrees."""
        self.ensure_one()
        return self.env['resource.calendar.attendance'].search([
            ('group_ids.study_id', 'in', self.study_ids.ids),
            ('calendar_id.is_framework', '=', False),
        ])

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
        pending = self._pending_graduates(order_index)
        seen = self.env['res.partner']
        for student in self._scope_students():
            order = order_index.get(student.id)
            if student in continuing:
                action, group = 'graduate_continue', self._destination_of(order)
            elif student in pending:
                action, group = 'graduate_pending', self.env['ems.group']
            elif student in graduates:
                action, group = 'graduate', self.env['ems.group']
            elif not order:
                action, group = 'missing', self.env['ems.group']
            elif order.state != 'sale':
                # Step 3 only executes confirmed enrollments, so promising a placement
                # here would overstate what the apply is about to do. They keep the
                # offer, lose the group like everybody unplaced, and place themselves
                # through _ems_admit_student() the day they confirm.
                action, group = 'pending', self.env['ems.group']
            elif not order.ems_group_id:
                action, group = 'unplaced', self.env['ems.group']
            elif destination := self._destination_of(order):
                action, group = 'place', destination
            else:
                # Confirmed, with a group, but heading to a study this run is not
                # transitioning: _apply_placement only executes its own studies, so this
                # one is detached now and placed by its own study's run. Calling it
                # 'place' promised a move that never happened, in the preview and in the
                # audit CSV that is the reference for undoing a case by hand.
                action, group = 'place_later', self.env['ems.group']
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

    def _destination_of(self, order):
        """The group THIS run will move the student into, empty when it will not.

        Every run only places into its own studies (_incoming_orders filters by
        study_ids), so a student heading elsewhere — a CFGM graduate going up to a
        CFGS the centre has not transitioned yet — is not moved here: their own
        study's run will do it, and step 4b detaches them in the meantime. Showing
        the group anyway promised a move that never happened, both on screen and in
        the audit CSV. The warning names them so the information is not lost.
        """
        self.ensure_one()
        if order.ems_study_id in self.study_ids and order.state == 'sale':
            return order.ems_group_id
        return self.env['ems.group']

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
        if self.graduate_pending_count:
            names = self.line_ids.filtered(
                lambda line: line.action == 'graduate_pending').mapped('student_id.display_name')
            warnings.append(_("%s graduate(s) hold an enrollment nobody has confirmed yet: they "
                              "become applicants and keep their portal access, so they can still "
                              "confirm it. They are not archived: %s.")
                            % (self.graduate_pending_count, ", ".join(names)))
        # 'graduate_continue' keeps its own label (they do graduate; only the placement is
        # deferred), so it is still recognised here by its missing destination group.
        elsewhere = self.line_ids.filtered(
            lambda line: line.action == 'place_later'
            or (line.action == 'graduate_continue' and not line.destination_group_id))
        if elsewhere:
            warnings.append(_("%s student(s) are heading to a study this run is not transitioning, "
                              "so they are not placed here: they keep their enrollment and join "
                              "their group when that study transitions. Meanwhile they are left "
                              "with no group: %s.")
                            % (len(elsewhere), ", ".join(elsewhere.mapped('student_id.display_name')[:10])))
        orphans = self._orphan_students()
        if orphans:
            warnings.append(_("%s active student(s) have no group at all, so no run can see "
                              "them: their academic history is not frozen and their records "
                              "are not cleaned. Give them a group or register their "
                              "withdrawal before applying: %s.")
                            % (len(orphans), ", ".join(orphans.mapped('display_name')[:10])))
        # The ones whose study DOES use the flow are a blocker, not a warning.
        expected = self.line_ids.filtered(
            lambda line: line.action == 'missing' and not line.study_id.uses_enrollment_flow)
        if expected:
            warnings.append(_("%s student(s) have no enrollment for the incoming course. Their "
                              "study does not use the enrollment flow, so that is the expected "
                              "state until the September Esfer@ re-import: %s.")
                            % (len(expected), ", ".join(expected.mapped('student_id.display_name')[:10])))
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
        if self.calendar_block_count:
            warnings.append(_("%s teacher calendar block(s) will be archived.") % self.calendar_block_count)
        if self.delete_count:
            warnings.append(_("%s operational record(s) will be deleted. This cannot be undone.")
                            % self.delete_count)
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
            'graduate_pending_count': actions.count('graduate_pending'),
            'place_count': actions.count('place'),
            'place_later_count': actions.count('place_later'),
            'pending_count': actions.count('pending'),
            'unplaced_count': actions.count('unplaced'),
            'missing_count': actions.count('missing'),
            'orphan_count': len(self._orphan_students()),
            'incomplete_evaluation_count': len(self._incomplete_evaluation_lines()),
            'template_count': len(self._templates_to_archive()),
            'calendar_block_count': len(self._migrating_calendar_blocks()),
            'delete_count': self._delete_count(),
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
            # Without a name the dialog falls back to the generic "Odoo" title: the
            # act_window record carries one, but these dicts replace it on every step.
            'name': _("Set up the next course"),
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

    def _apply_pending_graduates(self, graduates, order_index):
        """Step 2d — the graduates whose offer nobody has confirmed yet.

        'applicant' is not a workaround, it is the state that already models this exact
        situation: someone holding an offer for a study, with a portal user of their own
        (ems.portal.access.wizard covers 'applicant' and, unlike a minor, gives the
        applicant its own login rather than the family's), and with the return path
        already written — sale.order._ems_admit_student() converts an applicant back
        into a student on confirmation. An internal graduate holding an ASIX offer is in
        the very same position as an outsider who preinscribed to ASIX.

        Alumni is not an option: see _pending_graduates(). The portal is deliberately
        NOT revoked here, which is also why they are not archived.

        study_id and level_id follow the destination on the order, so they read as an
        applicant of the study they are heading to, not of the one they just finished.
        The exit metadata goes: they have not left, they are waiting to come back in.
        'has_graduated' stays — it is permanent, and it is what would make a later
        manual withdrawal land on alumni rather than on a withdrawal.
        """
        self.ensure_one()
        for graduate in graduates:
            study = order_index[graduate.id].ems_study_id
            graduate.write({
                'contact_type': 'applicant',
                'study_id': study.id or graduate.study_id.id,
                'level_id': study.level_id.id or graduate.level_id.id,
                'exit_type': False,
                'exit_course_id': False,
                'exit_date': False,
            })
        return len(graduates)

    def _apply_placement(self):
        """Steps 3 and 4 — destination group, then subject enrollments.

        Both are the one bulk call to sale.order._ems_apply_destination_placement(),
        already idempotent and already ordered (the ems.enrollment domain demands a
        'student', so the conversion has to come first). An enrollment confirmed
        without a destination group is skipped by the helper and was reported as
        'unplaced' in the preview. Returns the students actually placed, which step 4b
        needs to tell them from the ones nobody moved.
        """
        self.ensure_one()
        placed = self.env['res.partner']
        for order in self._incoming_orders():
            if not order.ems_group_id:
                continue
            student = order.partner_id
            # An applicant, or an ex-student coming back, has to be a student again
            # before it can hold subject enrollments.
            if student.contact_type in ('applicant', 'alumni', 'withdrawal'):
                student._ems_convert_to_student()
            order._ems_apply_destination_placement()
            placed |= student
        return placed

    def _apply_detach_unplaced(self, students, placed):
        """Step 4b — take whoever nobody placed out of the group that has just ended.

        ems.group carries the course number but not the academic year, so groups are
        reused: a student left pointing at the outgoing group turns up next September
        as a member of the new cohort. Leaving graduates already lost the group in step
        1 and placed students had it overwritten in step 3, so this is for everybody
        else — no enrollment at all, an unconfirmed one, or a confirmed one whose
        destination study is not in this run.

        It keys on who was actually placed, NOT on 'still sitting in a group of the
        scope': promoting a student from 1st to 2nd year of the same study lands in a
        scope group too, and that one must keep it.

        'study_id' and 'level_id' are deliberately kept: they say what the student was
        doing, which is what the "no destination" report and a late enrollment read.

        Also clears the outgoing group's own 'delegate_id' if it was one of these
        students - same stale-reference cleanup '_ems_clear_operational_records()' already
        does for a student leaving the centre entirely (see
        'res.partner._ems_clear_stale_delegate()'), needed here too since a stranded student
        keeps their group's delegate tag otherwise: the group itself is never archived
        (reused across years), only this student's own membership in it ends.
        """
        self.ensure_one()
        stranded = (students - placed).filtered(lambda student: student.main_group_id)
        for student in stranded:
            student._ems_clear_stale_delegate(student.main_group_id)
        stranded.write({'main_group_id': False})
        return len(stranded)

    def _apply_calendar_archival(self):
        """Step 7a — archives every migrating teacher calendar block found by
        `_migrating_calendar_blocks()`, then decides the fate of whichever `ems.attendance_schedule`
        line(s) it maps to - preferably read straight off the block's own `attendance_schedule_id`
        FK (added 2026-08-11 specifically to replace this kind of lookup, but never wired into this
        call site until 2026-09-02, see plans/calendar_driven_attendance_templates.md and
        plans/course_transition_stale_teacher_assignments.md's own follow-up analysis), falling back
        to `ems.attendance_mixin.find_schedule_lines_for_teaching` (matched by teacher+subject+group
        overlap+weekday/time - deliberately NOT by room, see that method's own docstring for why
        matching on room silently broke this exact link in real data) only for a legacy block whose
        calendar row predates that FK and was never resynced since:
        - A line that's ALREADY archived (the common case — `_templates_to_archive()`, called just
          before this, already cascaded to it) only needs its `attendance_session_ids` archived
          explicitly: that cascade never reaches sessions on its own (see
          `docs/en/developers/attendance/attendance_schedule.md`), and `_templates_to_archive()`
          already made the archival call unconditionally by study scope — no per-teacher check
          applies here.
        - A still-active line (`_templates_to_archive()` never touched its template — the
          decision-3/4 drift case: a calendar block can reference an in-scope group even when its
          own template doesn't) is decided at the TEMPLATE level, once per template, with the full
          set of departing teachers found across all of that template's migrating lines: if no
          other teacher still has an active block for any of them, the whole template is archived
          (cascading to its lines and their sessions); otherwise the departing teacher(s) are
          dropped via `_write_or_new_version()` (`ems.attendance_mixin`) — never a raw write. This
          matters because `teacher_ids` is a locked identity field once real attendance history
          exists (`has_sessions`): a raw write would retroactively change every already-taken
          session's own `template_teacher_ids` (related), rewriting who *actually* co-taught each
          past session. `_write_or_new_version` writes in place only when there's no history yet;
          otherwise it archives the original (leaving its own `teacher_ids` — and its sessions'
          `template_teacher_ids` — historically untouched) and clones a fresh, corrected version.

        Also catches a second, ORPHANED-line case (2026-08-10, developer feedback: "lo que manda es
        el calendario") right after the direct block-match loop: a migrating teacher's own
        still-active line whose (subject, group, weekday, time) is no longer backed by ANY of their
        current calendar blocks at all — not just the one that made them "migrating" — is treated
        as departed too, via the same `_teacher_has_active_block()` predicate used below for the
        opposite ("is a REMAINING co-teacher still genuinely supported") check. Real scenario this
        covers: a teacher edits their calendar by hand, bypassing the normal sync, so an old line
        (a different group/time the calendar no longer shows at all) would otherwise never be found
        by the direct match and would linger active forever.

        Deciding per template rather than per line also avoids ever creating a needless clone: if
        every one of a template's co-teachers departs in the same run, `remaining` is empty and the
        whole template is simply archived outright, no `_write_or_new_version` call at all.

        Finally, a third, fully UNSCOPED catch-up (2026-08-10, found re-running a real transition):
        every already-archived line anywhere with still-active sessions gets its sessions archived
        too - deliberately not limited to this run's own `affected_teachers`/`study_ids`, since a
        teacher whose calendar was already fully archived in an EARLIER run (zero active blocks
        left, so they never enter `affected_teachers` this time either) can still have a stale line
        from back then whose session catch-up was simply never reached by either check above.

        Returns the distinct set of teachers whose calendar had at least one migrating block this
        run - captured *before* archiving them, since `_migrating_calendar_blocks()`'s own search
        would otherwise silently exclude them once archived - for `_apply_calendar_rollover()` to
        check afterwards (phases 6-7).

        See plans/course_transition_teacher_schedule_archival.md, phase 5c.
        """
        self.ensure_one()
        blocks = self._migrating_calendar_blocks()
        affected_teachers = blocks.mapped('employee_id')
        line_departures = {}
        for block in blocks:
            teacher = block.employee_id
            if not teacher:
                continue
            # A direct Many2one field read (unlike search()) never filters by active_test on its
            # own, so an already-archived line (see the comment below on why that case still needs
            # handling here) is found via the FK exactly as reliably as an active one - no explicit
            # with_context(active_test=False) needed for this branch. '.exists()' is defensive only
            # (a schedule line is never hard-deleted while it has real session history, and archived
            # otherwise - see ems.attendance_schedule.unlink() - but a stale FK is cheap to guard).
            if block.attendance_schedule_id:
                lines = block.attendance_schedule_id.exists()
            else:
                # active_test=False: a matching line may already be archived by the EARLIER
                # _templates_to_archive().action_archive() call (its own cascade only reaches the
                # line, never its sessions, per decision 6) - that case still needs handling below
                # (catching up the sessions), so it must not be silently excluded from this search.
                lines = self.env['ems.attendance_schedule'].with_context(active_test=False).find_schedule_lines_for_teaching(
                    teacher, block.subject_id, block.group_ids, block.dayofweek, block.hour_from, block.hour_to)
            for line in lines:
                line_departures[line] = line_departures.get(line, self.env['hr.employee']) | teacher
        blocks.action_archive()

        # NEW (2026-08-10, developer feedback: "lo que manda es el calendario"): a migrating
        # teacher's own still-active line whose (subject, group, weekday, time) is no longer
        # backed by ANY of their current calendar blocks at all - not just the specific block
        # that made them "migrating" above - counts as departed too. Real example that surfaced
        # this: a teacher edits their calendar by hand, bypassing the normal sync, so the OLD
        # line (a different group/time the calendar no longer shows at all) is never found by
        # the direct block-match loop above and would otherwise linger active forever.
        for teacher in affected_teachers:
            # Explicit ('active', '=', True) keeps the search itself scoped to currently-active
            # lines only (matching the intent - an already-archived line needs no departure
            # processing here) - but 'with_context(active_test=False)' still propagates through
            # 'line.attendance_template_id' below, all the way to '_write_or_new_version''s own
            # 'new_template.attendance_schedule_ids.action_unarchive()' call further down: without
            # it, that later read would silently exclude the freshly-cloned (still momentarily
            # inactive) line, so it would never actually get unarchived.
            own_lines = self.env['ems.attendance_schedule'].with_context(active_test=False).search([
                ('attendance_template_id.teacher_ids', 'in', teacher.id),
                ('active', '=', True),
            ])
            for line in own_lines:
                if line not in line_departures and not self._teacher_has_active_block(teacher, line):
                    line_departures[line] = line_departures.get(line, self.env['hr.employee']) | teacher

        departures_by_template = {}
        for line, departing in line_departures.items():
            if not line.active:
                # Already archived by _templates_to_archive() - that mechanism already decided,
                # unconditionally by study scope, that this class is ending; no per-teacher check
                # applies here. Only catch up the one piece its own cascade deliberately skips.
                line.attendance_session_ids.action_archive()
                continue
            template = line.attendance_template_id
            departures_by_template[template] = departures_by_template.get(template, self.env['hr.employee']) | departing

        for template, departing in departures_by_template.items():
            lines = template.attendance_schedule_ids
            remaining = template.teacher_ids - departing
            still_needed = remaining.filtered(
                lambda teacher: any(self._teacher_has_active_block(teacher, line) for line in lines))
            if still_needed:
                # A full replacement command, not a (3, id) "unlink" one: _write_or_new_version's
                # archive+clone branch applies 'vals' via copy()'s own 'default' argument, which
                # populates the brand-new record's teacher_ids from 'vals' alone rather than
                # merging it with the original's - a (3, id) command there has nothing to unlink
                # from and silently leaves teacher_ids empty, tripping _check_teacher_ids.
                new_template = template._write_or_new_version({'teacher_ids': [(6, 0, remaining.ids)]})
                if new_template != template:
                    new_template.attendance_schedule_ids.action_unarchive()
            else:
                lines.attendance_session_ids.action_archive()
                template.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()

        # Unconditional, unscoped catch-up (2026-08-10, found re-running a real transition after
        # the fix above): an ALREADY-archived line with still-active sessions is always a bug,
        # regardless of when or why it was archived - deliberately NOT limited to this run's own
        # 'affected_teachers'/'study_ids'. The two checks above only ever look at a teacher who is
        # CURRENTLY migrating (has an active calendar block, or an active line to compare against
        # one) - a teacher whose entire calendar was already fully archived in an EARLIER run (no
        # active blocks left at all, so they never even entered 'affected_teachers' this time)
        # can still have a stale line from back then whose session catch-up was simply never
        # reached - real example that surfaced this: David Delgado's own template/line had
        # already been archived by a previous run, his whole 2025-2026 calendar was already
        # archived too (fully rolled over already), yet 4 of his session headers stayed active
        # because nothing ever triggered a look at that specific, by-then-inactive line again.
        self.env['ems.attendance_schedule'].with_context(active_test=False).search([
            ('active', '=', False), ('attendance_session_ids.active', '=', True),
        ]).mapped('attendance_session_ids').action_archive()
        return affected_teachers

    def _apply_calendar_rollover(self, teachers):
        """Step 7b — phases 6+7 of the plan: for every teacher `_apply_calendar_archival()` just
        touched, checks whether their CURRENT calendar has zero remaining *active teaching* blocks
        (a non-teaching commitment - guard duty, a meeting... - doesn't count, and doesn't block the
        rollover) — if so, rolls them onto a calendar for `target_course_id`, reactivating one
        already made for that exact (teacher, course) pair if one exists (a previous transition
        cycle already created and archived it), minting a fresh one otherwise, seeded from whatever
        framework the outgoing calendar itself followed (falling back to the company's own default
        framework for a calendar that was never seeded from one). The now-empty calendar is
        archived — never left orphaned (decision 5) — and `resource_calendar_id` reassigned.

        A calendar that still has real teaching left (e.g. this teacher also teaches a study that
        hasn't transitioned yet) is left completely untouched here — this is deliberately NOT a
        blanket per-teacher rollover, only ever triggered by the specific condition decision 5/7
        describe.
        """
        self.ensure_one()
        for teacher in teachers:
            calendar = teacher.resource_calendar_id
            if calendar.is_framework or calendar.attendance_ids.filtered(
                    lambda attendance: attendance.active and not attendance.non_teaching):
                continue
            next_calendar = self.env['resource.calendar'].with_context(active_test=False).search([
                ('employee_id', '=', teacher.id), ('course_id', '=', self.target_course_id.id),
            ], limit=1)
            if next_calendar:
                next_calendar.action_unarchive()
            else:
                next_calendar = self.env['resource.calendar'].create({
                    'employee_id': teacher.id, 'course_id': self.target_course_id.id,
                })
                next_calendar.seed_from_framework(
                    calendar.source_framework_id or self.env.company.default_schedule_framework_id)
            calendar.action_archive()
            teacher.resource_calendar_id = next_calendar

    def _apply_teaching_resync(self, teachers):
        """Step 7c (added 2026-09-01, see plans/course_transition_stale_teacher_assignments.md) -
        resyncs 'ems.teaching' for every teacher `_apply_calendar_archival()` found migrating,
        straight from their own CURRENT 'resource_calendar_id' (whichever `_apply_calendar_
        rollover()` just above left them on: a fresh one for a fully rolled-over teacher, empty
        of teaching entries; the SAME one, partially archived, for a teacher who still teaches
        part of their old schedule). Mirrors 'ems.attendance_template.regenerate_all_from_
        calendars()' 's own calendar-as-source-of-truth resync, but scoped and lightweight - never
        touches templates, so it is safe to call from this interactive wizard action (unlike
        'regenerate_all_from_calendars()', whose own docstring restricts it to an offline
        migration window).

        This is the ONLY place 'ems.teaching' ever gets reconciled as a consequence of a course
        transition - before this, a departed/reassigned teacher's stale teaching links (and, via
        'ems.teaching.unlink()' 's own cleanup, their group's stale 'tutor_id') survived
        indefinitely, since neither the calendar archival above nor the working-schedule
        importer's own call to 'ems.teaching.sync_from_schedule(..., replace=False)' (deliberately
        additive-only, by design - one imported file is only ever one slice of the centre's
        schedule) ever remove a stale entry outright."""
        for teacher in teachers:
            self.env['ems.teaching'].sync_from_schedule(teacher, teacher._teaching_entries_from_calendar())

    def _teacher_has_active_block(self, teacher, line):
        """Whether 'teacher' still has an active resource.calendar.attendance block matching
        'line's own teaching assignment - same subject, any group overlap, and weekday/time
        overlap. Deliberately NOT room (2026-08-10, developer feedback: "lo que manda es el
        calendario... el aula no deberíamos usarla para las búsquedas") - a teacher can freely
        change the room while taking attendance, so matching on it would break the very link
        this check exists to find, same reasoning as 'ems.attendance_mixin.find_schedule_lines_
        for_teaching'. Backs both directions of '_apply_calendar_archival''s per-teacher checks:
        a REMAINING co-teacher genuinely still supported (its original use), and a DEPARTING
        teacher's own line with no calendar support left at all (the newer orphaned-line case,
        see that method's own docstring).

        Built on 'hr.employee._teaching_entries_from_calendar()' (Phase 4 of
        plans/calendar_pipeline_simplification.md, 2026-09-02) rather than its own standalone
        'resource.calendar.attendance' query - the exact same "what does this teacher's calendar
        say they teach right now" primitive '_apply_teaching_resync()' just below already reuses,
        so this check can never silently drift from what the rest of the pipeline considers a
        real, current teaching entry."""
        template = line.attendance_template_id
        return any(
            entry['subject_id'] == template.subject_id.id
            and set(entry['group_ids']) & set(template.group_ids.ids)
            and entry['dayofweek'] == line.weekday
            and line.ranges_overlap(line.start_time, line.end_time, entry['hour_from'], entry['hour_to'])
            for entry in teacher._teaching_entries_from_calendar()
        )

    def _apply_attendance_records_archival(self):
        """Archives every ems.attendance_justification / ems.attendance_issue_status (+ its
        now-emptied ems.attendance_issue_student/ems.attendance_issue_tutor parents) whose
        underlying attendance is already archived - found 2026-08-10 auditing real dev data
        before a batch import: 2 justifications and 27 "daily issue" rows (10 tutor + 17 status)
        were sitting active, all referencing sessions that were themselves already correctly
        archived. Neither model has any direct link to the course/study being transitioned - only
        an indirect one through the ems.attendance_session_header they were generated for - and
        `_ems_clear_operational_records()` (the other place attendance issues get cleaned up,
        by DELETING them for a student actually leaving the centre) only runs for students in
        `_scope_students()`, which is captured by CURRENT group membership - a student already
        detached from any group (e.g. by an earlier run's `_apply_detach_unplaced()`, or a
        reinforcement-group student never captured by `main_group_id` at all) falls outside that
        scope forever, exactly the gap that left the real leftover data behind. This check is
        keyed on the session's own archived state instead, which both catches that gap and stays
        correct regardless of which specific transition run originally archived the session.

Called from `_apply_cleanup()` **last**, after `students._ems_clear_operational_records()`
        (moved there 2026-08-10, found the hard way: calling it earlier archived an issue_student/
        _tutor with zero children *before* `_ems_clear_operational_records()` got a chance to
        search for and DELETE that same record for a student genuinely leaving in this run - that
        method's own search only ever sees `active=True` rows by default, so the already-archived
        record became invisible to it and survived archived instead of deleted). Running last
        means this only ever catches what that deletion step was never going to touch anyway -
        this run's own newly-archived sessions, and any pre-existing stray leftover from an
        earlier run (e.g. a student already stranded before this run even started). Archives
        (never deletes) - unlike `_ems_clear_operational_records()`'s deletion, which is
        specifically justified there for a student who has actually left and whose stats are
        already frozen in the year record; these records have no such freezing step, so archiving
        (keeping them findable via the "Archived" filter) is the safer default, matching every
        other attendance model in this system.

        **Justifications: `attendance_session_line_ids` is NOT the real link** (found 2026-08-10,
        re-running a real transition after the first version of this method - 2 justifications
        still survived it with zero lines on that M2M). That field is a form-editing convenience
        ("Many2many needed in order to update values" per its own code comment) kept in sync with
        the real link only when a justification is created/edited *through the UI*. The real,
        authoritative link is `ems.attendance_session_line.attendance_justification_id`/
        `attendance_prevision_id` (a Many2one FROM the line TO the justification) - set
        automatically by `_auto_populate_lines()` whenever a session gets created for a date a
        justification already covers (`EmsAttendanceJustification.get_current_justifications()`),
        *without* ever syncing that back onto the justification's own M2M. So a real, dated-in-
        the-past justification can legitimately show zero entries on `attendance_session_line_ids`
        while still being linked from the line side, or - the actual case found - never having any
        session at all for its covered dates once the course it belongs to has fully ended. Checks
        both relations (`|`, unioned) per justification, and treats zero lines *of either kind* as
        just as archivable as "all archived", but only once its own `end_date` has already passed
        - protects a genuine future "prevision" (a justification submitted ahead of an expected
        absence that hasn't happened yet) from being swept up just because no session has been
        created for it yet.

        **Issue student/tutor: check every record's current children directly, not just the ones
        this call's own status-archival just emptied** (same finding, same day - 2 issue_student
        and 2 issue_tutor rows had ZERO status children from the start, so they never appeared in
        the "just archived" set at all and were never re-checked). Reads the model's own default
        active-filtered relation directly instead."""
        self.ensure_one()
        today = fields.Datetime.now()
        for justification in self.env['ems.attendance_justification'].sudo().search([('end_date', '<', today)]):
            lines = justification.attendance_session_line_ids | self.env['ems.attendance_session_line'].sudo().search([
                '|', ('attendance_justification_id', '=', justification.id),
                ('attendance_prevision_id', '=', justification.id),
            ])
            if not any(lines.mapped('attendance_session_id.active')):
                justification.action_archive()

        issue_statuses = self.env['ems.attendance_issue_status'].sudo().search([
            ('attendance_session_line_id.attendance_session_id.active', '=', False),
        ])
        issue_statuses.action_archive()
        self.env['ems.attendance_issue_student'].sudo().search([]).filtered(
            lambda student: not student.attendance_issue_status_ids
        ).action_archive()
        self.env['ems.attendance_issue_tutor'].sudo().search([]).filtered(
            lambda tutor: not tutor.attendance_issue_student_ids
        ).action_archive()

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
        # action_archive() (not a plain write()) is what cascades to the template's own
        # attendance_schedule_ids (see EmsAttendanceTemplate.action_archive) - a bare write()
        # here left those lines active=True forever, so a later import could still find them
        # as a genuine "existing schedule conflict" against a study that had already transitioned.
        self._templates_to_archive().with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()
        affected_teachers = self._apply_calendar_archival()
        self._apply_calendar_rollover(affected_teachers)
        self._apply_teaching_resync(affected_teachers)
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
        # Runs LAST, after _ems_clear_operational_records() (2026-08-10, found the hard way): this
        # archives any attendance_issue_student/_tutor with zero active children, which would
        # otherwise silently swallow the very records _ems_clear_operational_records() still
        # needs to find and DELETE for a student actually leaving in THIS run (its own search
        # only looks at active=True records by default - an already-archived one becomes
        # invisible to it, surviving archived instead of deleted). Running last means it only
        # ever catches genuine leftovers _ems_clear_operational_records() was never going to
        # touch anyway (e.g. a student already stranded by an earlier run).
        self._apply_attendance_records_archival()

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
        # 'is_enrollment_default' is deliberately left alone (D16): enrollments keep
        # being processed in September for the course that has just started, and the
        # flag is what every "which course do new enrollments belong to" lookup reads.
        # Clearing it left none flagged and broke all of them at once.
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

    def _apply_audit(self, flipped, issues, locked, cancelled, detached):
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
            _("Graduated, pending confirmation: %s") % self.graduate_pending_count,
            _("Placed: %s") % self.place_count,
            _("Without destination: %s") % self.missing_count,
            _("Detached from the outgoing group: %s") % detached,
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
        pending = self._pending_graduates(order_index)

        self._apply_history(students)
        issues = self._apply_graduates(graduates)
        self._apply_continuing_graduates(continuing)
        self._apply_pending_graduates(pending, order_index)
        self._apply_cleanup(students)
        placed = self._apply_placement()
        detached = self._apply_detach_unplaced(students, placed)
        flipped = self._apply_transition_flip()
        locked, cancelled = self._apply_outgoing_enrollments()
        self._apply_audit(flipped, issues, locked, cancelled, detached)

        self.state = 'done'
        return {
            'type': 'ir.actions.act_window',
            # Without a name the dialog falls back to the generic "Odoo" title: the
            # act_window record carries one, but these dicts replace it on every step.
            'name': _("Set up the next course"),
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
