# -*- coding: utf-8 -*-

import logging

from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Grade a convalidated subject gets when nobody says otherwise. The Head of Studies (or the
# secretariat afterwards) can replace it with the one the previous studies actually hold.
CONVALIDATED_GRADE = 5

# States a request can no longer move on from.
CLOSED_STATES = ('completed', 'rejected', 'cancelled')


class EmsConvalidation(models.Model):
    _name = 'ems.convalidation'
    _description = "Convalidation request: a student asks for some of their study's subjects to be convalidated."
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'

    name = fields.Char(string="Registration number", readonly=True, copy=False, index=True,
                       help="Registry entry of the request, e.g. CONV-2026-27-0001: the course it applies "
                            "to and a number that starts again every course. Assigned on submission.")
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
    # The circuit is linear: the student files it, the Head of Studies validates it (and grades
    # it), and the secretariat registers the result in Esfera and completes it. Only then does
    # the grade reach the student's own grades.
    state = fields.Selection(string="State", default='pending', required=True, index=True,
                             copy=False, readonly=True, tracking=True, selection=[
                                 ('pending', 'Pending'),
                                 ('in_progress', 'In progress'),
                                 ('completed', 'Completed'),
                                 ('rejected', 'Rejected'),
                                 ('cancelled', 'Cancelled'),
                             ])
    resolution_notes = fields.Text(string="Resolution comments",
                                   help="Shown to the student in the portal and in the resolution email.")
    validation_date = fields.Date(string="Validation date", readonly=True, copy=False)
    validated_by_id = fields.Many2one(string="Validated by", comodel_name='res.users', readonly=True, copy=False)
    resolution_date = fields.Date(string="Resolution date", readonly=True, copy=False)
    resolved_by_id = fields.Many2one(string="Resolved by", comodel_name='res.users', readonly=True, copy=False)
    granted_count = fields.Integer(string="Convalidated", compute='_compute_line_counts')
    pending_count = fields.Integer(string="To resolve", compute='_compute_line_counts')
    has_centre_title = fields.Boolean(string="Holds a title from this centre", compute='_compute_has_centre_title',
                                      help="The student's academic history records a title obtained here, so "
                                           "their previous grades can be looked up. Its absence proves nothing: "
                                           "only recent years are in EMS.")

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

    @api.depends('line_ids.state')
    def _compute_line_counts(self):
        for convalidation in self:
            convalidation.granted_count = len(convalidation.line_ids.filtered(lambda line: line.state == 'granted'))
            convalidation.pending_count = len(convalidation.line_ids.filtered(lambda line: line.state == 'pending'))

    @api.depends('student_id')
    def _compute_has_centre_title(self):
        # sudo: the academic history is not readable by everyone who resolves convalidations.
        records = self.env['ems.student.year_record'].sudo().search([
            ('student_id', 'in', self.student_id.ids), ('title_obtained', '=', True)])
        with_title = set(records.mapped('student_id').ids)
        for convalidation in self:
            convalidation.has_centre_title = convalidation.student_id.id in with_title

    @api.depends('name', 'student_id', 'course_id')
    def _compute_display_name(self):
        for convalidation in self:
            label = f"{convalidation.student_id.display_name or ''} ({convalidation.course_id.name or ''})"
            convalidation.display_name = f"{convalidation.name} - {label}" if convalidation.name else label

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
        for vals in vals_list:
            if not vals.get('name'):
                course = self.env['ems.course'].browse(vals.get('course_id')) or self._default_course_id()
                vals['name'] = self._ems_next_registration_number(course)
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
        convalidations._ems_schedule_task('ems.mail_activity_convalidation_review')
        return convalidations

    def write(self, vals):
        if 'study_id' in vals and self.filtered(lambda convalidation: convalidation.state != 'pending'):
            raise UserError(_("The study of a request cannot change once it has been validated."))
        res = super().write(vals)
        if 'attachment_ids' in vals:
            self._ems_link_attachments()
        if 'state' in vals:
            self.line_ids._ems_sync_grades()
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

    @api.model
    def _ems_next_registration_number(self, course):
        """Next registry entry for `course`: CONV-<start>-<end, two digits>-<4-digit counter>,
        the counter starting again every course. One ir.sequence per course, created the first
        time that course gets a request, so nothing has to be prepared before a new year opens.
        sudo: the request is usually filed from the portal."""
        if not course:
            return False
        Sequence = self.env['ir.sequence'].sudo()
        code = f'ems.convalidation.course.{course.id}'
        if not Sequence.search_count([('code', '=', code)]):
            Sequence.create({
                'name': f"Convalidations {course.name}",
                'code': code,
                'prefix': f"CONV-{course.start}-{str(course.end)[-2:]}-",
                'padding': 4,
                'company_id': False,
            })
        return Sequence.next_by_code(code)

    # --- who may do what -----------------------------------------------------

    def _ems_is_head_of_studies(self):
        """The Head of Studies (Director included, it implies the group) validates and grades."""
        return self.env.su or self.env.user.has_group('ems.group_head_of_studies') \
            or self.env.user.has_group('ems.group_academic_admin')

    def _ems_is_secretary(self):
        """The secretariat registers the resolution in Esfera and completes the request."""
        return self.env.su or self.env.user.has_group('ems.group_secretary') \
            or self.env.user.has_group('ems.group_academic_admin')

    def _ems_check_head_of_studies(self):
        if not self._ems_is_head_of_studies():
            raise UserError(_("Only the Head of Studies can validate convalidations."))

    def _ems_check_secretary(self):
        if not self._ems_is_secretary():
            raise UserError(_("Only the secretariat can complete a validated convalidation."))

    def _ems_check_state(self, expected):
        for convalidation in self:
            if convalidation.state not in expected:
                raise UserError(_("This request cannot be processed in its current state (%s).")
                                % dict(self._fields['state']._description_selection(self.env))[convalidation.state])

    # --- tasks ---------------------------------------------------------------

    def _ems_task_recipients(self, xmlid):
        """Who a convalidation task belongs to. Both are positions of the centre, not a
        configurable list, so they stay out of Academic Management > Configuration > Task
        Assignment on purpose - the same choice docs/en/developers/shared/task_assignment.md
        makes for attendance corrections, whose recipient also comes from the organisation:

        - the review is the Deputy Head of Studies' (ems.role_dhos), who handles vocational
          training;
        - the registration in Esfera is the whole secretariat's (ems.group_secretary). The EMS
          administrator is left out: it implies every group, so a group alone would hand it
          every task of every kind - the very reason Task Assignment stopped deriving its
          recipients from groups.

        Archived users and OdooBot never get one: nobody reads their inbox."""
        users = self.env['res.users']
        if xmlid == 'ems.mail_activity_convalidation_review':
            role = self.env.ref('ems.role_dhos', raise_if_not_found=False)
            if role:
                users = self.env['hr.employee'].sudo().browse(role.sudo().employee_ids.ids).exists().user_id
        elif xmlid == 'ems.mail_activity_convalidation_registration':
            users = self.env.ref('ems.group_secretary').sudo().users
            administrators = self.env.ref('ems.group_academic_admin', raise_if_not_found=False)
            if administrators:
                users -= administrators.sudo().users
        users = users.filtered(lambda user: user.active and user.id != SUPERUSER_ID)
        if not users:
            _logger.warning("Nobody holds the position in charge of %s: no task will be scheduled.", xmlid)
        return users

    def _ems_schedule_task(self, xmlid):
        """Put the request in the to-do list of whoever the task belongs to.

        ``mail_activity_quick_update`` suppresses Odoo's "X has assigned you the following
        activity" email: the task itself is the notice, and its author would otherwise be the
        family that filed the request from the portal."""
        users = self._ems_task_recipients(xmlid)
        if not users:
            return
        for convalidation in self:
            for user in users:
                convalidation.sudo().with_context(mail_activity_quick_update=True).activity_schedule(
                    act_type_xmlid=xmlid,
                    summary=_("Convalidation request: %s") % convalidation.student_id.display_name,
                    user_id=user.id,
                )
            # The to-do is their notice; a follower would also get every message meant for the
            # student's Communications page.
            convalidation.sudo().message_unsubscribe(partner_ids=users.mapped('partner_id').ids)

    def _ems_close_tasks(self):
        """Drop every pending convalidation task of these requests: the step that had to be
        done is done."""
        task_types = self.env.ref('ems.mail_activity_convalidation_review') \
            | self.env.ref('ems.mail_activity_convalidation_registration')
        self.sudo().activity_ids.filtered(lambda activity: activity.activity_type_id in task_types).unlink()

    # --- notices -------------------------------------------------------------

    def _ems_stamp_resolution(self):
        self.sudo().write({
            'resolution_date': fields.Date.context_today(self),
            'resolved_by_id': self.env.user.id,
        })

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

    # --- actions -------------------------------------------------------------

    def action_cancel(self):
        self._ems_check_state(('pending',))
        self.sudo().write({'state': 'cancelled'})
        self._ems_close_tasks()
        for convalidation in self:
            convalidation._ems_post_communication(
                _("Convalidation request cancelled"),
                _("The request has been cancelled by %s.") % self.env.user.name)

    def action_reopen(self):
        self._ems_check_state(('cancelled',))
        self.sudo().write({'state': 'pending'})
        for convalidation in self:
            convalidation._ems_post_communication(
                _("Convalidation request reopened"),
                _("The request has been reopened by %s.") % self.env.user.name)
        self._ems_schedule_task('ems.mail_activity_convalidation_review')

    def action_grant_pending(self):
        """Convalidate every subject still undecided, with the default grade: the usual case,
        where the whole request is accepted as filed."""
        self.line_ids.filtered(lambda line: line.state == 'pending').action_grant()

    def action_validate(self):
        """The Head of Studies' step: every subject is decided, so the request moves on to the
        secretariat - unless nothing was granted, in which case there is nothing to register in
        Esfera and the request is already resolved."""
        self._ems_check_head_of_studies()
        self._ems_check_state(('pending',))
        for convalidation in self:
            if convalidation.pending_count:
                raise UserError(_("Convalidate or reject every subject of the request before validating it."))
        self._ems_close_tasks()
        rejected = self.filtered(lambda convalidation: not convalidation.granted_count)
        validated = self - rejected
        if validated:
            validated.sudo().write({
                'state': 'in_progress',
                'validation_date': fields.Date.context_today(self),
                'validated_by_id': self.env.user.id,
            })
            for convalidation in validated:
                convalidation._ems_post_communication(
                    _("Convalidation request validated"),
                    _("The Head of Studies has validated the request. The secretariat will now "
                      "register it, and the grades will be published once it is completed."))
            validated._ems_schedule_task('ems.mail_activity_convalidation_registration')
        rejected._ems_reject()

    def action_complete(self):
        """The secretariat's step: the resolution is registered in Esfera, so the grades can be
        published and the student notified."""
        self._ems_check_secretary()
        self._ems_check_state(('in_progress',))
        self.sudo().write({'state': 'completed'})
        self._ems_stamp_resolution()
        self._ems_close_tasks()
        for convalidation in self:
            convalidation._ems_send_resolution()
        self._ems_withdraw_convalidated_subjects()

    def _ems_withdraw_convalidated_subjects(self):
        """The student stops taking every subject the request convalidated: their subject
        enrollment is deleted - grades already written included, the convalidation replaces them
        - which drops them from the attendance lists and from the open grade sessions, the same
        cascade as any other deleted enrollment. The history keeps the subject all the same
        (ems.student.year_record adds it from the convalidation), and whoever teaches it, plus
        the group's tutor, is told with an activity on the student.

        Resolved before deleting: the enrollment is what says which group the subject was taught
        in. A request completed before the student is placed has nothing to delete yet; the
        placement itself skips convalidated subjects (sale.order._ems_apply_destination_placement)."""
        Enrollment = self.env['ems.enrollment'].sudo().with_context(ems_bypass_grade_guard=True)
        for line in self.line_ids.filtered(lambda line: line.state == 'granted'):
            student = line.student_id.sudo()
            enrollments = Enrollment.search([('student_id', '=', student.id), ('subject_id', '=', line.subject_id.id)])
            groups = enrollments.group_id or student.main_group_id
            teachings = self.env['ems.teaching'].sudo().search([
                ('group_id', 'in', groups.ids), ('subject_id', '=', line.subject_id.id), ('active', '=', True)])
            staff = (teachings.teacher_id | groups.tutor_id).user_id
            enrollments.unlink()
            line.convalidation_id._ems_notify_teaching_staff(line, staff)

    def _ems_notify_teaching_staff(self, line, users):
        """A to-do on the student for each teacher of the convalidated subject and the group's
        tutor, the only notice they get: teachers cannot open convalidation requests, but they
        can open the student. Nobody is left following the student because of it."""
        self.ensure_one()
        users = users.filtered(lambda user: user.active and user.id != SUPERUSER_ID)
        if not users:
            return
        student = line.student_id.sudo().with_context(mail_activity_quick_update=True)
        followers = student.message_partner_ids
        note = Markup("<p>{}</p>").format(
            _("%(student)s no longer takes %(subject)s: it has been convalidated with a %(grade)s "
              "(registration %(number)s). They are no longer in its attendance lists or grades.") % {
                'student': student.name, 'subject': line.subject_id.display_name,
                'grade': line.grade, 'number': self.name,
            })
        for user in users:
            student.activity_schedule(
                act_type_xmlid='ems.mail_activity_convalidation_notice',
                summary=_("Convalidated: %s") % line.subject_id.display_name,
                note=note, user_id=user.id)
        newcomers = users.partner_id - followers
        if newcomers:
            student.message_unsubscribe(partner_ids=newcomers.ids)

    def action_reject(self):
        """Reject the whole request: the Head of Studies while it is pending, the secretariat
        once it has been validated."""
        for convalidation in self:
            if convalidation.state == 'pending':
                convalidation._ems_check_head_of_studies()
            elif convalidation.state == 'in_progress':
                convalidation._ems_check_secretary()
            else:
                convalidation._ems_check_state(('pending', 'in_progress'))
        self.line_ids.filtered(lambda line: line.state != 'rejected').sudo().write({'state': 'rejected'})
        self._ems_reject()

    def _ems_reject(self):
        """Close the requests as rejected and notify their outcome."""
        if not self:
            return
        self.sudo().write({'state': 'rejected'})
        self._ems_stamp_resolution()
        self._ems_close_tasks()
        for convalidation in self:
            convalidation._ems_send_resolution()

    def action_request_info(self):
        """Ask the student (or the family) for more documentation, by email and on the portal."""
        self.ensure_one()
        self._ems_check_state(('pending', 'in_progress'))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Request information"),
            'res_model': 'ems.convalidation.info_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_convalidation_id': self.id},
        }

    # --- portal helpers ------------------------------------------------------

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
            ('convalidation_id.state', '!=', 'cancelled'),
            ('state', '!=', 'rejected'),
        ]).mapped('subject_id')
        return study._ems_convalidable_subjects() - taken

    def _ems_portal_add_documents(self, attachments, message):
        """A reply from the portal: the files land in the request's own documents, and the text
        in the chatter, where the Head of Studies reads it."""
        self.ensure_one()
        if attachments:
            self.sudo().attachment_ids = [(4, attachment.id) for attachment in attachments]
        body = Markup("<p>{}</p>{}").format(
            message or _("New documentation attached."),
            self.env['ems.base'].build_html_list(attachments.mapped('name')) if attachments else Markup(""))
        self._ems_post_communication(_("Documentation added by the applicant"), body)


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
    request_state = fields.Selection(related='convalidation_id.state', string="Request state")
    subject_id = fields.Many2one(string="Subject", comodel_name='ems.subject', required=True, ondelete='restrict')
    state = fields.Selection(string="Resolution", required=True, default='pending', selection=[
        ('pending', 'Pending'),
        ('granted', 'Convalidated'),
        ('rejected', 'Rejected'),
    ])
    grade = fields.Integer(string="Grade", default=CONVALIDATED_GRADE,
                           help="Grade the convalidated subject is recorded with. It only reaches the "
                                "student's grades once the secretariat completes the request.")
    resolution_notes = fields.Char(string="Remarks",
                                   help="Where the resolution comes from, e.g. \"Granted by the Department, "
                                        "file no. 1234\". Shown to the student with the resolution.")

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

    @api.constrains('grade')
    def _check_grade(self):
        for line in self:
            if not CONVALIDATED_GRADE <= line.grade <= 10:
                raise ValidationError(_("A convalidated subject's grade must be between %(min)s and 10.")
                                      % {'min': CONVALIDATED_GRADE})

    @api.model_create_multi
    def create(self, vals_list):
        decided = [vals for vals in vals_list if vals.get('state', 'pending') != 'pending']
        if decided:
            self._ems_check_can_decide()
            self.env['ems.convalidation'].browse(
                [vals['convalidation_id'] for vals in decided if vals.get('convalidation_id')]
            )._ems_check_state(('pending',))
        lines = super().create(vals_list)
        lines._ems_sync_grades()
        return lines

    def write(self, vals):
        if 'state' in vals or 'subject_id' in vals:
            self._ems_check_can_decide()
        elif 'grade' in vals:
            self._ems_check_can_grade()
        else:
            return super().write(vals)
        # A changed subject leaves its previous one to be re-evaluated too.
        previous_pairs, courses = self._ems_grade_keys()
        res = super().write(vals)
        self._ems_sync_grades(previous_pairs, courses)
        return res

    def unlink(self):
        if self.filtered(lambda line: line.state != 'pending'):
            self._ems_check_can_decide()
        pairs, courses = self._ems_grade_keys()
        res = super().unlink()
        self.browse()._ems_sync_grades(pairs, courses)
        return res

    def _ems_check_can_decide(self):
        """Convalidating or rejecting a subject is the Head of Studies' call, and only while the
        request is still theirs: once validated, the resolution is what the secretariat is
        registering in Esfera.

        sudo bypasses both checks: the request's own actions write the lines that way, after
        checking who is acting on the request as a whole. The group check runs on an empty
        recordset too (a line created already resolved has no record to read yet)."""
        if self.env.su:
            return
        self.env['ems.convalidation']._ems_check_head_of_studies()
        for line in self:
            line.convalidation_id._ems_check_state(('pending',))

    def _ems_check_can_grade(self):
        """The Head of Studies grades while resolving; the secretariat can still correct the
        grade against Esfera before completing the request."""
        if self.env.su:
            return
        for line in self:
            convalidation = line.convalidation_id
            if convalidation.state == 'pending':
                convalidation._ems_check_head_of_studies()
            elif convalidation.state == 'in_progress':
                convalidation._ems_check_secretary()
            else:
                convalidation._ems_check_state(('pending', 'in_progress'))

    # --- actions -------------------------------------------------------------

    def action_grant(self):
        self.write({'state': 'granted'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset(self):
        self.write({'state': 'pending'})

    # --- grades sync ---------------------------------------------------------

    @api.model
    def _ems_convalidation_line(self, student, subject):
        """The line 'subject' is convalidated through for 'student', or an empty recordset: only
        a granted subject of a completed request counts, since the resolution is not official
        until the secretariat has registered it. sudo: grade lines are created by teachers too,
        who cannot read convalidations."""
        return self.sudo().search([
            ('student_id', '=', student.id),
            ('subject_id', '=', subject.id),
            ('state', '=', 'granted'),
            ('convalidation_id.state', '=', 'completed'),
        ], limit=1)

    @api.model
    def _ems_convalidation_grade(self, student, subject):
        """The grade 'subject' is convalidated with for 'student', or None when it is not."""
        line = self._ems_convalidation_line(student, subject)
        return line.grade if line else None

    @api.model
    def _ems_is_convalidated(self, student, subject):
        """Whether 'subject' is convalidated for 'student'."""
        return self._ems_convalidation_grade(student, subject) is not None

    def _ems_grade_keys(self):
        """The (student, subject) pairs and the courses these lines touch, read before a change
        that may make the lines themselves unreadable (an unlink)."""
        return {(line.student_id, line.subject_id) for line in self}, self.mapped('course_id')

    def _ems_sync_grades(self, extra_pairs=(), extra_courses=None):
        """Mirror each affected (student, subject)'s convalidation onto its grades: every live
        grade line, and the subject in the year record of the request's course when that
        history has already been frozen (a resolution can arrive after the year is closed)."""
        pairs, courses = self._ems_grade_keys()
        pairs |= set(extra_pairs)
        courses |= extra_courses or self.env['ems.course']
        GradeLine = self.env['ems.grade_subject_line'].sudo().with_context(ems_convalidation_sync=True)
        SubjectRecord = self.env['ems.student.year_record.subject'].sudo()
        YearRecord = self.env['ems.student.year_record'].sudo()
        for student, subject in pairs:
            line = self._ems_convalidation_line(student, subject)
            grade = line.grade if line else None
            convalidated = grade is not None
            GradeLine.search([
                ('student_id', '=', student.id),
                ('grade_session_id.subject_id', '=', subject.id),
                '|', ('is_convalidated', '!=', convalidated),
                ('convalidation_grade', '!=', grade or 0),
            ]).write({'is_convalidated': convalidated, 'convalidation_grade': grade or 0})
            changed = SubjectRecord.search([
                ('record_id.student_id', '=', student.id),
                ('record_id.course_id', 'in', courses.ids),
                ('subject_id', '=', subject.id),
                '|', ('is_convalidated', '!=', convalidated),
                ('convalidation_grade', '!=', grade or 0),
            ])
            # Revoked on a course still running: the subject was only there because of the
            # convalidation, so it goes (and the record with it once nothing is left).
            dropped = changed.filtered(lambda record: record.record_id.is_provisional and not convalidated)
            if dropped:
                records = dropped.record_id
                dropped.unlink()
                records.filtered(lambda record: not record.subject_record_ids).unlink()
            (changed - dropped)._ems_set_convalidated(
                convalidated, grade or CONVALIDATED_GRADE, line.convalidation_id)
            # The convalidation's own course records the subject, whether its history is frozen
            # already (the student was withdrawn before any round was graded) or not generated
            # yet: then a provisional record is opened, so the grade shows in the history - the
            # one place teachers look it up - from the day the request is completed.
            if convalidated:
                year_records = YearRecord.search([('student_id', '=', student.id),
                                                  ('course_id', '=', line.course_id.id)]) \
                    or YearRecord._ems_provisional_record(student, line.course_id, line.convalidation_id.study_id)
                for year_record in year_records:
                    if subject not in year_record.subject_record_ids.subject_id:
                        year_record.subject_record_ids = [
                            (0, 0, SubjectRecord._convalidated_vals(line, year_record.study_id))]
