# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

GROUP_VOTES = ('yes', 'no', 'abstain')
JUSTIFY_TASK = 'ems.mail_activity_student_walkout_justify'
REVIEW_TASK = 'ems.mail_activity_student_walkout_review'
# What the group sees: a call the Head of Studies has not accepted is only its delegate's.
VISIBLE_STATES = ('voting', 'closed', 'justified')


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
    close_date = fields.Date(string="Vote closes on", required=True, readonly=True,
                             help="The vote is open until the end of the day before; this day the minute is sent.")
    last_vote_date = fields.Date(string="Last day to vote", compute='_compute_last_vote_date')
    notes = fields.Text(string="Notes", readonly=True)
    attachment_ids = fields.Many2many(string="Union's call", comodel_name='ir.attachment',
                                      relation='ems_student_walkout_attachment_rel', column1='walkout_id',
                                      column2='attachment_id', readonly=True)
    state = fields.Selection(string="State", selection=[
        ('pending', "Pending review"),
        ('voting', "Voting"),
        ('closed', "Closed"),
        ('justified', "Justified"),
        ('rejected', "Rejected"),
        ('expired', "Expired"),
        ('cancelled', "Cancelled"),
    ], required=True, default='pending', readonly=True)
    # The Head of Studies accepts the call before the group hears of it, or rejects it with a reason.
    decided_by_id = fields.Many2one(string="Decided by", comodel_name='res.users', readonly=True, copy=False)
    decision_datetime = fields.Datetime(string="Decided on", readonly=True, copy=False)
    rejection_reason_id = fields.Many2one(string="Rejection reason", comodel_name='ems.student_walkout.rejection_reason',
                                          readonly=True, copy=False, ondelete='restrict')
    rejection_details = fields.Text(string="Rejection details", readonly=True, copy=False)
    can_decide = fields.Boolean(compute='_compute_can_decide')
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
        for walkout in self:
            walkout.name = walkout.group_id.name and walkout.walkout_date and \
                f"{walkout.group_id.name} - {format_date(self.env, walkout.walkout_date)}"

    @api.depends('close_date')
    def _compute_last_vote_date(self):
        for walkout in self:
            walkout.last_vote_date = walkout.close_date and walkout.close_date - timedelta(days=1)

    @api.depends('group_yes_count', 'group_no_count')
    def _compute_group_supports(self):
        for walkout in self:
            walkout.group_supports = walkout.group_yes_count > walkout.group_no_count

    @api.depends('line_ids.joins', 'line_ids.voted', 'line_ids.has_portal')
    def _compute_line_counts(self):
        for walkout in self:
            joining = walkout.line_ids.filtered('joins')
            walkout.joining_student_ids = joining.student_id
            walkout.joining_count = len(joining)
            walkout.voter_count = len(walkout.line_ids.filtered('has_portal'))
            walkout.voted_count = len(walkout.line_ids.filtered('voted'))

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_can_decide(self):
        for walkout in self:
            walkout.can_decide = walkout.state == 'pending' and walkout._ems_user_may_decide()

    @api.depends('state', 'line_ids.joins', 'group_yes_count', 'group_no_count')
    @api.depends_context('uid')
    def _compute_can_generate_justification(self):
        for walkout in self:
            walkout.can_generate_justification = walkout._ems_has_something_to_justify() and \
                walkout._ems_user_may_justify()

    # Portal: the controller passes the logged-in student; everything is checked here.

    @api.model
    def _ems_portal_open(self, partner, values, files):
        """Opens a call for `partner`'s group: `values` has walkout_date, close_date and notes,
        `files` the union's call as (name, content) pairs. Emails every student with portal access."""
        partner = partner.sudo()
        group = partner._ems_walkout_opener_group()
        if not group:
            raise UserError(_("Only the delegate or the sub-delegate of a group that may call a student walkout "
                              "can open one."))
        walkout_date = fields.Date.to_date(values.get('walkout_date'))
        close_date = fields.Date.to_date(values.get('close_date'))
        self._ems_check_dates(walkout_date, close_date)
        files = [(name, content) for name, content in files or [] if name and content]
        if not files:
            raise UserError(_("Attach the call of the students' union."))
        groups = group | group.joinable_group_ids.filtered(
            lambda half: partner in (half.delegate_id | half.subdelegate_id))
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
            'close_date': close_date,
            'notes': (values.get('notes') or '').strip()[:2000] or False,
            'line_ids': [(0, 0, {'student_id': student.id, 'has_portal': student.id in with_portal})
                         for student in students],
        })
        walkout.attachment_ids = self.env['ir.attachment'].create([{
            'name': name, 'raw': content, 'res_model': self._name, 'res_id': walkout.id,
        } for name, content in files])
        walkout._message_log(body=_("Opened by %(name)s from the portal.", name=partner.name))
        walkout._ems_request_review()
        return walkout

    def _ems_portal_vote(self, partner, group_vote, joins):
        """`partner` answers: the group vote counts once and is never linked to them; whether they
        join can be changed until the vote closes."""
        self.ensure_one()
        line = self.line_ids.filtered(lambda line: line.student_id == partner and line.has_portal)
        if not line:
            raise UserError(_("Only the students of the group with access to the portal can vote."))
        if not self._ems_voting_open():
            raise UserError(_("The vote of this student walkout is closed."))
        vals = {'joins': bool(joins), 'vote_date': fields.Datetime.now()}
        if not line.voted:
            if group_vote not in GROUP_VOTES:
                raise UserError(_("Say whether the group supports the walkout."))
            # Two answers at the same time update the same rows: PostgreSQL refuses the second
            # (REPEATABLE READ) and Odoo retries it, so no vote is lost nor counted twice.
            counter = f'group_{group_vote}_count'
            self.write({counter: self[counter] + 1})
            vals['voted'] = True
        line.write(vals)

    def _ems_portal_close(self, partner):
        self._ems_check_delegate(partner)
        self.action_close()

    def _ems_portal_cancel(self, partner):
        self._ems_check_delegate(partner)
        if self.state not in ('pending', 'voting'):
            raise UserError(_("Only a call still being reviewed or voted can be cancelled."))
        self.state = 'cancelled'
        self._ems_sync_user_tasks(self.env.ref(REVIEW_TASK), self.env['res.users'], fields.Date.today())
        self._message_log(body=_("Cancelled by %(name)s from the portal.", name=partner.name))

    def _ems_check_delegate(self, partner):
        """The opener, or the group's current delegate or sub-delegate, manage the call."""
        self.ensure_one()
        if partner != self.opener_id and partner not in (self.group_ids.delegate_id | self.group_ids.subdelegate_id):
            raise UserError(_("Only the delegate or the sub-delegate of the group can manage this call."))

    @api.model
    def _ems_check_dates(self, walkout_date, close_date):
        """The notice period, in days: the walkout far enough, and the vote closing in time for the
        Head of Studies to get the minute that many days ahead."""
        if not walkout_date or not close_date:
            raise UserError(_("Give the walkout day and the day the vote closes."))
        today = self.get_local_today()
        notice = self.env.company.walkout_notice_days
        if (walkout_date - today).days < notice:
            raise UserError(_("A student walkout must be called at least %(days)s days in advance.", days=notice))
        if close_date <= today:
            raise UserError(_("The vote closes tomorrow at the earliest: the group needs at least one day to vote."))
        latest = walkout_date - timedelta(days=notice)
        if close_date > latest:
            raise UserError(_("The vote must close at least %(days)s days before the walkout: on %(date)s at the "
                              "latest.", days=notice, date=format_date(self.env, latest)))

    def _ems_voting_open(self):
        self.ensure_one()
        return self.state == 'voting' and self.get_local_today() < self.close_date

    # Closing

    @api.model
    def _cron_ems_close_due(self):
        """Hourly: the calls whose vote ended yesterday are closed, and the ones the Head of Studies
        did not accept by then expire (only their delegate sees it, on the portal)."""
        due = self.search([('state', 'in', ('pending', 'voting')), ('close_date', '<=', self.get_local_today())])
        due.filtered(lambda walkout: walkout.state == 'voting').action_close()
        for walkout in due.filtered(lambda walkout: walkout.state == 'pending'):
            walkout.state = 'expired'
            walkout._ems_sync_user_tasks(self.env.ref(REVIEW_TASK), self.env['res.users'], walkout.close_date)
            walkout._message_log(body=_("Expired: the Head of Studies did not accept it before the vote had to close."))

    def action_close(self):
        for walkout in self.filtered(lambda walkout: walkout.state == 'voting'):
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
        """The minute to the Head of Studies right away (the walkout is a few days off: not a notice
        for the daily summary), with a task when there is somebody to justify; the result to the
        group, and the family of each student who joins and is a minor (or shares with it)."""
        self.ensure_one()
        users = self._ems_head_users()
        self._ems_mail_staff('ems.email_template_student_walkout_head', users,
                             attachment_ids=[(4, self.pdf_attachment_id.id)])
        if self._ems_has_something_to_justify():
            self.sudo()._ems_sync_user_tasks(self.env.ref(JUSTIFY_TASK), users, self.walkout_date)
        self._ems_mail_students('ems.email_template_student_walkout_result')
        family_template = self.env.ref('ems.email_template_student_walkout_family').sudo()
        for line in self.line_ids.filtered('joins'):
            student = line.student_id
            if student.is_adult and not student.auth_share:
                continue
            emails = student._ems_family_contacts().filtered('email').mapped('email')
            if emails:
                family_template.send_mail(line.id, email_values={'email_to': ','.join(emails)})

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
        """Who decides on the call and gets its minute: the Head or Deputy Head of Studies above the
        group's tutor; failing that, the academic administrators. Noted on the call."""
        self.ensure_one()
        tutor = self.group_id.tutor_id.sudo()
        head = tutor.find_head_of_studies() if tutor else tutor
        self.head_of_studies_id = head
        return head.user_id or self.env.ref('ems.group_academic_admin').sudo().users.filtered(
            lambda user: not user.share)

    def _ems_mail_staff(self, template_xmlid, users, **email_values):
        """An email to staff, sent at once: the walkout is only a few days off."""
        email_to = ','.join(users.filtered('email').mapped('email_formatted'))
        if email_to:
            self.env.ref(template_xmlid).sudo().send_mail(self.id, email_values={'email_to': email_to, **email_values})

    # Reviewing

    def _ems_request_review(self):
        """A new call goes to the Head of Studies first, with a task due the last day of the vote:
        the group hears of it only once accepted."""
        self.ensure_one()
        users = self._ems_head_users()
        self._ems_mail_staff('ems.email_template_student_walkout_review', users)
        self.sudo()._ems_sync_user_tasks(self.env.ref(REVIEW_TASK), users, self.last_vote_date)

    def _ems_user_may_decide(self):
        """A Head of Studies, Deputy Head of Studies or Director above the group's tutor (tutor scope),
        or an administrator."""
        self.ensure_one()
        return self.get_user_is_admin() or (self.env.user.has_group('ems.group_head_of_studies')
                                            and self.user_acts_as_tutor(self.group_id.tutor_id))

    def _ems_check_decide(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("This student walkout call has already been decided."))
        if not self._ems_user_may_decide():
            raise UserError(_("Only the Head of Studies, the Deputy Head of Studies or the Director of this group, or "
                              "an administrator, can accept or reject a student walkout call."))

    def _ems_decided(self, vals):
        walkout = self.sudo()
        walkout.write({'decided_by_id': self.env.uid, 'decision_datetime': fields.Datetime.now(), **vals})
        walkout._ems_sync_user_tasks(self.env.ref(REVIEW_TASK), self.env['res.users'], self.last_vote_date, done=True)
        return walkout

    def action_accept(self):
        """The group may vote: each student with portal access gets the call email."""
        self._ems_check_decide()
        walkout = self._ems_decided({'state': 'voting'})
        walkout._ems_mail_students('ems.email_template_student_walkout_call')
        walkout._message_log(body=_("Accepted by %(name)s.", name=self.env.user.name))

    def action_open_reject_wizard(self):
        self._ems_check_decide()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reject the student walkout call"),
            'res_model': 'ems.student_walkout.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def _ems_reject(self, reason, details):
        """Rejected with a reason: only the delegate who opened it is told; nobody else hears of it."""
        self._ems_check_decide()
        details = (details or '').strip()
        if reason.requires_details and not details:
            raise UserError(_("Explain the reason in the details: %(reason)s", reason=reason.name))
        walkout = self._ems_decided({'state': 'rejected', 'rejection_reason_id': reason.id,
                                     'rejection_details': details or False})
        walkout._ems_mail_students('ems.email_template_student_walkout_rejected',
                                   walkout.line_ids.filtered(lambda line: line.student_id == walkout.opener_id))
        walkout._message_log(body=_("Rejected by %(name)s: %(reason)s", name=self.env.user.name, reason=reason.name))

    # Justifying

    def _ems_has_something_to_justify(self):
        self.ensure_one()
        return self.state == 'closed' and self.group_supports and bool(self.line_ids.filtered('joins'))

    def _ems_user_may_justify(self):
        """A Head of Studies, Deputy Head of Studies or Director above every student who joins
        (tutor scope), or an administrator."""
        self.ensure_one()
        if self.get_user_is_admin():
            return True
        return self.env.user.has_group('ems.group_head_of_studies') and \
            self.env['ems.attendance_justification']._user_may_justify(self.joining_student_ids)

    def action_generate_justification(self):
        """One full-day justification of the walkout day for the students who join, except the ones
        already justified that day (noted in the chatter)."""
        self.ensure_one()
        if not self._ems_has_something_to_justify():
            raise UserError(_("There is nobody to justify: the vote is not closed, the group did not support the "
                              "walkout, nobody joined it or it is already justified."))
        if not self._ems_user_may_justify():
            raise UserError(_("Only the Head of Studies, the Deputy Head of Studies or the Director of these "
                              "students, or an administrator, can justify a student walkout."))
        Justification = self.env['ems.attendance_justification']
        period = Justification._whole_day_vals(self.walkout_date)
        joining = self.joining_student_ids
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
        if skipped:
            walkout._message_log(body=_("Not justified again, they already had a justification that day: %(names)s",
                                        names=", ".join(skipped.mapped('name'))))
        return justification and justification.get_formview_action()

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
    joins = fields.Boolean(string="Joins", readonly=True)
    vote_date = fields.Datetime(string="Answered on", readonly=True)


class EmsStudentWalkoutRejectionReason(models.Model):
    """Why the Head of Studies rejects a student walkout call: the catalog they pick from, edited in
    Student's Attendances > Configuration. "Other reasons" asks for details."""
    _name = 'ems.student_walkout.rejection_reason'
    _description = "Student walkout rejection reason"
    _order = 'sequence, name'

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    requires_details = fields.Boolean(string="Requires details",
                                      help="Whoever rejects the call must explain it in the details (e.g. 'Other').")


class EmsStudentWalkoutRejectWizard(models.TransientModel):
    """Rejects a student walkout call (active_id) with a reason from the catalog."""
    _name = 'ems.student_walkout.reject.wizard'
    _description = "Reject a student walkout call"

    walkout_id = fields.Many2one(string="Walkout call", comodel_name='ems.student_walkout', required=True,
                                 default=lambda self: self.env.context.get('active_id'), ondelete='cascade')
    reason_id = fields.Many2one(string="Reason", comodel_name='ems.student_walkout.rejection_reason', required=True)
    requires_details = fields.Boolean(related='reason_id.requires_details')
    details = fields.Text(string="Details")

    def action_reject(self):
        self.ensure_one()
        self.walkout_id._ems_reject(self.reason_id, self.details)
        return {'type': 'ir.actions.act_window_close'}
