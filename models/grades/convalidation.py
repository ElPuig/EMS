# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Grade a convalidated subject counts with in the grades subsystem: it is passed, and a
# vocational training cycle's final grade averages a convalidated module as a 5.
CONVALIDATED_GRADE = 5

# Line states that close a subject's request for good. A forwarded line is still waiting for
# the Departament d'Educació, so it keeps the request open.
RESOLVED_LINE_STATES = ('granted', 'rejected')


class EmsConvalidation(models.Model):
    _name = 'ems.convalidation'
    _description = "Convalidation request: a student asks for some of their study's subjects to be convalidated."
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 ondelete='restrict', index=True, tracking=True,
                                 domain="[('contact_type', 'in', ('student', 'applicant'))]")
    requester_id = fields.Many2one(string="Requested by", comodel_name='res.partner', ondelete='set null',
                                   help="Portal user who submitted the request: the student or a family contact.")
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', required=True,
                                ondelete='restrict', index=True,
                                default=lambda self: self._default_course_id())
    study_id = fields.Many2one(string="Study", comodel_name='ems.study', required=True, ondelete='restrict',
                               domain="[('level_id.allows_convalidation', '=', True)]")
    submission_date = fields.Datetime(string="Submission date", required=True, readonly=True,
                                      default=fields.Datetime.now)
    basis = fields.Selection(string="Grounds", required=True, default='prior_studies', selection=[
        ('prior_studies', 'Prior vocational training or university studies'),
        ('certificate', 'Professional certificate or accreditation of competences'),
        ('other', 'Other'),
    ])
    student_notes = fields.Text(string="Applicant's comments")
    attachment_ids = fields.Many2many(string="Supporting documents", comodel_name='ir.attachment',
                                      relation='ems_convalidation_attachment_rel',
                                      column1='convalidation_id', column2='attachment_id')
    line_ids = fields.One2many(string="Subjects", comodel_name='ems.convalidation.line',
                               inverse_name='convalidation_id', copy=True)
    allowed_subject_ids = fields.Many2many(string="Allowed subjects", comodel_name='ems.subject',
                                           compute='_compute_allowed_subject_ids')
    is_cancelled = fields.Boolean(string="Cancelled", default=False, copy=False, tracking=True)
    state = fields.Selection(string="State", compute='_compute_state', store=True, index=True, tracking=True,
                             selection=[
                                 ('submitted', 'Submitted'),
                                 ('in_progress', 'In progress'),
                                 ('resolved', 'Resolved'),
                                 ('cancelled', 'Cancelled'),
                             ])
    resolution_notes = fields.Text(string="Resolution comments",
                                   help="Shown to the student in the portal and in the resolution email.")
    resolution_date = fields.Date(string="Resolution date", readonly=True, copy=False)
    resolved_by_id = fields.Many2one(string="Resolved by", comodel_name='res.users', readonly=True, copy=False)
    granted_count = fields.Integer(string="Convalidated", compute='_compute_line_counts')
    pending_count = fields.Integer(string="To resolve", compute='_compute_line_counts')

    @api.model
    def _default_course_id(self):
        """The course a request applies to: the one being enrolled into, else the running one.
        Requests are made while enrolling, so the enrollment course comes first - the same order
        the portal's enrollment page uses."""
        Course = self.env['ems.course']
        return Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.search([('is_current', '=', True)], limit=1)

    @api.depends('study_id')
    def _compute_allowed_subject_ids(self):
        for convalidation in self:
            convalidation.allowed_subject_ids = convalidation.study_id._ems_convalidable_subjects()

    @api.depends('is_cancelled', 'line_ids.state')
    def _compute_state(self):
        for convalidation in self:
            states = set(convalidation.line_ids.mapped('state'))
            if convalidation.is_cancelled:
                convalidation.state = 'cancelled'
            elif states and states <= set(RESOLVED_LINE_STATES):
                convalidation.state = 'resolved'
            elif states - {'pending'}:
                convalidation.state = 'in_progress'
            else:
                convalidation.state = 'submitted'

    @api.depends('line_ids.state')
    def _compute_line_counts(self):
        for convalidation in self:
            convalidation.granted_count = len(convalidation.line_ids.filtered(lambda line: line.state == 'granted'))
            convalidation.pending_count = len(convalidation.line_ids.filtered(
                lambda line: line.state not in RESOLVED_LINE_STATES))

    @api.depends('student_id', 'course_id')
    def _compute_display_name(self):
        for convalidation in self:
            convalidation.display_name = \
                f"{convalidation.student_id.display_name or ''} ({convalidation.course_id.name or ''})"

    @api.constrains('study_id')
    def _check_study_allows_convalidation(self):
        for convalidation in self:
            if not convalidation.study_id.level_id.allows_convalidation:
                raise ValidationError(_("Convalidations cannot be requested for %s.")
                                      % convalidation.study_id.display_name)

    # study_id too: a constraint only fires for the fields being written, and a request created
    # without subjects carries no line_ids at all.
    @api.constrains('line_ids', 'study_id')
    def _check_has_lines(self):
        for convalidation in self:
            if not convalidation.line_ids:
                raise ValidationError(_("Select at least one subject to convalidate."))

    @api.model_create_multi
    def create(self, vals_list):
        # Nobody follows a request on creation: the portal creates it on the student's behalf,
        # and a follower would get an email for every message posted to the student's
        # Communications page (see _ems_post_communication) on top of the resolution email.
        convalidations = super(EmsConvalidation, self.with_context(mail_create_nosubscribe=True)).create(vals_list)
        convalidations._ems_link_attachments()
        for convalidation in convalidations:
            convalidation._ems_post_communication(
                _("Convalidation request submitted"),
                Markup("<p>{}</p>{}").format(
                    _("Subjects requested:"),
                    self.env['ems.base'].build_html_list(convalidation.line_ids.subject_id.mapped('display_name'))))
        return convalidations

    def write(self, vals):
        if 'study_id' in vals and self.line_ids.filtered(lambda line: line.state != 'pending'):
            raise UserError(_("The study of a request cannot change once a subject has been resolved."))
        res = super().write(vals)
        if 'attachment_ids' in vals:
            self._ems_link_attachments()
        if 'is_cancelled' in vals:
            self.line_ids._ems_sync_grades()
        self._ems_on_resolved()
        return res

    def unlink(self):
        # The lines' own unlink keeps the grades in sync; the database cascade would not.
        self.line_ids.unlink()
        return super().unlink()

    def _ems_link_attachments(self):
        """Attachments uploaded from the form's many2many widget are created unlinked
        (res_id 0): tie them to the request so they follow its access rights and show in the
        chatter's attachment box."""
        for convalidation in self:
            convalidation.attachment_ids.filtered(lambda attachment: not attachment.res_id).sudo().write({
                'res_model': self._name, 'res_id': convalidation.id,
            })

    def _ems_on_resolved(self):
        """Stamp and notify the requests that have just become resolved. Called after every
        change that can resolve one: a write on the request itself or on one of its lines, so
        it is idempotent - the stamp is what tells a request already notified. A request
        reopened after its resolution loses the stamp, so resolving it again notifies the new
        outcome."""
        reopened = self.filtered(lambda convalidation: convalidation.state != 'resolved'
                                 and convalidation.resolution_date)
        if reopened:
            reopened.sudo().write({'resolution_date': False, 'resolved_by_id': False})
        for convalidation in self.filtered(lambda convalidation: convalidation.state == 'resolved'
                                           and not convalidation.resolution_date):
            convalidation.sudo().write({
                'resolution_date': fields.Date.context_today(convalidation),
                'resolved_by_id': self.env.user.id,
            })
            convalidation._ems_send_resolution()

    def _ems_send_resolution(self):
        """Email the resolution to whoever speaks for the student: the student when adult, the
        family when a minor (res.partner._ems_notification_recipients(), the rule every other
        EMS notification follows). A recipient without an email is logged in the chatter."""
        self.ensure_one()
        template = self.env.ref('ems.email_template_convalidation_resolved', raise_if_not_found=False)
        if not template:
            return
        recipients = self.student_id._ems_notification_recipients()
        addressable = recipients.filtered('email')
        for recipient in addressable:
            template.with_context(lang=recipient.lang or self.student_id.lang).sudo().send_mail(
                self.id, force_send=False, email_values={'email_to': recipient.email})
        # The same text, in the language of whoever reads it, on the Communications page.
        lang = recipients[:1].lang or self.student_id.lang or self.env.lang
        localized = template.with_context(lang=lang).sudo()
        self._ems_post_communication(
            localized._render_field('subject', self.ids)[self.id],
            localized._render_field('body_html', self.ids)[self.id])
        if addressable:
            body = _("Resolution sent to %s.") % ", ".join(addressable.mapped('email'))
        else:
            body = _("The resolution could not be emailed: nobody to notify has an email address.")
        self.sudo().message_post(body=body, message_type='comment', subtype_xmlid='mail.mt_note')

    def _ems_post_communication(self, subject, body):
        """Record a message the student (or the family) has to see on the portal's
        Communications page, which lists the requests' comments but never their internal
        notes. Nobody follows a request (see create), so posting notifies nobody: the emails
        are sent on their own terms (_ems_send_resolution)."""
        self.ensure_one()
        self.sudo().message_post(subject=subject, body=body, message_type='comment',
                                 subtype_xmlid='mail.mt_comment')

    # --- actions ---

    def action_cancel(self):
        for convalidation in self:
            if convalidation.line_ids.filtered(lambda line: line.state != 'pending'):
                raise UserError(_("A request cannot be cancelled once a subject has been resolved or forwarded."))
        self.write({'is_cancelled': True})
        for convalidation in self:
            convalidation._ems_post_communication(
                _("Convalidation request cancelled"),
                _("The request has been cancelled by %s.") % self.env.user.name)

    def action_reopen(self):
        self.write({'is_cancelled': False})
        for convalidation in self:
            convalidation._ems_post_communication(
                _("Convalidation request reopened"),
                _("The request has been reopened by %s.") % self.env.user.name)

    def action_grant_pending(self):
        self.line_ids.filtered(lambda line: line.state == 'pending').action_grant()

    # --- portal helpers ---

    @api.model
    def _ems_portal_study(self, student):
        """The study a portal student can request convalidations for, or an empty recordset.

        The enrollment of the course being enrolled into wins over the current group: a
        student finishing SMX and enrolling into DAM asks for DAM's modules. Only studies
        whose level allows convalidations qualify."""
        course = self._default_course_id()
        order = self.env['sale.order'].sudo().search([
            ('partner_id', '=', student.id),
            ('ems_course_id', '=', course.id),
            ('state', '!=', 'cancel'),
        ], limit=1) if course else self.env['sale.order']
        study = order.ems_study_id or student.sudo().main_group_id.study_id
        return study if study.level_id.allows_convalidation else study.browse()

    @api.model
    def _ems_portal_requestable_subjects(self, student, study):
        """Subjects the student can still ask for: the study's, minus those already requested
        and not rejected (a rejected subject can be asked for again with new documents)."""
        taken = self.env['ems.convalidation.line'].sudo().search([
            ('student_id', '=', student.id),
            ('subject_id', 'in', study._ems_convalidable_subjects().ids),
            ('convalidation_id.is_cancelled', '=', False),
            ('state', '!=', 'rejected'),
        ]).mapped('subject_id')
        return study._ems_convalidable_subjects() - taken


class EmsConvalidationLine(models.Model):
    _name = 'ems.convalidation.line'
    _description = "Convalidation request line: one subject and its resolution."
    _order = 'convalidation_id, subject_id'
    _sql_constraints = [
        ('unique_subject_per_request', 'unique (convalidation_id, subject_id)',
         'A subject can only be requested once per convalidation request.'),
    ]

    convalidation_id = fields.Many2one(string="Request", comodel_name='ems.convalidation', required=True,
                                       ondelete='cascade', index=True)
    student_id = fields.Many2one(string="Student", related='convalidation_id.student_id', store=True, index=True)
    course_id = fields.Many2one(string="Course", related='convalidation_id.course_id', store=True)
    subject_id = fields.Many2one(string="Subject", comodel_name='ems.subject', required=True, ondelete='restrict')
    state = fields.Selection(string="Resolution", required=True, default='pending', selection=[
        ('pending', 'Pending'),
        ('forwarded', 'Forwarded to the Department of Education'),
        ('granted', 'Convalidated'),
        ('rejected', 'Rejected'),
    ])
    resolution_notes = fields.Char(string="Remarks")

    @api.depends('subject_id')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.subject_id.display_name or ""

    @api.constrains('subject_id', 'convalidation_id')
    def _check_subject_in_study(self):
        for line in self:
            if line.subject_id not in line.convalidation_id.study_id._ems_convalidable_subjects():
                raise ValidationError(_("%(subject)s is not a subject of %(study)s that can be convalidated.") % {
                    'subject': line.subject_id.display_name,
                    'study': line.convalidation_id.study_id.display_name,
                })

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('state', 'pending') != 'pending' for vals in vals_list):
            self._ems_check_can_resolve()
        lines = super().create(vals_list)
        lines._ems_sync_grades()
        lines.convalidation_id._ems_on_resolved()
        return lines

    def write(self, vals):
        if 'state' not in vals and 'subject_id' not in vals:
            return super().write(vals)
        self._ems_check_can_resolve()
        # A changed subject leaves its previous one to be re-evaluated too.
        previous_pairs, courses = self._ems_grade_keys()
        res = super().write(vals)
        self._ems_sync_grades(previous_pairs, courses)
        self.convalidation_id._ems_on_resolved()
        return res

    def unlink(self):
        if self.filtered(lambda line: line.state != 'pending'):
            self._ems_check_can_resolve()
        pairs, courses = self._ems_grade_keys()
        convalidations = self.convalidation_id
        res = super().unlink()
        self.browse()._ems_sync_grades(pairs, courses)
        convalidations.exists()._ems_on_resolved()
        return res

    def _ems_check_can_resolve(self):
        """Resolving is the Head of Studies' call (Director included, it implies the group);
        the secretariat registers requests but never decides them."""
        user = self.env.user
        if not self.env.su and not (user.has_group('ems.group_head_of_studies')
                                    or user.has_group('ems.group_academic_admin')):
            raise UserError(_("Only the Head of Studies can resolve convalidations."))

    # --- actions ---

    def action_grant(self):
        self.write({'state': 'granted'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_forward(self):
        self.write({'state': 'forwarded'})

    def action_reset(self):
        self.write({'state': 'pending'})

    # --- grades sync ---

    @api.model
    def _ems_is_convalidated(self, student, subject):
        """Whether 'subject' is convalidated for 'student': some granted line of a request that
        is still in force. sudo: grade lines are created by teachers too, who cannot read
        convalidations."""
        return bool(self.sudo().search_count([
            ('student_id', '=', student.id),
            ('subject_id', '=', subject.id),
            ('state', '=', 'granted'),
            ('convalidation_id.is_cancelled', '=', False),
        ], limit=1))

    def _ems_grade_keys(self):
        """The (student, subject) pairs and the courses these lines touch, read before a change
        that may make the lines themselves unreadable (an unlink)."""
        return {(line.student_id, line.subject_id) for line in self}, self.mapped('course_id')

    def _ems_sync_grades(self, extra_pairs=(), extra_courses=None):
        """Mirror each affected (student, subject)'s convalidation onto its grades: every live
        grade line, and the subject in the year record of the request's course when that
        history has already been frozen (the Department can take months to answer)."""
        pairs, courses = self._ems_grade_keys()
        pairs |= set(extra_pairs)
        courses |= extra_courses or self.env['ems.course']
        GradeLine = self.env['ems.grade_subject_line'].sudo().with_context(ems_convalidation_sync=True)
        SubjectRecord = self.env['ems.student.year_record.subject'].sudo()
        for student, subject in pairs:
            convalidated = self._ems_is_convalidated(student, subject)
            GradeLine.search([
                ('student_id', '=', student.id),
                ('grade_session_id.subject_id', '=', subject.id),
                ('is_convalidated', '!=', convalidated),
            ]).write({'is_convalidated': convalidated})
            SubjectRecord.search([
                ('record_id.student_id', '=', student.id),
                ('record_id.course_id', 'in', courses.ids),
                ('subject_id', '=', subject.id),
                ('is_convalidated', '!=', convalidated),
            ])._ems_set_convalidated(convalidated)
