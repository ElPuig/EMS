# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date, format_datetime

GROUP_VOTES = ('yes', 'no', 'abstain')
VALIDATE_TASK = 'ems.mail_activity_student_walkout_validate'
# What the group sees: a call cancelled by its delegate is only theirs.
VISIBLE_STATES = ('voting', 'joining', 'closed', 'validated', 'rejected')
# Issue #838: the least a phase can last when it is cut to keep the notice before the walkout.
MIN_PHASE_MINUTES = 5
# The group's tutor (and the chain above them) may abort a call while it is voted or joined; once
# closed, the Head of Studies validates it or not, and may undo a validation.
ABORTABLE_STATES = ('voting', 'joining')
VALIDATION_STATES = ('closed', 'validated')
# Issue #828: the sample call shown in the settings (_ems_sample_calendar).
SAMPLE_CLASS_FROM = 8.0
SAMPLE_CLASS_TO = 15.0
SAMPLE_PROPOSAL_HOUR = 17.0


def _sample_school_days(date_from, date_to):
    """Every weekday between both dates (included): the sample's school days."""
    return {date_from + timedelta(days=offset) for offset in range((date_to - date_from).days + 1)
            if (date_from + timedelta(days=offset)).weekday() < 5}


class EmsStudentWalkout(models.Model):
    """Issue #800: a student walkout (a strike called by a students' union), opened from the portal
    by a group's delegate or sub-delegate and voted by the group. "Walkout", never "strike":
    ems.strike is the disciplinary record. See docs/en/developers/attendance/student_walkout.md."""
    _name = 'ems.student_walkout'
    _description = "Student walkout proposal"
    _inherit = ['ems.base', 'ems.datetime_utils']
    _order = 'walkout_date desc, id desc'

    name = fields.Char(string="Name", compute='_compute_name', store=True)
    group_id = fields.Many2one(string="Group", comodel_name='ems.group', required=True, readonly=True,
                               ondelete='restrict', index=True)
    # The halves of a split group sharing the delegate vote together.
    group_ids = fields.Many2many(string="Groups", comodel_name='ems.group', relation='ems_student_walkout_group_rel',
                                 column1='walkout_id', column2='group_id', readonly=True)
    opener_id = fields.Many2one(string="Proposed by", comodel_name='res.partner', required=True, readonly=True,
                                ondelete='restrict')
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', readonly=True, ondelete='restrict')
    company_id = fields.Many2one(string="Company", comodel_name='res.company', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    walkout_date = fields.Date(string="Walkout day", required=True, readonly=True)
    # The calendar (_ems_plan): each phase lasts phase_hours and the Head of Studies gets the minute at
    # least notice_hours before walkout_start, counted as the settings say (issue #828): real hours or
    # the group's class hours, from the proposal or from when the email reaches the group, with or
    # without the days the group has no class. All kept from the settings the proposal was made with;
    # the defaults are the count of the calls opened before issue #828.
    walkout_start = fields.Datetime(string="Walkout starts", compute='_compute_walkout_start')
    phase_hours = fields.Integer(string="Phase (hours)", readonly=True)
    notice_hours = fields.Integer(string="Notice (hours)", readonly=True)
    hours_kind = fields.Selection(string="Kind of hours", selection=[
        ('real', "Real hours"),
        ('school', "School hours"),
    ], default='real', required=True, readonly=True)
    count_from = fields.Selection(string="Count starts", selection=[
        ('proposal', "From the moment of the proposal"),
        ('email', "When the group receives the email within its schedule"),
    ], default='email', required=True, readonly=True)
    count_days_off = fields.Boolean(string="Counts the days without class", readonly=True)
    vote_start = fields.Datetime(string="Group vote from", readonly=True, copy=False)
    vote_until = fields.Datetime(string="Group vote until", readonly=True, copy=False)
    join_start = fields.Datetime(string="Joining from", readonly=True, copy=False)
    join_until = fields.Datetime(string="Joining until", readonly=True, copy=False)
    notes = fields.Text(string="Reason", readonly=True)
    attachment_ids = fields.Many2many(string="Union's call", comodel_name='ir.attachment',
                                      relation='ems_student_walkout_attachment_rel', column1='walkout_id',
                                      column2='attachment_id', readonly=True)
    state = fields.Selection(string="State", selection=[
        ('voting', "Voting"),
        ('joining', "Joining"),
        ('closed', "Closed"),
        ('validated', "Validated"),
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
    # undone (validated). It decides what the group and the families are told.
    rejected_from_state = fields.Selection(string="Rejected while", selection=[
        ('voting', "Voting"),
        ('joining', "Joining"),
        ('closed', "Closed"),
        ('validated', "Validated"),
    ], readonly=True, copy=False)
    # Issue #838: the delegates extend the joining once; the tutor chain, any number of times.
    delegate_extended = fields.Boolean(string="Extended by the delegates", readonly=True, copy=False)
    can_extend = fields.Boolean(compute='_compute_can_reject')
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
    joining_count = fields.Integer(string="Join", compute='_compute_line_counts')
    voter_count = fields.Integer(string="May vote", compute='_compute_line_counts')
    voted_count = fields.Integer(string="Voted", compute='_compute_line_counts')
    join_answered_count = fields.Integer(string="Answered whether they join", compute='_compute_line_counts')
    closed_datetime = fields.Datetime(string="Closed on", readonly=True, copy=False)
    head_of_studies_id = fields.Many2one(string="Head of Studies", comodel_name='hr.employee', readonly=True,
                                         copy=False, ondelete='set null')
    pdf_attachment_id = fields.Many2one(string="Minute", comodel_name='ir.attachment', readonly=True, copy=False,
                                        ondelete='set null')
    can_validate = fields.Boolean(compute='_compute_can_validate')

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

    @api.depends('line_ids.joins', 'line_ids.voted', 'line_ids.has_portal', 'line_ids.join_answered')
    def _compute_line_counts(self):
        for walkout in self:
            joining = walkout.line_ids.filtered('joins')
            walkout.joining_student_ids = joining.student_id
            walkout.joining_count = len(joining)
            walkout.voter_count = len(walkout.line_ids.filtered('has_portal'))
            walkout.voted_count = len(walkout.line_ids.filtered('voted'))
            walkout.join_answered_count = len(walkout.line_ids.filtered('join_answered'))

    @api.depends('state', 'join_until')
    @api.depends_context('uid')
    def _compute_can_reject(self):
        for walkout in self:
            walkout.can_extend = walkout._ems_user_may_abort() and bool(walkout._ems_extension())
            walkout.can_abort = walkout.state in ABORTABLE_STATES and walkout._ems_user_may_abort()
            walkout.can_reject = walkout.state in VALIDATION_STATES and walkout._ems_user_may_reject()

    @api.depends('state', 'line_ids.joins', 'group_yes_count', 'group_no_count')
    @api.depends_context('uid')
    def _compute_can_validate(self):
        for walkout in self:
            walkout.can_validate = walkout._ems_has_something_to_validate() and walkout._ems_user_may_validate()

    # Portal: the controller passes the logged-in student; everything is checked here.

    @api.model
    def _ems_portal_open(self, partner, values, files):
        """Makes a walkout proposal for `partner`'s group: `values` has walkout_date and notes, `files` the
        union's call as (name, content) pairs. The group votes at once, with no review first."""
        partner = partner.sudo()
        group = partner._ems_walkout_opener_group()
        if not group:
            raise UserError(_("Only the delegate or the sub-delegate of a group that may propose supporting a student walkout "
                              "can propose it."))
        groups = partner._ems_walkout_opener_groups()
        walkout_date = fields.Date.to_date(values.get('walkout_date'))
        calendar = self._ems_projected_calendar(groups)
        self._ems_check_request_date(walkout_date, calendar)
        notes = (values.get('notes') or '').strip()
        if not notes:
            raise UserError(_("Give the reason of the walkout: why it is called."))
        files = [(name, content) for name, content in files or [] if name and content]
        if not files:
            raise UserError(_("Attach the call of the students' union."))
        if self.search_count([('group_ids', 'in', groups.ids), ('walkout_date', '=', walkout_date),
                              ('state', 'not in', ('cancelled', 'rejected'))]):
            raise UserError(_("Your group already has a student walkout proposal for %(date)s.",
                              date=format_date(self.env, walkout_date)))
        students = self.env['res.partner'].search([('contact_type', '=', 'student'),
                                                   ('main_group_id', 'in', groups.ids)])
        with_portal = set(self._ems_with_portal(students).ids)
        walkout = self.create({
            'group_id': group.id,
            'group_ids': [(6, 0, groups.ids)],
            'opener_id': partner.id,
            'course_id': self.env.company.current_course_id.id,
            'walkout_date': walkout_date,
            'phase_hours': calendar['phase_hours'],
            'notice_hours': calendar['notice_hours'],
            **calendar['plan']['rule'],
            'vote_start': calendar['vote_start'],
            'vote_until': calendar['vote_until'],
            'notes': notes[:2000],
            'line_ids': [(0, 0, {'student_id': student.id, 'has_portal': student.id in with_portal})
                         for student in students],
        })
        walkout.attachment_ids = self.env['ir.attachment'].create([{
            'name': name, 'raw': content, 'res_model': self._name, 'res_id': walkout.id,
        } for name, content in files])
        walkout._message_log(body=_("Proposed by %(name)s from the portal.", name=partner.name))
        walkout._ems_start_voting()
        return walkout

    @api.model
    def _ems_with_portal(self, students):
        """The students of `students` with access to the portal now (an active portal user)."""
        return self.env['res.users'].sudo().search([('partner_id', 'in', students.ids), ('share', '=', True)]).partner_id

    def _ems_portal_line(self, partner, voting=False):
        """`partner`'s line, to answer on the portal. The group vote is only for the students with
        portal access when the proposal was made (has_portal): its majority is counted over them.
        Joining is each student's own decision, so any student of the call answers, also one who got
        access afterwards (issue #830): answering on the portal already means having it."""
        line = self.line_ids.filtered(lambda line: line.student_id == partner and (line.has_portal or not voting))
        if not line:
            raise UserError(_("Only the students of the group with access to the portal can answer."))
        return line

    def _ems_joining_lines(self):
        """The lines told that joining is open: every student of the call with portal access now."""
        self.ensure_one()
        with_portal = self._ems_with_portal(self.line_ids.student_id)
        return self.line_ids.filtered(lambda line: line.student_id in with_portal)

    @api.model
    def _ems_portal_access_granted(self, partners):
        """Issue #830: a student who gets portal access while their call's joining is open and has
        not answered yet gets the joining email, so they know they can still say whether they join."""
        now = fields.Datetime.now()
        lines = self.env['ems.student_walkout.line'].sudo().search([
            ('student_id', 'in', partners.ids), ('join_answered', '=', False), ('walkout_id.state', '=', 'joining'),
            ('walkout_id.join_until', '>', now)])
        for walkout, walkout_lines in lines.grouped('walkout_id').items():
            walkout._ems_mail_students('ems.email_template_student_walkout_join', walkout_lines)

    def _ems_portal_vote(self, partner, group_vote):
        """`partner` votes whether the group supports the walkout: once, never linked to them. The
        vote ends as soon as its result is decided (_ems_vote_decided)."""
        self.ensure_one()
        line = self._ems_portal_line(partner, voting=True)
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
        """`partner` says whether they join the walkout, by name; changeable until joining ends. The
        family of a minor joining is asked at once to ratify it (Decret 102/2010, art. 24.2), only to
        know whether it knows and agrees (issue #844); withdrawing clears it, joining again asks again."""
        self.ensure_one()
        line = self._ems_portal_line(partner)
        if not self._ems_phase_open('joining'):
            raise UserError(_("Joining this student walkout is closed."))
        vals = {'joins': bool(joins), 'join_answered': True, 'join_date': fields.Datetime.now()}
        asks = bool(joins) and not line.joins and self._ems_is_minor(line.student_id)
        if not joins:
            vals.update({'needs_ratification': False, 'ratification': False, 'ratified_by_id': False,
                         'ratification_date': False, 'ratified_manually': False})
        elif asks:
            vals.update({'needs_ratification': True, 'ratification': 'pending', 'ratified_by_id': False,
                         'ratification_date': False, 'ratified_manually': False})
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
        can change its answer meanwhile. Only a family contact of the student with portal access. It
        only says the family knows and agrees (issue #844): nobody can revoke the student's decision. A
        refusal is told to the student, for information."""
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
                    'ratification_date': fields.Datetime.now(), 'ratified_manually': False})
        if refused_now:
            self._ems_mail_students('ems.email_template_student_walkout_ratification_refused', line)

    def _ems_portal_cancel(self, partner):
        self._ems_check_manager(partner)
        if self.state not in ('voting', 'joining'):
            raise UserError(_("Only a proposal still being voted or joined can be cancelled."))
        self.state = 'cancelled'
        self._message_log(body=_("Cancelled by %(name)s from the portal.", name=partner.name))

    def _ems_portal_extend(self, partner):
        """The delegates extend the joining once."""
        self._ems_check_manager(partner)
        if self.delegate_extended:
            raise UserError(_("The delegates can extend the joining only once."))
        self._ems_extend_joining(partner.name, as_delegate=True)

    def action_extend_joining(self):
        """The tutor chain (and the administrators) extend the joining any time, as often as needed."""
        if not self._ems_user_may_abort():
            raise UserError(_("Only the tutor of the group, the chain above them (Department or Seminar Chief, Head "
                              "or Deputy Head of Studies, Director) or an administrator can extend the joining."))
        self._ems_extend_joining(self.env.user.name)

    def _ems_is_manager(self, partner):
        """The opener, or the group's current delegate or sub-delegate, manage the proposal."""
        self.ensure_one()
        return partner == self.opener_id or partner in (self.group_ids.delegate_id | self.group_ids.subdelegate_id)

    def _ems_check_manager(self, partner):
        if not self._ems_is_manager(partner):
            raise UserError(_("Only the delegate or the sub-delegate of the group can manage this proposal."))

    # The calendar

    def _ems_day_start(self, day):
        """00:00 of `day` in the centre, naive UTC: the walkout starts then."""
        return day and self.datetime_to_odoo(self.time_float_to_utc_datetime(day, 0.0))

    # How the hours are counted (issue #828): a plan, built once per calendar, holds the rule
    # (hours_kind, count_from, count_days_off), each group's class windows (when its email reaches it)
    # and their union (the class hours counted with school hours). `school_days` is only given by the
    # sample of the settings (_ems_sample_calendar); otherwise the centre's calendar is read.

    @api.model
    def _ems_company_rule(self):
        company = self.env.company
        return {'hours_kind': company.walkout_hours_kind, 'count_from': company.walkout_count_from,
                'count_days_off': company.walkout_count_days_off}

    def _ems_rule(self):
        self.ensure_one()
        return {'hours_kind': self.hours_kind, 'count_from': self.count_from, 'count_days_off': self.count_days_off}

    def _ems_own_plan(self):
        self.ensure_one()
        return self._ems_plan(self.group_ids, self._ems_rule())

    @api.model
    def _ems_plan(self, groups, rule, group_windows=None, school_days=None):
        group_windows = group_windows if group_windows is not None else \
            [group._ems_class_windows() for group in groups]
        union = {}
        for windows in group_windows:
            for day, (hour_from, hour_to) in windows.items():
                start, end = union.get(day, (24.0, 0.0))
                union[day] = (min(start, hour_from), max(end, hour_to))
        return {'rule': rule, 'group_windows': group_windows, 'windows': union, 'school_days': school_days}

    @api.model
    def _ems_counted_windows(self, plan):
        """The class windows the count is limited to: only with school hours. A group with no
        schedule counts every hour of its school days."""
        return plan['windows'] if plan['rule']['hours_kind'] == 'school' else None

    @api.model
    def _ems_counts_every_day(self, plan):
        return plan['rule']['hours_kind'] == 'real' and plan['rule']['count_days_off']

    @api.model
    def _ems_add_hours(self, plan, moment, hours):
        if self._ems_counts_every_day(plan):
            return moment + timedelta(hours=hours)
        return self.ems_add_school_hours(moment, hours, self._ems_counted_windows(plan), plan['school_days'])

    @api.model
    def _ems_hours_between(self, plan, start, end):
        if self._ems_counts_every_day(plan):
            return max(0.0, (end - start).total_seconds() / 3600)
        return self.ems_school_hours_between(start, end, self._ems_counted_windows(plan), plan['school_days'])

    @api.model
    def _ems_sends_at_once(self, rule):
        """Real hours counted from the proposal: the emails leave at once, whatever the time, instead
        of waiting for the group's classes."""
        return rule['hours_kind'] == 'real' and rule['count_from'] == 'proposal'

    @api.model
    def _ems_send_moment(self, plan, moment):
        """When an email sent at `moment` reaches the students: then when the rule sends at once,
        otherwise during their classes or at the next ones (the latest group's)."""
        if self._ems_sends_at_once(plan['rule']):
            return moment
        return max([self.ems_class_send_moment(moment, windows, plan['school_days'])
                    for windows in plan['group_windows']] or [moment])

    @api.model
    def _ems_phase(self, plan, moment, hours):
        """A phase whose email is sent at `moment`: from when it reaches the students (or at once, see
        _ems_sends_at_once), `hours` long."""
        start = self._ems_send_moment(plan, moment)
        return start, self._ems_add_hours(plan, start, hours)

    @api.model
    def _ems_projected_calendar(self, groups, now=None, plan=None, phase=None, notice=None):
        """The calendar of a call opened `now` for `groups` with the settings (or `plan`, `phase` and
        `notice`, for the sample of the settings), the group vote taking its whole phase: the latest
        the minute can reach the Head of Studies (join_until)."""
        company = self.env.company
        plan = plan or self._ems_plan(groups, self._ems_company_rule())
        phase = company.walkout_phase_hours if phase is None else phase
        notice = company.walkout_notice_hours if notice is None else notice
        vote_start, vote_until = self._ems_phase(plan, now or fields.Datetime.now(), phase)
        join_start, join_until = self._ems_phase(plan, vote_until, phase)
        return {
            'phase_hours': phase, 'notice_hours': notice, 'plan': plan,
            'vote_start': vote_start, 'vote_until': vote_until,
            'join_start': join_start, 'join_until': join_until,
        }

    @api.model
    def _ems_notice_kept(self, calendar, day):
        """Whether a walkout on `day` keeps the notice: the minute at least notice_hours, counted as
        the phases, before its 00:00."""
        return self._ems_hours_between(calendar['plan'], calendar['join_until'], self._ems_day_start(day)) >= \
            calendar['notice_hours']

    @api.model
    def _ems_longest_end(self, plan, start, hours, day, notice_hours):
        """Issue #838: the end of a phase that starts at `start` and lasts `hours`, or, when the minute would
        then not reach the Head of Studies `notice_hours` before `day`, the longest part of it that does
        (bisection over minutes). False when not even MIN_PHASE_MINUTES keep the notice."""
        day_start = self._ems_day_start(day)

        def end(minutes):
            return self._ems_add_hours(plan, start, minutes / 60)

        def kept(minutes):
            return self._ems_hours_between(plan, end(minutes), day_start) >= notice_hours

        longest = int(hours * 60)
        if kept(longest):
            return end(longest)
        if not kept(MIN_PHASE_MINUTES):
            return False
        low, high = MIN_PHASE_MINUTES, longest
        while high - low > 1:
            middle = (low + high) // 2
            low, high = (middle, high) if kept(middle) else (low, middle)
        return end(low)

    @api.model
    def _ems_join_until_for(self, calendar, day):
        """When the joining of a call for `day` ends at the latest: its whole phase, or shorter when the
        notice needs it (False when not even a few minutes fit)."""
        return self._ems_longest_end(calendar['plan'], calendar['join_start'], calendar['phase_hours'], day,
                                     calendar['notice_hours'])

    @api.model
    def _ems_first_walkout_day(self, calendar, shortened=False):
        """The first school day a call with this calendar can be for, with both phases whole or, with
        `shortened`, with the joining cut to what the notice allows."""
        first = self.utc_to_local_date(calendar['join_start' if shortened else 'join_until'])
        school_days_of = calendar['plan']['school_days'] or self._ems_school_days
        school_days = sorted(school_days_of(first, fields.Date.add(first, days=366)))
        fits = (lambda day: self._ems_join_until_for(calendar, day)) if shortened else \
            (lambda day: self._ems_notice_kept(calendar, day))
        return next((day for day in school_days if fits(day)), False)

    @api.model
    def _ems_sample_calendar(self, rule, phase, notice, now=None):
        """The calendar of a sample call for the settings: a group with class from SAMPLE_CLASS_FROM to
        SAMPLE_CLASS_TO, Monday to Friday, every weekday a school day, proposing on the next Friday
        (`now`, by default) at SAMPLE_PROPOSAL_HOUR, after its classes. The same functions as a real
        call, only the timetable and the school days are the sample's."""
        if now is None:
            today = self.get_local_today()
            friday = today + timedelta(days=(4 - today.weekday()) % 7)
            now = self.datetime_to_odoo(self.time_float_to_utc_datetime(friday, SAMPLE_PROPOSAL_HOUR))
        plan = self._ems_plan(self.env['ems.group'], rule,
                              group_windows=[{day: (SAMPLE_CLASS_FROM, SAMPLE_CLASS_TO) for day in range(5)}],
                              school_days=_sample_school_days)
        calendar = self._ems_projected_calendar(self.env['ems.group'], now, plan, phase, notice)
        calendar['proposal'] = now
        calendar['first_day'] = self._ems_first_walkout_day(calendar)
        calendar['earliest_day'] = self._ems_first_walkout_day(calendar, shortened=True)
        return calendar

    @api.model
    def _ems_sample_html(self, rule, phase, notice, now=None):
        """The sample call of the settings, as text (see _ems_sample_calendar)."""
        if not phase or phase < 1 or notice is None or notice < 0:
            return ''
        calendar = self._ems_sample_calendar(rule, phase, notice, now)
        tz = self.company_tz_name()

        def moment(value):
            return format_datetime(self.env, value, tz=tz, dt_format='EEEE d/M, HH:mm')

        lines = [
            _("The group vote ends: %(moment)s", moment=moment(calendar['vote_until'])),
            _("The joining ends, and the minute reaches the Head of Studies at the latest: %(moment)s",
              moment=moment(calendar['join_until'])),
            _("First possible walkout day: %(day)s",
              day=format_date(self.env, calendar['first_day'], date_format='EEEE d/M')),
        ]
        if calendar['earliest_day'] != calendar['first_day']:
            lines.append(_("Earliest walkout day, with a shorter joining: %(day)s",
                           day=format_date(self.env, calendar['earliest_day'], date_format='EEEE d/M')))
        intro = _("Example: a group with class from 8:00 to 15:00, Monday to Friday, proposes a walkout on "
                  "%(moment)s, after its classes.", moment=moment(calendar['proposal']))
        return Markup('<p class="mb-1">%s</p><ul class="mb-1">%s</ul><p class="mb-0">%s</p>') % (
            intro, Markup('').join(Markup('<li>%s</li>') % line for line in lines),
            self._ems_count_description(rule))

    @api.model
    def _ems_count_description(self, rule):
        """What the rule means, in two sentences: shown on the portal, the settings and the error."""
        if rule['hours_kind'] == 'school':
            return _("Only the group's class hours count, according to its timetable: the days without class "
                     "(weekends, public holidays and school breaks) have none. The count starts at the group's first "
                     "class after the proposal.")
        if rule['count_days_off']:
            hours = _("Real hours count, every day, also the days the group has no class.")
        else:
            hours = _("Real hours count, except on the days the group has no class (weekends, public holidays and "
                      "school breaks), which count nothing.")
        if rule['count_from'] == 'proposal':
            start = _("The count starts at the moment of the proposal, and the emails leave at once.")
        else:
            start = _("Each phase starts when its email reaches the group: during its classes, or at the start of "
                      "the next ones.")
        return f"{hours} {start}"

    @api.model
    def _ems_check_request_date(self, walkout_date, calendar):
        """The group vote takes a whole phase, the joining the rest of what the notice leaves (at least
        MIN_PHASE_MINUTES) and the minute must reach the Head of Studies the notice before the walkout, all
        counted as the settings say."""
        if not walkout_date:
            raise UserError(_("Give the walkout day."))
        if not self._ems_school_days(walkout_date, walkout_date):
            raise UserError(_("A student walkout can only be on a school day."))
        if not self._ems_join_until_for(calendar, walkout_date):
            raise UserError(_(
                "It is too late to propose supporting a student walkout for %(day)s: the group vote takes %(phase)s "
                "hours, the joining can be shortened but needs at least %(minutes)s minutes, and the Head of Studies "
                "must get the minute %(notice)s hours before the walkout. %(count)s A proposal made now can be for "
                "%(first)s at the earliest.",
                day=format_date(self.env, walkout_date), phase=calendar['phase_hours'], minutes=MIN_PHASE_MINUTES,
                notice=calendar['notice_hours'], count=self._ems_count_description(calendar['plan']['rule']),
                first=format_date(self.env, self._ems_first_walkout_day(calendar, shortened=True))))

    def _ems_worst_join_hours(self):
        """Issue #838: when a proposal still being voted could not give the joining its whole phase even if
        the vote takes all of its own, the hours the joining would last then (a shorter vote lengthens it, up
        to the phase); False when the whole phase fits."""
        self.ensure_one()
        plan = self._ems_own_plan()
        start = self._ems_send_moment(plan, self.vote_until)
        until = self._ems_longest_end(plan, start, self.phase_hours, self.walkout_date, self.notice_hours) or \
            self._ems_add_hours(plan, start, MIN_PHASE_MINUTES / 60)
        hours = self._ems_hours_between(plan, start, until)
        return round(hours, 1) if hours < self.phase_hours else False

    def _ems_phase_open(self, state):
        """Whether the phase `state` (voting, joining) is open: the proposal is in it and its end has not
        come. Students may answer before its start too (e.g. on the weekend before)."""
        self.ensure_one()
        until = self.vote_until if state == 'voting' else self.join_until
        return self.state == state and bool(until) and fields.Datetime.now() < until

    def _ems_extension(self):
        """Issue #838: what the joining can be extended to, or False when it cannot: only a proposal the
        group supports, still joining or already closed (its minute goes out again when it closes), and
        the minute must still reach the Head of Studies the notice before the walkout. An extension is
        one phase long, or, when that would break the notice, as long as it allows (_ems_longest_end)."""
        self.ensure_one()
        if not (self.state == 'joining' or (self.state == 'closed' and self.group_supports)):
            return False
        plan = self._ems_own_plan()
        start = max(self.join_until, self._ems_send_moment(plan, fields.Datetime.now()))
        return self._ems_longest_end(plan, start, self.phase_hours, self.walkout_date, self.notice_hours)

    def _ems_extend_joining(self, by_name, as_delegate=False):
        """Joining lasts one phase more. A closed proposal reopens: its minute and its task are withdrawn
        (the Head of Studies is told in their daily summary) and both are made again when it closes."""
        self.ensure_one()
        until = self._ems_extension()
        if not until:
            raise UserError(_(
                "The joining cannot be extended: it has to be a proposal the group supports, and the Head of Studies "
                "must get the minute at least %(notice)s hours before the walkout of %(day)s.",
                notice=self.notice_hours, day=format_date(self.env, self.walkout_date)))
        walkout = self.sudo()
        was_closed = walkout.state == 'closed'
        values = {'state': 'joining', 'join_until': until, 'delegate_extended': walkout.delegate_extended or as_delegate}
        if was_closed:
            walkout.pdf_attachment_id.unlink()
            values['closed_datetime'] = False
            walkout._ems_sync_user_tasks(self.env.ref(VALIDATE_TASK), self.env['res.users'], walkout.walkout_date)
        walkout.write(values)
        walkout._ems_wake_cron_at(until)
        walkout._ems_mail_students('ems.email_template_student_walkout_join_extended', walkout._ems_joining_lines())
        walkout._ems_mail_tutors('extended')
        if was_closed:
            walkout._ems_notify_heads(lambda env: env._(
                "Student walkout: %(name)s has extended the joining of %(group)s for the walkout on %(day)s, so the "
                "minute is held back until it closes again.", name=by_name, group=walkout.group_id.name,
                day=format_date(env, walkout.walkout_date)))
        walkout._message_log(body=_("Joining extended by %(name)s until %(until)s.", name=by_name,
                                    until=walkout.format_local_datetime(until)))

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
        group's tutor, who may abort the proposal."""
        self.ensure_one()
        self._ems_mail_students('ems.email_template_student_walkout_call')
        self._ems_mail_tutors('call')
        self._ems_wake_cron_at(self.vote_until)

    @api.model
    def _cron_ems_walkout_deadlines(self):
        """At each phase's end (woken up then, hourly as a safety net): the group vote ends; the
        joining ends and the proposal closes."""
        now = fields.Datetime.now()
        self.search([('state', '=', 'voting'), ('vote_until', '<=', now)])._ems_end_group_vote()
        self.search([('state', '=', 'joining'), ('join_until', '<=', now)])._ems_close()

    def _ems_end_group_vote(self):
        """The group vote ends: if the group supports the walkout, each student is told the result and
        has a phase to say whether they join (from when the email reaches them); otherwise the proposal
        closes (nobody joins it)."""
        for walkout in self.filtered(lambda walkout: walkout.state == 'voting'):
            if walkout.group_supports:
                # The joining lasts a whole phase, or less when the notice needs it: a vote that ended early
                # leaves it more time (issue #838). Late by the cron, at least the shortest it can be.
                plan = walkout._ems_own_plan()
                join_start = walkout._ems_send_moment(plan, fields.Datetime.now())
                join_until = walkout._ems_longest_end(plan, join_start, walkout.phase_hours, walkout.walkout_date,
                                                      walkout.notice_hours) or \
                    walkout._ems_add_hours(plan, join_start, MIN_PHASE_MINUTES / 60)
                walkout.write({'state': 'joining', 'join_start': join_start, 'join_until': join_until})
                walkout._ems_wake_cron_at(walkout.join_until)
                walkout._ems_mail_students('ems.email_template_student_walkout_join', walkout._ems_joining_lines())
                walkout._ems_mail_tutors('join')
            else:
                walkout._ems_close()
                walkout._ems_mail_students('ems.email_template_student_walkout_result')

    def _ems_close(self):
        for walkout in self.filtered(lambda walkout: walkout.state in ('voting', 'joining')):
            walkout.write({'state': 'closed', 'closed_datetime': fields.Datetime.now()})
            walkout._ems_render_minute()
            walkout._ems_notify_closed()
            walkout._ems_apply_walkout_lines()

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
        the daily summary), with a task when somebody joins it; the tutor is told. The families hear
        of the result when the Head of Studies decides (action_validate, _ems_reject)."""
        self.ensure_one()
        users = self._ems_head_users()
        self._ems_mail_staff('ems.email_template_student_walkout_head', users,
                             attachment_ids=[(4, self.pdf_attachment_id.id)])
        if self._ems_has_something_to_validate():
            self.sudo()._ems_sync_user_tasks(self.env.ref(VALIDATE_TASK), users, self.walkout_date)
        self._ems_mail_tutors('closed')

    def _ems_family_lines(self, validated):
        """The students whose family hears of the proposal: the minors who join (it was asked to ratify
        it, whatever it answered) and, once `validated`, the adults who join and share with their family."""
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
        group's school hours: queued until its next class when it is outside them, unless the hours
        are counted from the proposal (_ems_sends_at_once)."""
        template = self.env.ref(template_xmlid).sudo()
        at_once = self._ems_sends_at_once(self._ems_rule())
        moments = {}
        for line in lines if lines is not None else self.line_ids.filtered('has_portal'):
            email = line.student_id.student_email or line.student_id.email
            if not email:
                continue
            group = line.student_id.main_group_id or self.group_id
            if group not in moments:
                moments[group] = not at_once and group._ems_school_send_time()
            template.send_mail(line.id, email_values={'email_to': email, 'scheduled_date': moments[group]})

    def _ems_head_users(self):
        """Who gets the minute and validates the proposal: the Head or Deputy Head of Studies above the
        group's tutor; with no tutor, every Head and Deputy Head of Studies; failing that, the academic
        administrators. Noted on the proposal."""
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
        """Who watches over the proposal: the tutors of its groups (co-tutors of a split group too);
        with no tutor, the Head of Studies who would get the minute."""
        self.ensure_one()
        return self.group_ids.tutor_id.sudo().user_id or self._ems_head_users()

    def _ems_mail_tutors(self, event):
        """The tutors' copy of what the group is told (`event`: call, join, closed, validated,
        rejected), when it reaches the group. An email, not a notice for the daily summary: a phase
        lasts one school day and the tutor must be able to abort the proposal within it."""
        self.ensure_one()
        plan = self._ems_own_plan()
        moment = not self._ems_sends_at_once(plan['rule']) and self._ems_send_moment(plan, fields.Datetime.now())
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
        return (self.state == 'validated' or self._ems_has_something_to_validate()) and self._ems_user_may_validate()

    def _ems_check_reject(self):
        self.ensure_one()
        if self.state in ABORTABLE_STATES:
            if not self._ems_user_may_abort():
                raise UserError(_("Only the tutor of the group, the chain above them (Department or Seminar Chief, Head "
                                  "or Deputy Head of Studies, Director) or an administrator can abort a student "
                                  "walkout proposal."))
        elif self.state in VALIDATION_STATES:
            if not self._ems_user_may_reject():
                raise UserError(_("Only the Head of Studies, the Deputy Head of Studies or the Director of these "
                                  "students, or an administrator, can decide whether a student walkout is validated."))
        else:
            raise UserError(_("This student walkout proposal can no longer be aborted nor rejected."))

    def action_open_reject_wizard(self):
        self._ems_check_reject()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Abort the student walkout proposal") if self.state in ABORTABLE_STATES
            else _("Do not validate the student walkout"),
            'res_model': 'ems.student_walkout.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def _ems_reject(self, reason, details):
        """Aborted (voting, joining) or not validated (closed, validated), always with a reason. The
        students and the tutor are always told, the families that heard of it too (_ems_family_lines),
        and the Head of Studies of an aborted call in their daily summary. Not validated, the classes
        of the walkout day are regular absences again."""
        self._ems_check_reject()
        details = (details or '').strip()
        if reason.requires_details and not details:
            raise UserError(_("Explain the reason in the details: %(reason)s", reason=reason.name))
        previous = self.state
        walkout = self.sudo()
        walkout.write({'state': 'rejected', 'rejected_by_id': self.env.uid, 'rejected_datetime': fields.Datetime.now(),
                       'rejection_reason_id': reason.id, 'rejection_details': details or False,
                       'rejected_from_state': previous})
        walkout._ems_sync_user_tasks(self.env.ref(VALIDATE_TASK), self.env['res.users'], walkout.walkout_date)
        walkout._ems_restore_walkout_lines()
        walkout._ems_mail_students('ems.email_template_student_walkout_rejected')
        walkout._ems_mail_tutors('rejected')
        # The families that heard of it (asked to ratify, or told of the validation) are told too.
        walkout._ems_mail_families('ems.email_template_student_walkout_family_rejected',
                                   walkout._ems_family_lines(previous == 'validated'))
        if previous in ABORTABLE_STATES:
            walkout._ems_notify_aborted()
        walkout._message_log(body=_("Rejected by %(name)s: %(reason)s", name=self.env.user.name, reason=reason.name))

    def _ems_notify_aborted(self):
        """The Head of Studies is told of every aborted call and why, in their daily summary (no
        action asked)."""
        self._ems_notify_heads(lambda env: env._(
            "Student walkout: %(name)s has aborted the proposal of %(group)s for a walkout on %(day)s. Reason: "
            "%(reason)s.", name=self.rejected_by_id.name, group=self.group_id.name,
            day=format_date(env, self.walkout_date),
            reason=self.rejection_reason_id.with_env(env).name + (
                f" ({self.rejection_details})" if self.rejection_details else '')))

    def _ems_notify_heads(self, text):
        """A notice in the daily summary of whoever gets the minute, in their language: `text(env)`."""
        body = Markup("<p>{}</p>")
        for user in self._ems_head_users():
            body_text = body.format(text(self.with_context(lang=user.lang or self.env.lang).env))
            self.env['ems.info_notice']._ems_queue(user, self, lambda _user, text=body_text: text)

    # Validating

    def _ems_has_something_to_validate(self):
        self.ensure_one()
        return self.state == 'closed' and self.group_supports and bool(self.joining_student_ids)

    def _ems_user_may_validate(self):
        """A Head of Studies, Deputy Head of Studies or Director above every student who joins (tutor
        scope, the same rule as justifying them), or an administrator."""
        self.ensure_one()
        if self.get_user_is_top_admin():
            return True
        return self.env.user.has_group('ems.group_head_of_studies') and \
            self.env['ems.attendance_justification']._user_may_justify(self.joining_student_ids)

    def action_validate(self):
        """Issue #844: the walkout is confirmed. Nothing is justified: every student who joins is
        already off the roll-calls of the day (_ems_apply_walkout_lines)."""
        self.ensure_one()
        if not self._ems_has_something_to_validate():
            raise UserError(_("There is nothing to validate: the vote is not closed, the group did not support the "
                              "walkout, nobody joined it or it is already validated."))
        if not self._ems_user_may_validate():
            raise UserError(_("Only the Head of Studies, the Deputy Head of Studies or the Director of these "
                              "students, or an administrator, can validate a student walkout."))
        walkout = self.sudo()
        walkout.state = 'validated'
        walkout._ems_sync_user_tasks(self.env.ref(VALIDATE_TASK), self.env['res.users'], self.walkout_date, done=True)
        # Validated: every student is told, the family of each one who joins and the tutor too.
        walkout._ems_mail_students('ems.email_template_student_walkout_validated')
        walkout._ems_mail_families('ems.email_template_student_walkout_family', walkout._ems_family_lines(True))
        walkout._ems_mail_tutors('validated')
        return True

    # The roll-calls of the walkout day (issue #844)

    def _ems_walkout_session_lines(self, students, domain):
        """The session lines of the walkout day of `students`, of every session (taken off or not).
        One search for the whole call."""
        self.ensure_one()
        return self.env['ems.attendance_session_line'].sudo().with_context(active_test=False).search([
            ('student_id', 'in', students.ids), ('attendance_session_id.date', '=', self.walkout_date),
        ] + domain)

    def _ems_apply_walkout_lines(self):
        """Every student who joins is off the roll-calls of the walkout day, from when joining closes
        with the group's support: "not required to attend: student walkout" (the roll-calls taken
        later start so, res.partner._ems_not_expected_reasons). Neither an absence nor a presence. A
        line with strikes stays: the student was in class. A student who no longer joins (a joining
        extended after it had closed) is back on them."""
        self.ensure_one()
        if not (self.group_supports and self.state in ('closed', 'validated')):
            return
        joining = self.joining_student_ids
        lines = self._ems_walkout_session_lines(joining, [('active', '=', True), ('strike_ids', '=', False)])
        back = self._ems_walkout_session_lines(self.line_ids.student_id - joining,
                                               [('not_expected_reason', '=', 'walkout')])
        # One at a time: a session line's write() works out its notifications for one line.
        for line in lines:
            line.write({'active': False, 'not_expected_reason': 'walkout'})
        for line in back:
            line.write({'active': True})

    def _ems_restore_walkout_lines(self):
        """Not validated, or reopened: the classes of the walkout day are regular absences again
        (or expected classes, while joining), without telling the family of past days."""
        self.ensure_one()
        students = self._ems_walkout_session_lines(self.line_ids.student_id,
                                                   [('not_expected_reason', '=', 'walkout')]).student_id
        day = [('attendance_session_id.date', '=', self.walkout_date)]
        for student in students:
            student._ems_restore_not_expected_lines([('not_expected_reason', '=', 'walkout')] + day)


class EmsStudentWalkoutLine(models.Model):
    """One student of a walkout proposal. Never the group vote: only whether it was cast."""
    _name = 'ems.student_walkout.line'
    _description = "Student of a student walkout proposal"
    _order = 'walkout_id, student_id'
    _sql_constraints = [
        ('student_unique', 'UNIQUE(walkout_id, student_id)', 'A student appears only once in a walkout proposal.'),
    ]

    walkout_id = fields.Many2one(string="Walkout proposal", comodel_name='ems.student_walkout', required=True,
                                 ondelete='cascade', index=True)
    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True, ondelete='cascade',
                                 index=True)
    has_portal = fields.Boolean(string="Portal access", readonly=True,
                                help="Whether the student had access to the portal when the proposal was made: "
                                     "only they vote.")
    voted = fields.Boolean(string="Voted", readonly=True)
    vote_date = fields.Datetime(string="Voted on", readonly=True)
    joins = fields.Boolean(string="Joins", readonly=True)
    join_answered = fields.Boolean(string="Answered whether they join", readonly=True)
    join_date = fields.Datetime(string="Answered on", readonly=True)
    # The family of a minor joining is asked to ratify it (Decret 102/2010, art. 24.2), on the portal
    # while joining lasts. Issue #844: it only says the family knows and agrees; nobody can revoke
    # the student's decision, and their classes of the day are off the roll-call all the same. The
    # family of an unratified minor is told of each class, for information only.
    needs_ratification = fields.Boolean(string="Needs the family's ratification", readonly=True)
    ratification = fields.Selection(string="Family ratification", selection=[
        ('pending', "Pending"),
        ('ratified', "Ratified"),
        ('refused', "Refused"),
    ], readonly=True)
    ratified_by_id = fields.Many2one(string="Answered by", comodel_name='res.partner', readonly=True,
                                     ondelete='set null')
    ratification_date = fields.Datetime(string="Family answered on", readonly=True)
    # Issue #840: a family that cannot use the portal asks the centre to ratify it; the tutor (or
    # whoever is above them) marks it by hand, and `ratified_by_id` is then that staff member.
    ratified_manually = fields.Boolean(string="Ratified by the centre", readonly=True,
                                       help="The tutor, or whoever is above them, marked the family's ratification by hand.")
    can_ratify_manually = fields.Boolean(compute='_compute_can_ratify_manually')
    @api.depends('joins', 'needs_ratification', 'ratification', 'walkout_id.state')
    @api.depends_context('uid')
    def _compute_can_ratify_manually(self):
        # The permission is the walkout's: checked once per walkout, not once per student.
        may_abort = {walkout: walkout._ems_user_may_abort() for walkout in self.walkout_id}
        for line in self:
            line.can_ratify_manually = line._ems_ratification_is_open() and may_abort[line.walkout_id]

    def _ems_ratification_is_open(self):
        """A minor's pending ratification, from joining until the Head of Studies validates. A family's
        refusal is theirs to change, never overridden."""
        self.ensure_one()
        return (self.joins and self.needs_ratification and self.ratification == 'pending'
                and self.walkout_id.state in ('joining', 'closed'))

    def _ems_can_ratify_manually(self):
        """Whoever may abort the proposal (the tutor, the chain above them, an administrator) may mark it."""
        self.ensure_one()
        return self._ems_ratification_is_open() and self.walkout_id._ems_user_may_abort()

    def action_ratify_manually(self):
        """Marks the family's ratification by hand, for a family that cannot use the portal."""
        self.ensure_one()
        if not self._ems_can_ratify_manually():
            raise UserError(_("The ratification of %(student)s cannot be marked by you now: only the tutor of the "
                              "group, the chain above them or an administrator can, for a minor whose family has "
                              "not answered, until the Head of Studies validates the walkout.",
                              student=self.student_id.name))
        self.sudo().write({'ratification': 'ratified', 'ratified_by_id': self.env.user.partner_id.id,
                           'ratification_date': fields.Datetime.now(), 'ratified_manually': True})
        self._ems_refresh_walkout_notices()
        self.walkout_id.sudo()._message_log(body=_(
            "%(user)s marked by hand the family's ratification that %(student)s joins the walkout.",
            user=self.env.user.name, student=self.student_id.name))


    def _ems_refresh_walkout_notices(self):
        """A ratification marked once the roll-calls of the day exist: their notice to the family of an
        unratified minor is withdrawn (or rectified, if already sent)."""
        for line in self:
            for session_line in line.walkout_id._ems_walkout_session_lines(
                    line.student_id, [('not_expected_reason', '=', 'walkout')]):
                session_line._update_notification()


class EmsStudentWalkoutRejectionReason(models.Model):
    """Why a student walkout proposal is aborted by the tutor or not validated by the Head of Studies: the catalog they pick from, edited in
    Student's Attendances > Configuration. "Other reasons" asks for details."""
    _name = 'ems.student_walkout.rejection_reason'
    _inherit = 'ems.reason.catalog'
    _description = "Student walkout rejection reason"

    requires_details = fields.Boolean(string="Requires details",
                                      help="Whoever rejects the proposal must explain it in the details (e.g. 'Other').")


class EmsStudentWalkoutRejectWizard(models.TransientModel):
    """Aborts a student walkout proposal (active_id) or does not validate it, with a reason from the
    catalog. The view explains which reasons are lawful when aborting."""
    _name = 'ems.student_walkout.reject.wizard'
    _description = "Reject a student walkout proposal"

    walkout_id = fields.Many2one(string="Walkout proposal", comodel_name='ems.student_walkout', required=True,
                                 default=lambda self: self.env.context.get('active_id'), ondelete='cascade')
    walkout_state = fields.Selection(related='walkout_id.state')
    reason_id = fields.Many2one(string="Reason", comodel_name='ems.student_walkout.rejection_reason', required=True)
    requires_details = fields.Boolean(related='reason_id.requires_details')
    details = fields.Text(string="Details")

    def action_reject(self):
        self.ensure_one()
        self.walkout_id._ems_reject(self.reason_id, self.details)
        return {'type': 'ir.actions.act_window_close'}
