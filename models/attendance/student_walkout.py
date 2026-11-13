# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

GROUP_VOTES = ('yes', 'no', 'abstain')
JUSTIFY_TASK = 'ems.mail_activity_student_walkout_justify'
# What the group sees: a call cancelled by its delegate is only theirs.
VISIBLE_STATES = ('voting', 'joining', 'closed', 'justified', 'rejected')
# The group's tutor (and the chain above them) may abort a call while it is voted or joined; once
# closed, the Head of Studies validates it (justifies) or not, and may undo a validation.
ABORTABLE_STATES = ('voting', 'joining')
VALIDATION_STATES = ('closed', 'justified')


class EmsStudentWalkout(models.Model):
    """Issue #800: a student walkout (a strike called by a students' union), opened from the portal
    by a group's delegate or sub-delegate and voted by the group. "Walkout", never "strike":
    ems.strike is the disciplinary record. See docs/en/developers/attendance/student_walkout.md."""
    _name = 'ems.student_walkout'
    _description = "Student walkout call"
    _inherit = ['ems.base', 'ems.datetime_utils']
    _order = 'walkout_date desc, id desc'

    name = fields.Char(string="Name", compute='_compute_name', store=True)
    group_id = fields.Many2one(string="Group", comodel_name='ems.group', required=True, readonly=True,
                               ondelete='restrict', index=True)
    # The halves of a split group sharing the delegate vote together.
    group_ids = fields.Many2many(string="Groups", comodel_name='ems.group', relation='ems_student_walkout_group_rel',
                                 column1='walkout_id', column2='group_id', readonly=True)
    opener_id = fields.Many2one(string="Opened by", comodel_name='res.partner', required=True, readonly=True,
                                ondelete='restrict')
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', readonly=True, ondelete='restrict')
    company_id = fields.Many2one(string="Company", comodel_name='res.company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    walkout_date = fields.Date(string="Walkout day", required=True, readonly=True)
    # The calendar, in school hours (ems.datetime_utils.ems_add_school_hours): each phase starts when
    # its email reaches the students (their next class, _ems_send_moment) and lasts phase_hours; the
    # Head of Studies gets the minute at least notice_hours before walkout_start. Both kept from the
    # settings the call was opened with.
    walkout_start = fields.Datetime(string="Walkout starts", compute='_compute_walkout_start')
    phase_hours = fields.Integer(string="Phase (school hours)", readonly=True)
    notice_hours = fields.Integer(string="Notice (school hours)", readonly=True)
    vote_start = fields.Datetime(string="Group vote from", readonly=True, copy=False)
    vote_until = fields.Datetime(string="Group vote until", readonly=True, copy=False)
    join_start = fields.Datetime(string="Joining from", readonly=True, copy=False)
    join_until = fields.Datetime(string="Joining until", readonly=True, copy=False)
    notes = fields.Text(string="Notes", readonly=True)
    attachment_ids = fields.Many2many(string="Union's call", comodel_name='ir.attachment',
                                      relation='ems_student_walkout_attachment_rel', column1='walkout_id',
                                      column2='attachment_id', readonly=True)
    state = fields.Selection(string="State", selection=[
        ('voting', "Voting"),
        ('joining', "Joining"),
        ('closed', "Closed"),
        ('justified', "Justified"),
        ('rejected', "Rejected"),
        ('cancelled', "Cancelled"),
    ], required=True, default='voting', readonly=True)
    # Aborted by the tutor while voted or joined, or not validated by the Head of Studies once
    # closed: always with a reason.
    rejected_by_id = fields.Many2one(string="Rejected by", comodel_name='res.users', readonly=True, copy=False)
    rejected_datetime = fields.Datetime(string="Rejected on", readonly=True, copy=False)
    rejection_reason_id = fields.Many2one(string="Rejection reason", comodel_name='ems.student_walkout.rejection_reason',
                                          readonly=True, copy=False, ondelete='restrict')
    rejection_details = fields.Text(string="Rejection details", readonly=True, copy=False)
    # The state it was rejected from: aborted (voting, joining), not validated (closed) or validation
    # undone (justified). It decides what the group and the families are told.
    rejected_from_state = fields.Selection(string="Rejected while", selection=[
        ('voting', "Voting"),
        ('joining', "Joining"),
        ('closed', "Closed"),
        ('justified', "Justified"),
    ], readonly=True, copy=False)
    can_abort = fields.Boolean(compute='_compute_can_reject')
    can_reject = fields.Boolean(compute='_compute_can_reject')
    # The group vote, anonymous: only the counts, never who voted what (_ems_portal_vote).
    group_yes_count = fields.Integer(string="Group supports it", readonly=True, copy=False)
    group_no_count = fields.Integer(string="Group does not support it", readonly=True, copy=False)
    group_abstain_count = fields.Integer(string="Abstentions", readonly=True, copy=False)
    group_supports = fields.Boolean(string="The group supports it", compute='_compute_group_supports')
    line_ids = fields.One2many(string="Students", comodel_name='ems.student_walkout.line', inverse_name='walkout_id',
                               readonly=True)
    joining_student_ids = fields.Many2many(string="Students who join", comodel_name='res.partner',
                                           compute='_compute_line_counts')
    # Those who join and can be justified: adults, and minors whose family ratified it.
    justifiable_student_ids = fields.Many2many(string="Students who can be justified", comodel_name='res.partner',
                                               compute='_compute_line_counts')
    joining_count = fields.Integer(string="Join", compute='_compute_line_counts')
    voter_count = fields.Integer(string="May vote", compute='_compute_line_counts')
    voted_count = fields.Integer(string="Voted", compute='_compute_line_counts')
    join_answered_count = fields.Integer(string="Answered whether they join", compute='_compute_line_counts')
    closed_datetime = fields.Datetime(string="Closed on", readonly=True, copy=False)
    head_of_studies_id = fields.Many2one(string="Head of Studies", comodel_name='hr.employee', readonly=True,
                                         copy=False, ondelete='set null')
    pdf_attachment_id = fields.Many2one(string="Minute", comodel_name='ir.attachment', readonly=True, copy=False,
                                        ondelete='set null')
    justification_id = fields.Many2one(string="Justification", comodel_name='ems.attendance_justification',
                                       readonly=True, copy=False, ondelete='set null')
    can_generate_justification = fields.Boolean(compute='_compute_can_generate_justification')

    @api.depends('group_id.name', 'walkout_date')
    def _compute_name(self):
        # In the centre's language, whoever opens it: the name is stored and names the minute.
        centre = self.env['res.company']._ems_centre_env()
        for walkout in self:
            walkout.name = walkout.group_id.name and walkout.walkout_date and \
                f"{walkout.group_id.name} - {format_date(centre, walkout.walkout_date)}"

    @api.depends('walkout_date')
    def _compute_walkout_start(self):
        for walkout in self:
            walkout.walkout_start = walkout._ems_day_start(walkout.walkout_date)

    @api.depends('group_yes_count', 'group_no_count')
    def _compute_group_supports(self):
        for walkout in self:
            walkout.group_supports = walkout.group_yes_count > walkout.group_no_count

    @api.depends('line_ids.joins', 'line_ids.voted', 'line_ids.has_portal', 'line_ids.join_answered',
                 'line_ids.justifiable')
    def _compute_line_counts(self):
        for walkout in self:
            joining = walkout.line_ids.filtered('joins')
            walkout.joining_student_ids = joining.student_id
            walkout.justifiable_student_ids = joining.filtered('justifiable').student_id
            walkout.joining_count = len(joining)
            walkout.voter_count = len(walkout.line_ids.filtered('has_portal'))
            walkout.voted_count = len(walkout.line_ids.filtered('voted'))
            walkout.join_answered_count = len(walkout.line_ids.filtered('join_answered'))

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_can_reject(self):
        for walkout in self:
            walkout.can_abort = walkout.state in ABORTABLE_STATES and walkout._ems_user_may_abort()
            walkout.can_reject = walkout.state in VALIDATION_STATES and walkout._ems_user_may_reject()

    @api.depends('state', 'line_ids.justifiable', 'group_yes_count', 'group_no_count')
    @api.depends_context('uid')
    def _compute_can_generate_justification(self):
        for walkout in self:
            walkout.can_generate_justification = walkout._ems_has_something_to_justify() and \
                walkout._ems_user_may_justify()

    # Portal: the controller passes the logged-in student; everything is checked here.

    @api.model
    def _ems_portal_open(self, partner, values, files):
        """Opens a walkout call for `partner`'s group: `values` has walkout_date and notes, `files` the
        union's call as (name, content) pairs. The group votes at once, with no review first."""
        partner = partner.sudo()
        group = partner._ems_walkout_opener_group()
        if not group:
            raise UserError(_("Only the delegate or the sub-delegate of a group that may call a student walkout "
                              "can open one."))
        groups = partner._ems_walkout_opener_groups()
        walkout_date = fields.Date.to_date(values.get('walkout_date'))
        calendar = self._ems_projected_calendar(groups)
        self._ems_check_request_date(walkout_date, calendar)
        files = [(name, content) for name, content in files or [] if name and content]
        if not files:
            raise UserError(_("Attach the call of the students' union."))
        if self.search_count([('group_ids', 'in', groups.ids), ('walkout_date', '=', walkout_date),
                              ('state', '!=', 'cancelled')]):
            raise UserError(_("Your group already has a student walkout call for %(date)s.",
                              date=format_date(self.env, walkout_date)))
        students = self.env['res.partner'].search([('contact_type', '=', 'student'),
                                                   ('main_group_id', 'in', groups.ids)])
        with_portal = set(self.env['res.users'].search([('partner_id', 'in', students.ids),
                                                        ('share', '=', True)]).partner_id.ids)
        walkout = self.create({
            'group_id': group.id,
            'group_ids': [(6, 0, groups.ids)],
            'opener_id': partner.id,
            'course_id': self.env.company.current_course_id.id,
            'walkout_date': walkout_date,
            'phase_hours': calendar['phase_hours'],
            'notice_hours': calendar['notice_hours'],
            'vote_start': calendar['vote_start'],
            'vote_until': calendar['vote_until'],
            'notes': (values.get('notes') or '').strip()[:2000] or False,
            'line_ids': [(0, 0, {'student_id': student.id, 'has_portal': student.id in with_portal})
                         for student in students],
        })
        walkout.attachment_ids = self.env['ir.attachment'].create([{
            'name': name, 'raw': content, 'res_model': self._name, 'res_id': walkout.id,
        } for name, content in files])
        walkout._message_log(body=_("Opened by %(name)s from the portal.", name=partner.name))
        walkout._ems_start_voting()
        return walkout

    def _ems_portal_line(self, partner):
        line = self.line_ids.filtered(lambda line: line.student_id == partner and line.has_portal)
        if not line:
            raise UserError(_("Only the students of the group with access to the portal can answer."))
        return line

    def _ems_portal_vote(self, partner, group_vote):
        """`partner` votes whether the group supports the walkout: once, never linked to them. The
        vote ends as soon as its result is decided (_ems_vote_decided)."""
        self.ensure_one()
        line = self._ems_portal_line(partner)
        if not self._ems_phase_open('voting'):
            raise UserError(_("The group vote of this student walkout is closed."))
        if line.voted:
            raise UserError(_("You have already voted: the group vote cannot be changed."))
        if group_vote not in GROUP_VOTES:
            raise UserError(_("Say whether the group supports the walkout."))
        # Two answers at the same time update the same rows: PostgreSQL refuses the second
        # (REPEATABLE READ) and Odoo retries it, so no vote is lost nor counted twice.
        counter = f'group_{group_vote}_count'
        self.write({counter: self[counter] + 1})
        line.write({'voted': True, 'vote_date': fields.Datetime.now()})
        if self._ems_vote_decided():
            self._ems_end_group_vote()

    def _ems_portal_join(self, partner, joins):
        """`partner` says whether they join the walkout, by name; changeable until joining ends. A
        minor joining needs their family to ratify it (Decret 102/2010, art. 24.2): the family is
        asked at once; withdrawing clears it, joining again asks again."""
        self.ensure_one()
        line = self._ems_portal_line(partner)
        if not self._ems_phase_open('joining'):
            raise UserError(_("Joining this student walkout is closed."))
        vals = {'joins': bool(joins), 'join_answered': True, 'join_date': fields.Datetime.now()}
        asks = bool(joins) and not line.joins and self._ems_is_minor(line.student_id)
        if not joins:
            vals.update({'needs_ratification': False, 'ratification': False, 'ratified_by_id': False,
                         'ratification_date': False})
        elif asks:
            vals.update({'needs_ratification': True, 'ratification': 'pending', 'ratified_by_id': False,
                         'ratification_date': False})
        line.write(vals)
        if asks:
            self._ems_mail_families('ems.email_template_student_walkout_ratify', line)

    def _ems_is_minor(self, student):
        """Under 18 on the walkout day; a student with no birth date counts as a minor."""
        # Imported here: importing contacts/ at load time would register its res.partner
        # extensions before contacts' own, changing their order.
        from ..contacts.coming_of_age import ADULT_AGE
        self.ensure_one()
        birth_date = student.sudo().birth_date
        return not birth_date or relativedelta(self.walkout_date, birth_date).years < ADULT_AGE

    def _ems_portal_ratify(self, family, line, ratifies):
        """`family` ratifies (or refuses) that its child joins, on the portal, while joining lasts; it
        can change its answer meanwhile. Only a family contact of the student with portal access. A
        refusal is told to the student: their absence will not be justified."""
        self.ensure_one()
        family = family.sudo()
        if line.walkout_id != self or not (line.joins and line.needs_ratification):
            raise UserError(_("There is nothing to ratify for this student."))
        if not family.user_ids.filtered('share') or family not in line.student_id._ems_family_contacts():
            raise UserError(_("Only the family of the student, with access to the portal, can ratify it."))
        if not self._ems_phase_open('joining'):
            raise UserError(_("The time to ratify it is over: joining this student walkout is closed."))
        refused_now = not ratifies and line.ratification != 'refused'
        line.write({'ratification': 'ratified' if ratifies else 'refused', 'ratified_by_id': family.id,
                    'ratification_date': fields.Datetime.now()})
        if refused_now:
            self._ems_mail_students('ems.email_template_student_walkout_ratification_refused', line)

    def _ems_portal_cancel(self, partner):
        self._ems_check_manager(partner)
        if self.state not in ('voting', 'joining'):
            raise UserError(_("Only a call still being voted or joined can be cancelled."))
        self.state = 'cancelled'
        self._message_log(body=_("Cancelled by %(name)s from the portal.", name=partner.name))

    def _ems_is_manager(self, partner):
        """The opener, or the group's current delegate or sub-delegate, manage the call."""
        self.ensure_one()
        return partner == self.opener_id or partner in (self.group_ids.delegate_id | self.group_ids.subdelegate_id)

    def _ems_check_manager(self, partner):
        if not self._ems_is_manager(partner):
            raise UserError(_("Only the delegate or the sub-delegate of the group can manage this call."))

    # The calendar

    def _ems_day_start(self, day):
        """00:00 of `day` in the centre, naive UTC: the walkout starts then."""
        return day and self.datetime_to_odoo(self.time_float_to_utc_datetime(day, 0.0))

    @api.model
    def _ems_send_moment(self, groups, moment):
        """When an email sent at `moment` reaches the students of `groups`: then during their
        classes, otherwise at the next ones (the latest group's)."""
        return max(group._ems_school_send_time(moment) or moment for group in groups)

    @api.model
    def _ems_phase(self, groups, moment, hours):
        """A phase whose email is sent at `moment`: from when it reaches the students, `hours` school
        hours long."""
        start = self._ems_send_moment(groups, moment)
        return start, self.ems_add_school_hours(start, hours)

    @api.model
    def _ems_projected_calendar(self, groups, now=None):
        """The calendar of a call opened `now` for `groups`, the group vote taking its whole phase:
        the latest the minute can reach the Head of Studies (join_until)."""
        company = self.env.company
        phase, notice = company.walkout_phase_hours, company.walkout_notice_hours
        vote_start, vote_until = self._ems_phase(groups, now or fields.Datetime.now(), phase)
        join_start, join_until = self._ems_phase(groups, vote_until, phase)
        return {
            'phase_hours': phase, 'notice_hours': notice,
            'vote_start': vote_start, 'vote_until': vote_until,
            'join_start': join_start, 'join_until': join_until,
        }

    @api.model
    def _ems_notice_kept(self, calendar, day):
        """Whether a walkout on `day` keeps the notice: the minute at least notice_hours school hours
        before its 00:00."""
        return self.ems_school_hours_between(calendar['join_until'], self._ems_day_start(day)) >= \
            calendar['notice_hours']

    @api.model
    def _ems_first_walkout_day(self, calendar):
        """The first school day a call with this calendar can be for."""
        first = self.utc_to_local_date(calendar['join_until'])
        school_days = sorted(self._ems_school_days(first, fields.Date.add(first, days=366)))
        return next((day for day in school_days if self._ems_notice_kept(calendar, day)), False)

    @api.model
    def _ems_check_request_date(self, walkout_date, calendar):
        """The group vote and the joining take a phase each and the minute must reach the Head of
        Studies the notice before the walkout, all in school hours."""
        if not walkout_date:
            raise UserError(_("Give the walkout day."))
        if not self._ems_school_days(walkout_date, walkout_date):
            raise UserError(_("A student walkout can only be called for a school day."))
        if not self._ems_notice_kept(calendar, walkout_date):
            raise UserError(_(
                "It is too late to call a student walkout for %(day)s: the group vote and the joining take "
                "%(phase)s school hours each and the Head of Studies must get the minute %(notice)s school hours "
                "before the walkout (weekends, public holidays and school breaks do not count). A call opened "
                "now can be for %(first)s at the earliest.", day=format_date(self.env, walkout_date),
                phase=calendar['phase_hours'], notice=calendar['notice_hours'],
                first=format_date(self.env, self._ems_first_walkout_day(calendar))))

    def _ems_phase_open(self, state):
        """Whether the phase `state` (voting, joining) is open: the call is in it and its end has not
        come. Students may answer before its start too (e.g. on the weekend before)."""
        self.ensure_one()
        until = self.vote_until if state == 'voting' else self.join_until
        return self.state == state and bool(until) and fields.Datetime.now() < until

    def _ems_vote_decided(self):
        """Whether the group vote's result is known: everybody voted, or the votes still to come
        cannot change it (support needs more yes than no)."""
        self.ensure_one()
        to_come = self.voter_count - self.voted_count
        yes, no = self.group_yes_count, self.group_no_count
        return to_come <= 0 or yes > no + to_come or yes + to_come <= no

    def _ems_wake_cron_at(self, moment):
        """Runs the deadlines cron exactly when a phase ends (the hourly run is only the safety net)."""
        cron = self.env.ref('ems.ir_cron_student_walkout_deadlines', raise_if_not_found=False)
        if cron and moment:
            cron.sudo()._trigger(at=moment)

    # The phases

    def _ems_start_voting(self):
        """The group votes at once: each student with portal access gets the email, and so does the
        group's tutor, who may abort the call."""
        self.ensure_one()
        self._ems_mail_students('ems.email_template_student_walkout_call')
        self._ems_mail_tutors('call')
        self._ems_wake_cron_at(self.vote_until)

    @api.model
    def _cron_ems_walkout_deadlines(self):
        """At each phase's end (woken up then, hourly as a safety net): the group vote ends; the
        joining ends and the call closes."""
        now = fields.Datetime.now()
        self.search([('state', '=', 'voting'), ('vote_until', '<=', now)])._ems_end_group_vote()
        self.search([('state', '=', 'joining'), ('join_until', '<=', now)])._ems_close()

    def _ems_end_group_vote(self):
        """The group vote ends: if the group supports the walkout, each student is told the result and
        has a phase to say whether they join (from when the email reaches them); otherwise the call
        closes (nobody is justified)."""
        for walkout in self.filtered(lambda walkout: walkout.state == 'voting'):
            if walkout.group_supports:
                join_start, join_until = walkout._ems_phase(walkout.group_ids, fields.Datetime.now(),
                                                            walkout.phase_hours)
                walkout.write({'state': 'joining', 'join_start': join_start, 'join_until': join_until})
                walkout._ems_wake_cron_at(walkout.join_until)
                walkout._ems_mail_students('ems.email_template_student_walkout_join')
                walkout._ems_mail_tutors('join')
            else:
                walkout._ems_close()
                walkout._ems_mail_students('ems.email_template_student_walkout_result')

    def _ems_close(self):
        for walkout in self.filtered(lambda walkout: walkout.state in ('voting', 'joining')):
            walkout.write({'state': 'closed', 'closed_datetime': fields.Datetime.now()})
            walkout._ems_render_minute()
            walkout._ems_notify_closed()

    def _ems_render_minute(self):
        self.ensure_one()
        pdf, _report_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.action_report_student_walkout', self.ids)
        self.pdf_attachment_id = self.env['ir.attachment'].sudo().create({
            'name': f"{self.name}.pdf", 'raw': pdf, 'mimetype': 'application/pdf',
            'res_model': self._name, 'res_id': self.id,
        })

    def _ems_notify_closed(self):
        """The minute to the Head of Studies right away (the walkout is a day off: not a notice for
        the daily summary), with a task when there is somebody to justify; the tutor is told. The
        families hear of the result when the Head of Studies decides (action_generate_justification,
        _ems_reject)."""
        self.ensure_one()
        users = self._ems_head_users()
        self._ems_mail_staff('ems.email_template_student_walkout_head', users,
                             attachment_ids=[(4, self.pdf_attachment_id.id)])
        if self._ems_has_something_to_justify():
            self.sudo()._ems_sync_user_tasks(self.env.ref(JUSTIFY_TASK), users, self.walkout_date)
        self._ems_mail_tutors('closed')

    def _ems_family_lines(self, validated):
        """The students whose family hears of the call: the minors it was asked to ratify for and,
        once `validated`, the adults who join and share with their family."""
        self.ensure_one()
        return self.line_ids.filtered(lambda line: line.needs_ratification or (
            validated and line.joins and not self._ems_is_minor(line.student_id) and line.student_id.sudo().auth_share))

    def _ems_mail_families(self, template_xmlid, lines):
        """The family of each student of `lines`, at once (families are not tied to school hours)."""
        template = self.env.ref(template_xmlid).sudo()
        for line in lines:
            emails = line.student_id._ems_family_contacts().filtered('email').mapped('email')
            if emails:
                template.send_mail(line.id, email_values={'email_to': ','.join(emails)})

    def _ems_mail_students(self, template_xmlid, lines=None):
        """Each student's email (`lines`, by default those with portal access), sent during their
        group's school hours: queued until its next class when it is outside them."""
        template = self.env.ref(template_xmlid).sudo()
        moments = {}
        for line in lines if lines is not None else self.line_ids.filtered('has_portal'):
            email = line.student_id.student_email or line.student_id.email
            if not email:
                continue
            group = line.student_id.main_group_id or self.group_id
            if group not in moments:
                moments[group] = group._ems_school_send_time()
            template.send_mail(line.id, email_values={'email_to': email, 'scheduled_date': moments[group]})

    def _ems_head_users(self):
        """Who gets the minute and validates the call: the Head or Deputy Head of Studies above the
        group's tutor; with no tutor, every Head and Deputy Head of Studies; failing that, the academic
        administrators. Noted on the call."""
        self.ensure_one()
        tutor = self.group_id.tutor_id.sudo()
        if tutor:
            head = tutor.find_head_of_studies()
            self.head_of_studies_id = head
            users = head.user_id
        else:
            users = self.env.ref('ems.group_head_of_studies').sudo().users.filtered(lambda user: not user.share)
        return users or self.env.ref('ems.group_academic_admin').sudo().users.filtered(lambda user: not user.share)

    def _ems_tutor_users(self):
        """Who watches over the call: the tutors of its groups (co-tutors of a split group too);
        with no tutor, the Head of Studies who would get the minute."""
        self.ensure_one()
        return self.group_ids.tutor_id.sudo().user_id or self._ems_head_users()

    def _ems_mail_tutors(self, event):
        """The tutors' copy of what the group is told (`event`: call, join, closed, validated,
        rejected), when it reaches the group. An email, not a notice for the daily summary: a phase
        lasts one school day and the tutor must be able to abort the call within it."""
        self.ensure_one()
        moment = self._ems_send_moment(self.group_ids, fields.Datetime.now())
        self.with_context(walkout_event=event)._ems_mail_staff(
            'ems.email_template_student_walkout_tutor', self._ems_tutor_users(), scheduled_date=moment)

    def _ems_mail_staff(self, template_xmlid, users, **email_values):
        """An email to staff, sent at once: the walkout is only a few days off."""
        email_to = ','.join(users.filtered('email').mapped('email_formatted'))
        if email_to:
            self.env.ref(template_xmlid).sudo().send_mail(self.id, email_values={'email_to': email_to, **email_values})

    # Rejecting

    def _ems_user_may_abort(self):
        """The group's tutor or the chain above them (tutor scope: Department or Seminar Chief, Head
        or Deputy Head of Studies, Director), any Head of Studies when the group has no tutor, or an
        administrator."""
        self.ensure_one()
        if self.get_user_is_top_admin():
            return True
        tutors = self.group_ids.tutor_id
        if not tutors:
            return self.env.user.has_group('ems.group_head_of_studies')
        return any(self.user_acts_as_tutor(tutor) for tutor in tutors)

    def _ems_user_may_reject(self):
        """Not validating a closed call, or undoing its validation: whoever validates it."""
        self.ensure_one()
        return (self.state == 'justified' or self._ems_has_something_to_justify()) and self._ems_user_may_justify()

    def _ems_check_reject(self):
        self.ensure_one()
        if self.state in ABORTABLE_STATES:
            if not self._ems_user_may_abort():
                raise UserError(_("Only the tutor of the group, the chain above them (Department or Seminar Chief, Head "
                                  "or Deputy Head of Studies, Director) or an administrator can abort a student "
                                  "walkout call."))
        elif self.state in VALIDATION_STATES:
            if not self._ems_user_may_reject():
                raise UserError(_("Only the Head of Studies, the Deputy Head of Studies or the Director of these "
                                  "students, or an administrator, can decide whether a student walkout is validated."))
        else:
            raise UserError(_("This student walkout call can no longer be aborted nor rejected."))

    def action_open_reject_wizard(self):
        self._ems_check_reject()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Abort the student walkout call") if self.state in ABORTABLE_STATES
            else _("Do not validate the student walkout"),
            'res_model': 'ems.student_walkout.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def _ems_reject(self, reason, details):
        """Aborted (voting, joining) or not validated (closed, justified), always with a reason. The
        students and the tutor are always told, the families that heard of it too (_ems_family_lines),
        and the Head of Studies of an aborted call in their daily summary. A justification already
        generated is removed, as the user rejecting it."""
        self._ems_check_reject()
        details = (details or '').strip()
        if reason.requires_details and not details:
            raise UserError(_("Explain the reason in the details: %(reason)s", reason=reason.name))
        previous = self.state
        if self.justification_id:
            self._ems_justifications('unlink').browse(self.justification_id.id).unlink()
        walkout = self.sudo()
        walkout.write({'state': 'rejected', 'rejected_by_id': self.env.uid, 'rejected_datetime': fields.Datetime.now(),
                       'rejection_reason_id': reason.id, 'rejection_details': details or False,
                       'rejected_from_state': previous})
        walkout._ems_sync_user_tasks(self.env.ref(JUSTIFY_TASK), self.env['res.users'], walkout.walkout_date)
        walkout._ems_mail_students('ems.email_template_student_walkout_rejected')
        walkout._ems_mail_tutors('rejected')
        # The families that heard of it (asked to ratify, or told of the validation) are told too.
        walkout._ems_mail_families('ems.email_template_student_walkout_family_rejected',
                                   walkout._ems_family_lines(previous == 'justified'))
        if previous in ABORTABLE_STATES:
            walkout._ems_notify_aborted()
        walkout._message_log(body=_("Rejected by %(name)s: %(reason)s", name=self.env.user.name, reason=reason.name))

    def _ems_notify_aborted(self):
        """The Head of Studies is told of every aborted call and why, in their daily summary (no
        action asked)."""
        body = Markup("<p>{}</p>")
        for user in self._ems_head_users():
            env = self.with_context(lang=user.lang or self.env.lang).env
            text = body.format(env._(
                "Student walkout: %(name)s has aborted the call of %(group)s for a walkout on %(day)s. Reason: "
                "%(reason)s.", name=self.rejected_by_id.name, group=self.group_id.name,
                day=format_date(env, self.walkout_date),
                reason=self.rejection_reason_id.with_env(env).name + (
                    f" ({self.rejection_details})" if self.rejection_details else '')))
            self.env['ems.info_notice']._ems_queue(user, self, lambda _user, text=text: text)

    # Justifying

    def _ems_justifications(self, operation):
        """The justifications to create or remove the walkout's one with, as the user deciding (whom
        _ems_check_reject / _ems_user_may_justify already allowed). The system administrator, above
        Direction, has no justification rights of their own: for them, as the superuser."""
        justifications = self.env['ems.attendance_justification']
        # with_user, not sudo: the justification's own checks read env.user (get_user_is_admin).
        return justifications if justifications.has_access(operation) else justifications.with_user(SUPERUSER_ID)

    def _ems_has_something_to_justify(self):
        self.ensure_one()
        return self.state == 'closed' and self.group_supports and bool(self.justifiable_student_ids)

    def _ems_user_may_justify(self):
        """A Head of Studies, Deputy Head of Studies or Director above every student who can be
        justified (tutor scope), or an administrator."""
        self.ensure_one()
        if self.get_user_is_top_admin():
            return True
        return self.env.user.has_group('ems.group_head_of_studies') and \
            self.env['ems.attendance_justification']._user_may_justify(self.justifiable_student_ids)

    def action_generate_justification(self):
        """One full-day justification of the walkout day for the students who can be justified
        (adults, and minors whose family ratified it), except the ones already justified that day
        (noted in the chatter)."""
        self.ensure_one()
        if not self._ems_has_something_to_justify():
            raise UserError(_("There is nobody to justify: the vote is not closed, the group did not support the "
                              "walkout, nobody joined it or it is already justified."))
        if not self._ems_user_may_justify():
            raise UserError(_("Only the Head of Studies, the Deputy Head of Studies or the Director of these "
                              "students, or an administrator, can justify a student walkout."))
        Justification = self._ems_justifications('create')
        period = Justification._whole_day_vals(self.walkout_date)
        joining = self.justifiable_student_ids
        skipped = Justification.new({'student_ids': [(6, 0, joining.ids)], **period})._overlapping_students(joining)
        students = joining - skipped
        justification = Justification
        if students:
            teacher = self.env['hr.employee'].search([('user_id', '=', self.env.uid),
                                                      ('employee_type', '=', 'teacher')], limit=1)
            justification = Justification.create({
                'teacher_id': (teacher or self.group_id.tutor_id).id,
                'student_ids': [(6, 0, students.ids)],
                'reason_id': self.env.ref('ems.attendance_justification_reason_walkout').id,
                'notes': self.name,
                **period,
            })
        walkout = self.sudo()
        walkout.write({'state': 'justified', 'justification_id': justification.id})
        walkout._ems_sync_user_tasks(self.env.ref(JUSTIFY_TASK), self.env['res.users'], self.walkout_date, done=True)
        # Validated: every student is told, the family of each one justified and the tutor too.
        walkout._ems_mail_students('ems.email_template_student_walkout_validated')
        walkout._ems_mail_families('ems.email_template_student_walkout_family',
                                   walkout._ems_family_lines(True).filtered('justifiable'))
        walkout._ems_mail_tutors('validated')
        if skipped:
            walkout._message_log(body=_("Not justified again, they already had a justification that day: %(names)s",
                                        names=", ".join(skipped.mapped('name'))))
        if justification and self.env['ems.attendance_justification'].has_access('read'):
            return justification.get_formview_action()
        return False

    def action_open_justification(self):
        self.ensure_one()
        return self.justification_id.get_formview_action()


class EmsStudentWalkoutLine(models.Model):
    """One student of a walkout call. Never the group vote: only whether it was cast."""
    _name = 'ems.student_walkout.line'
    _description = "Student of a student walkout call"
    _order = 'walkout_id, student_id'
    _sql_constraints = [
        ('student_unique', 'UNIQUE(walkout_id, student_id)', 'A student appears only once in a walkout call.'),
    ]

    walkout_id = fields.Many2one(string="Walkout call", comodel_name='ems.student_walkout', required=True,
                                 ondelete='cascade', index=True)
    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True, ondelete='cascade',
                                 index=True)
    has_portal = fields.Boolean(string="Portal access", readonly=True,
                                help="Whether the student had access to the portal when the call was opened: "
                                     "only they vote.")
    voted = fields.Boolean(string="Voted", readonly=True)
    vote_date = fields.Datetime(string="Voted on", readonly=True)
    joins = fields.Boolean(string="Joins", readonly=True)
    join_answered = fields.Boolean(string="Answered whether they join", readonly=True)
    join_date = fields.Datetime(string="Answered on", readonly=True)
    # A minor joining needs their family to ratify it (Decret 102/2010, art. 24.2), on the portal
    # while joining lasts; without it, the student is not justified.
    needs_ratification = fields.Boolean(string="Needs the family's ratification", readonly=True)
    ratification = fields.Selection(string="Family ratification", selection=[
        ('pending', "Pending"),
        ('ratified', "Ratified"),
        ('refused', "Refused"),
    ], readonly=True)
    ratified_by_id = fields.Many2one(string="Answered by", comodel_name='res.partner', readonly=True,
                                     ondelete='set null')
    ratification_date = fields.Datetime(string="Family answered on", readonly=True)
    justifiable = fields.Boolean(string="Can be justified", compute='_compute_justifiable',
                                 help="Joins the walkout and, if a minor, their family ratified it.")

    @api.depends('joins', 'needs_ratification', 'ratification')
    def _compute_justifiable(self):
        for line in self:
            line.justifiable = line.joins and (not line.needs_ratification or line.ratification == 'ratified')


class EmsStudentWalkoutRejectionReason(models.Model):
    """Why a student walkout call is aborted by the tutor or not validated by the Head of Studies: the catalog they pick from, edited in
    Student's Attendances > Configuration. "Other reasons" asks for details."""
    _name = 'ems.student_walkout.rejection_reason'
    _inherit = 'ems.reason.catalog'
    _description = "Student walkout rejection reason"

    requires_details = fields.Boolean(string="Requires details",
                                      help="Whoever rejects the call must explain it in the details (e.g. 'Other').")


class EmsStudentWalkoutRejectWizard(models.TransientModel):
    """Aborts a student walkout call (active_id) or does not validate it, with a reason from the
    catalog. The view explains which reasons are lawful when aborting."""
    _name = 'ems.student_walkout.reject.wizard'
    _description = "Reject a student walkout call"

    walkout_id = fields.Many2one(string="Walkout call", comodel_name='ems.student_walkout', required=True,
                                 default=lambda self: self.env.context.get('active_id'), ondelete='cascade')
    walkout_state = fields.Selection(related='walkout_id.state')
    reason_id = fields.Many2one(string="Reason", comodel_name='ems.student_walkout.rejection_reason', required=True)
    requires_details = fields.Boolean(related='reason_id.requires_details')
    details = fields.Text(string="Details")

    def action_reject(self):
        self.ensure_one()
        self.walkout_id._ems_reject(self.reason_id, self.details)
        return {'type': 'ir.actions.act_window_close'}
