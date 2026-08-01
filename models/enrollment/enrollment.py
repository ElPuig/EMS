# -*- coding: utf-8 -*-
from datetime import date

from psycopg2 import IntegrityError

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.mail.tools.discuss import Store

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def init(self):
        """Partial unique index backstopping _check_unique_enrollment_per_course at the DB
        level - a plain _sql_constraints unique can't express "unique except when
        cancelled" (see plans/enrollment_header_unique_race_condition.md, now resolved).
        Mirrors the Python constraint's own skip conditions (cancelled / no partner / no
        course) exactly, so it only ever fires for the same cases the Python check does.
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS sale_order_unique_enrollment_per_course
            ON sale_order (partner_id, ems_course_id)
            WHERE state != 'cancel' AND partner_id IS NOT NULL AND ems_course_id IS NOT NULL
        """)

    def _get_default_course(self):
        """
        Logic to auto-select the academic year:
        1. Look for the course marked as 'Enrollment Default' (e.g., 2026/27).
        2. If not found, fallback to 'Current' (e.g., 2025/26).
        """
        course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)
        if not course:
            course = self.env['ems.course'].search([('is_current', '=', True)], limit=1)
        return course.id if course else False

    ems_enrollment_number = fields.Char(string="Enrollment Number", copy=False, readonly=True)
    # Auxiliary field for the view's product-line domain filter.
    ems_existing_product_ids = fields.Many2many(
        'product.template',
        compute='_compute_existing_products',
        string="Enrolled Products (Technical)"
    )

    ems_course_id = fields.Many2one(
        'ems.course',
        string="Academic Year",
        # Not required at the model level: made required at the view level instead.
        default=_get_default_course,
        help="Academic year for this enrollment."
    )

    # Study selected for this enrollment.
    ems_study_id = fields.Many2one(
        'ems.study',
        string="Studies for enrollment"
        # Not required at the model level: made required at the view level instead.
    )

    # Study level, derived automatically from ems_study_id.
    ems_level_id = fields.Many2one(
        comodel_name="ems.level",
        string="Level",
        related="ems_study_id.level_id",
        store=True  # Needed to group/filter by level in the list view.
    )

    # Shift (Turno) ---
    shift = fields.Selection(
        selection=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
        ],
        string="Shift",
        #required=True,
        #default='morning',
        help="Morning or afternoon shift for this enrollment."
    )

    # Destination group: the single source of truth for group placement. Optional
    # (never blocks confirmation); there is no equivalent field on res.partner.
    # The domain only restricts by study (a student may switch shift); a shift/course
    # mismatch is surfaced as a soft warning instead of being blocked.
    ems_group_id = fields.Many2one(
        'ems.group',
        string="Destination group",
        copy=False,
        domain="[('study_id', '=', ems_study_id)]",
        help="Group the student will be placed in: in bulk when the destination "
             "study is transitioned, or individually when a latecomer confirms "
             "after that transition. Left empty until known."
    )

    # Native 'sale_order_template_id' field, re-domained: only offer templates
    # (enrollment packs) belonging to the study selected above.
    sale_order_template_id = fields.Many2one(
        comodel_name='sale.order.template', 
        domain="[('ems_study_id', '=', ems_study_id)]"
    )

    ems_authorization_ids = fields.One2many(
        comodel_name='ems.authorization',
        inverse_name='enrollment_id',
        string="Authorizations"
    )

    ems_payment_method = fields.Selection([
        ('transfer',     'Bank Transfer'),
        ('direct_debit', 'Direct Debit'),
    ], string='Payment Method')

    ems_has_fees = fields.Boolean(
        compute='_compute_fee_amounts', store=True,
        string='Has Fee Products',
    )
    ems_fee_amount = fields.Monetary(
        compute='_compute_fee_amounts', store=True,
        string='Fee Amount',
    )
    ems_non_fee_amount = fields.Monetary(
        compute='_compute_fee_amounts', store=True,
        string='Non-fee Amount',
    )
    ems_first_installment = fields.Monetary(
        compute='_compute_installments',
        string='First Installment',
    )
    ems_second_installment = fields.Monetary(
        compute='_compute_installments',
        string='Second Installment',
    )

    @api.depends('order_line.price_subtotal', 'order_line.product_template_id.ems_is_enrollment_fee')
    def _compute_fee_amounts(self):
        for order in self:
            fee = sum(
                l.price_subtotal for l in order.order_line
                if l.product_template_id.ems_is_enrollment_fee
            )
            non_fee = sum(
                l.price_subtotal for l in order.order_line
                if not l.product_template_id.ems_is_enrollment_fee
            )
            order.ems_fee_amount = fee
            order.ems_non_fee_amount = non_fee
            order.ems_has_fees = fee > 0

    @api.depends('ems_fee_amount', 'ems_non_fee_amount')
    def _compute_installments(self):
        for order in self:
            order.ems_first_installment = order.ems_non_fee_amount + order.ems_fee_amount * 0.5
            order.ems_second_installment = order.ems_fee_amount * 0.5

    ems_enrollment_status_label = fields.Char(
        string='Enrollment Status',
        compute='_compute_enrollment_status_label',
        store=False,
    )    

    @api.depends('state')
    def _compute_enrollment_status_label(self):
        labels = {
            'draft': 'Pre-enrollment',
            'sent': 'Sent to student',
            'sale': 'Confirmed',
            'cancel': 'Cancelled',
            'done': 'Locked',
        }
        for order in self:
            order.ems_enrollment_status_label = labels.get(order.state, order.state)

    def _get_dynamic_enrollment_name(self):
        """Build the enrollment code dynamically using acronyms and shortening the year."""
        self.ensure_one()

        # 1. Shorten the academic year ("2025-2026" -> "25-26").
        course_str = 'XXXX'
        if self.ems_course_id and self.ems_course_id.name:
            full_course = self.ems_course_id.name.strip()
            # Exact 9-character format like "2025-2026" or "2025/2026"?
            if len(full_course) == 9 and full_course[4] in ('-', '/'):
                # Take the digits at positions 2:4 (25) and 7:9 (26).
                course_str = f"{full_course[2:4]}-{full_course[7:9]}"
            else:
                # Unexpected format (e.g. just "2025"): keep it as-is, safely.
                course_str = full_course
        # 2. Level and study acronyms.
        level_str = self.ems_level_id.acronym if self.ems_level_id and self.ems_level_id.acronym else 'XXX'
        study_str = self.ems_study_id.acronym if self.ems_study_id and self.ems_study_id.acronym else 'XXX'
        # 3. Sequence number.
        num_str = self.ems_enrollment_number or 'New'
        # 4. Build and clean the final string.
        return f"M/{course_str}/{level_str}/{study_str}/{num_str}".replace(' ', '')

    @api.onchange('ems_course_id', 'ems_level_id', 'ems_study_id')
    def _onchange_enrollment_name_preview(self):
        """Update the enrollment code in real time on the screen before saving."""
        for order in self:
            # Only preview it in draft/sent state, for an actual enrollment.
            if order.state in ['draft', 'sent'] and order.ems_study_id:
                order.name = order._get_dynamic_enrollment_name()

    def _translate_enrollment_race_error(self, error):
        """Re-raise a friendly ValidationError for the partial unique index created in
        init() - a genuine cross-transaction race that slipped past
        _check_unique_enrollment_per_course's own search()-then-raise check. Any other
        IntegrityError is re-raised unchanged."""
        if 'sale_order_unique_enrollment_per_course' not in str(error):
            raise error
        raise ValidationError(_(
            "This student already has a pre-enrolment or active enrolment for this "
            "academic year. Someone else may have just created one — please refresh "
            "and check.")) from error

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Clear the salesperson so the company appears as fallback in communications.
            vals['user_id'] = False
            # Is this an enrollment (i.e. did the user pick a study)?
            if vals.get('ems_study_id'):
                # 1. Ask the sequence for the next enrollment number (e.g. 0004).
                vals['ems_enrollment_number'] = self.env['ir.sequence'].next_by_code('ems.enrollment.number') or '0000'
                # 2. Override 'name'. Setting it to anything other than 'New' blocks
                #    Odoo from assigning the default sale-order sequence (S0000X).
                vals['name'] = 'Generating...'
        # 3. Call the native method to persist the records. Since 'name' is
        #    'Generating...', Odoo will not apply the S0000X sequence.
        try:
            records = super(SaleOrder, self).create(vals_list)
        except IntegrityError as e:
            self._translate_enrollment_race_error(e)
        # 4. The records now exist and have their enrollment number saved:
        #    build the final name.
        for order in records:
            if order.ems_study_id and order.ems_enrollment_number:
                order.name = order._get_dynamic_enrollment_name()
        return records

    def write(self, vals):
        """Refresh the enrollment code if the user changes their mind after saving."""
        # Detect the draft -> sent transition for enrollments: once the secretary
        # sends the proposal to the students, the tutor's job is done.
        handover_orders = self.env['sale.order']
        if vals.get('state') == 'sent':
            handover_orders = self.filtered(
                lambda o: o.ems_study_id and o.state != 'sent'
            )

        try:
            res = super(SaleOrder, self).write(vals)
        except IntegrityError as e:
            self._translate_enrollment_race_error(e)

        if handover_orders:
            handover_orders._ems_unfollow_teachers()

        if vals.get('ems_group_id'):
            self._ems_place_on_group_assignment()

        # If one of the fields that make up the code was changed...
        if any(field in vals for field in ['ems_course_id', 'ems_level_id', 'ems_study_id']):
            for order in self:
                # ...and it is still in an editable state...
                if order.state in ['draft', 'sent'] and order.ems_enrollment_number:
                    new_name = order._get_dynamic_enrollment_name()
                    # Update the code if it changed.
                    if order.name != new_name:
                        order.name = new_name
        return res

    # ------------------------------------------------------------------
    # Secretary handover (issue #270)
    # ------------------------------------------------------------------
    def _ems_unfollow_teachers(self):
        """Stop notifying teachers once the enrollment has been sent to students.

        Their job is done; from now on the secretary follows up through review
        activities (not as followers — see _ems_schedule_comment_review_activities)."""
        teachers = (
            self.env.ref('ems.group_teacher').users
            - self.env.ref('ems.group_secretary').users
            - self.env.ref('ems.group_academic_admin').users
        )
        teacher_partner_ids = teachers.mapped('partner_id').ids
        if teacher_partner_ids:
            for order in self:
                order.message_unsubscribe(partner_ids=teacher_partner_ids)

    def _ems_schedule_comment_review_activities(self):
        """Schedule a review to-do for each configured reviewer when a student/family
        comments from the portal. The activity shows up in their systray and in
        "view all activities". Skips orders that already have a pending one so
        repeated comments don't pile up tasks.

        Recipients come from Academic Management > Configuration > Task Assignment,
        not from a security group: who handles enrollments is a matter of
        organisation, not of access rights.

        No email is sent to the reviewers: the systray task is their only
        notice. We use ``mail_activity_quick_update`` to skip the assignment
        email, and unsubscribe them afterwards because scheduling an activity
        auto-subscribes the assignee (which would forward them the comments)."""
        comment_type = self.env.ref('ems.mail_activity_enrollment_comment')
        reviewers = comment_type._ems_task_users()
        reviewer_partner_ids = reviewers.mapped('partner_id').ids
        for order in self:
            pending = order.activity_ids.filtered(
                lambda a: a.activity_type_id == comment_type
            )
            if not pending:
                for user in reviewers:
                    order.with_context(mail_activity_quick_update=True).activity_schedule(
                        act_type_xmlid='ems.mail_activity_enrollment_comment',
                        summary=_('Review enrollment comment: %(name)s', name=order.name),
                        user_id=user.id,
                    )
            # Always keep reviewers out of the followers (activity creation
            # auto-subscribes the assignee), so the comment doesn't email them.
            if reviewer_partner_ids:
                order.message_unsubscribe(partner_ids=reviewer_partner_ids)

    def _thread_to_store(self, store, /, *, fields=None, request_list=None):
        """In the chatter, show each user only their OWN enrollment-comment
        review activity. We create one per secretary (for the systray), but they
        are duplicates of the same task; this only affects activities, messages
        and everything else are served unchanged for everyone."""
        if request_list and "activities" in request_list:
            reduced = [r for r in request_list if r != "activities"]
            super()._thread_to_store(store, fields=fields, request_list=reduced)
            comment_type = self.env.ref(
                'ems.mail_activity_enrollment_comment', raise_if_not_found=False
            )
            for thread in self:
                acts = thread.with_context(active_test=True).activity_ids
                if comment_type:
                    acts = acts.filtered(
                        lambda a: a.activity_type_id != comment_type
                        or a.user_id == self.env.user
                    )
                store.add(thread, {"activities": Store.many(acts)}, as_thread=True)
        else:
            super()._thread_to_store(store, fields=fields, request_list=request_list)

    # Clear the template if the user changes the study, to avoid mismatches.
    @api.onchange('ems_study_id')
    def _onchange_ems_study_id(self):
        self.sale_order_template_id = False
        self.with_context(skip_tutoria_check=True).order_line = [(5, 0, 0)]
        # Drop a destination group that no longer belongs to the selected study.
        if self.ems_group_id and self.ems_group_id.study_id != self.ems_study_id:
            self.ems_group_id = False

    @api.onchange('ems_group_id')
    def _onchange_ems_group_id(self):
        """Soft warning when the chosen group's shift or course does not match the
        enrollment/template (the domain only enforces the study)."""
        group = self.ems_group_id
        if not group:
            return
        issues = []
        if self.shift and group.shift and group.shift != self.shift:
            issues.append(_("The group shift does not match the enrollment shift."))
        template_year = self.sale_order_template_id.study_year
        if template_year and group.course != template_year:
            issues.append(_(
                "The group course (%(group)s) does not match the enrollment "
                "template course (%(template)s).",
                group=group.course, template=template_year))
        if issues:
            return {'warning': {
                'title': _("Destination group mismatch"),
                'message': "\n".join(issues),
            }}

    @api.depends('order_line.product_template_id')
    def _compute_existing_products(self):
        for order in self:
            valid_lines = order.order_line.filtered(lambda l: l.product_template_id)
            order.ems_existing_product_ids = valid_lines.mapped('product_template_id')
    
    @api.onchange('ems_level_id', 'ems_study_id')
    def _onchange_ems_level_study_for_authorizations(self):
        """Autofills authorizations based on the selected Level and Study."""
        for order in self:
            order.ems_authorization_ids = order._get_authorization_commands()

    def _get_authorization_commands(self):
        """Return the ORM commands to sync authorizations with the current
        level/study selection (AND-of-scopes, see
        ems.authorization.template._matches_scope())."""
        self.ensure_one()
        templates = self.env['ems.authorization.template'].search([]).filtered(
            lambda template: template._matches_scope(self.ems_level_id, self.ems_study_id))
        commands = []
        to_remove = self.ems_authorization_ids.filtered(
            lambda a: a.template_id not in templates
        )
        for auth in to_remove:
            commands.append((2, auth.id, 0))
        for template in templates:
            existing = self.ems_authorization_ids.filtered(
                lambda a: a.template_id == template
            )
            if not existing:
                commands.append((0, 0, {
                    'template_id': template.id,
                    'status': 'pending',
                }))
        return commands

    def apply_authorizations(self):
        """Apply authorizations, persisting them to the database. Callable from code."""
        for order in self:
            commands = order._get_authorization_commands()
            if commands:
                order.write({'ems_authorization_ids': commands})

    @api.constrains('partner_id', 'ems_course_id', 'state')
    def _check_unique_enrollment_per_course(self):
        """
        Prevents the same student (partner_id) from having more than one active enrollment
        (that has not been cancelled) in the same academic year (ems_course_id).
        """
        for order in self:
            # Ignore the current record if it is cancelled or has no student/course.
            if order.state == 'cancel' or not order.partner_id or not order.ems_course_id:
                continue

            # Look for another, non-cancelled order for the same student and course.
            domain = [
                ('id', '!=', order.id),  # Exclude the current record.
                ('partner_id', '=', order.partner_id.id),
                ('ems_course_id', '=', order.ems_course_id.id),
                ('state', '!=', 'cancel')
            ]

            existing_enrollment = self.search(domain, limit=1)

            if existing_enrollment:
                raise ValidationError(_(
                    "The student %(student)s already has a pre-enrolment or "
                    "active enrolment for the academic year %(course)s.",
                    student=order.partner_id.name, course=order.ems_course_id.display_name,
                ))

    @api.constrains('ems_group_id', 'ems_study_id')
    def _check_group_matches_study(self):
        """ems_group_id.study_id must match ems_study_id - a destination group always
        implies a study, both by the view (ems_study_id required="1") and by every real
        writer of ems_group_id (ems.enrollment_proposal_wizard.action_create_enrollments
        always sets both together; _ems_suggest_group refuses to suggest a group at all
        while ems_study_id is empty). The onchanges (above) only enforce this client-side;
        a direct write (e.g. a tutor editing the form directly instead of going through
        the wizard) needs the same guard server-side. See
        plans/enrollment_header_tutor_guard_gap.md."""
        for order in self:
            if order.ems_group_id and order.ems_group_id.study_id != order.ems_study_id:
                raise ValidationError(_(
                    "The destination group %(group)s does not belong to the "
                    "study selected for this enrollment.",
                    group=order.ems_group_id.display_name,
                ))

    def _is_blocked_tutor(self):
        """True for a plain teacher (blocked outright), and for a tutor who isn't
        genuinely *this* order's own tutor - checked via has_access('write') rather
        than re-deriving rule_sale_order_tutor's own condition in Python, so this
        never drifts out of sync with security/rules/contacts.xml (the same class of
        duplication bug fixed for ems.authorization.template's matching semantics).
        Gives both cases the same friendly ValidationError instead of a bare
        AccessError for the wrong-student-tutor case. See
        plans/enrollment_header_tutor_guard_gap.md (now resolved).
        """
        if not self.env.user.has_group('ems.group_teacher'):
            return False
        if self.env.user.has_group('ems.group_academic_admin') \
                or self.env.user.has_group('ems.group_secretary'):
            return False
        if self.env.user.has_group('ems.group_tutor'):
            return not self.has_access('write')
        return True

    def action_cancel(self):
        if self._is_blocked_tutor():
            raise ValidationError(_(
                "Tutors cannot cancel enrollments. "
                "Please contact the secretary or admin."))
        return super().action_cancel()

    def action_quotation_sent(self):
        if self._is_blocked_tutor():
            raise ValidationError(_(
                "Tutors cannot change the enrollment status. "
                "Please contact the secretary or admin."))
        return super().action_quotation_sent()

    def action_quotation_send(self):
        if self._is_blocked_tutor():
            raise ValidationError(_(
                "Tutors cannot send enrollments to students. "
                "Please contact the secretary or admin."))
        if self.ems_study_id:
            template = self.env.ref('ems.email_template_enrollment_send', raise_if_not_found=False)
            if template:
                action = super().action_quotation_send()
                action['context']['default_template_id'] = template.id
                return action
        return super().action_quotation_send()

    def action_send_enrollment_proposal(self):
        """One-click bulk action for the Matricules list: email the enrollment
        proposal (``email_template_enrollment_send``) to the selected
        enrollments and mark the drafts as sent, merging the "Send an email"
        and "Mark Quotation as Sent" steps into a single button."""
        if self._is_blocked_tutor():
            raise ValidationError(_(
                "Tutors cannot send enrollments to students. "
                "Please contact the secretary or admin."))
        template = self.env.ref(
            'ems.email_template_enrollment_send', raise_if_not_found=False)
        if not template:
            raise UserError(_("The enrollment proposal email template is missing."))
        orders = self.filtered(
            lambda order: order.ems_study_id and order.state in ('draft', 'sent'))
        if not orders:
            raise UserError(_("Select draft enrollments to send."))
        for order in orders:
            template.send_mail(order.id, force_send=True)
        orders.filtered(lambda order: order.state == 'draft').action_quotation_sent()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Enrollments sent"),
                'message': _(
                    "%(count)s enrollment(s) emailed and marked as sent.",
                    count=len(orders)),
                'type': 'success',
                'sticky': False,
            },
        }

    def _notify_get_recipients_groups(self, message, model_description, msg_vals=None):
        groups = super()._notify_get_recipients_groups(message, model_description, msg_vals=msg_vals)
        if self.ems_study_id:
            for group in groups:
                group[2]['has_button_access'] = False
        return groups

    def action_confirm(self):
        if self._is_blocked_tutor():
            raise ValidationError(_(
                "Tutors cannot confirm enrollments. "
                "Please contact the secretary or admin."))
        for order in self:
            pending = order.ems_authorization_ids.filtered(
                lambda a: a.status == 'pending' and a.template_id.is_required
            )
            if pending:
                names = '\n'.join('- ' + t for t in pending.mapped('template_id.name'))
                raise ValidationError(_(
                    "Cannot confirm enrollment '%(name)s'. "
                    "The following required authorizations are still pending:\n%(names)s",
                    name=order.name, names=names,
                ))
        res = super().action_confirm()
        comment_type = self.env.ref('ems.mail_activity_enrollment_comment', raise_if_not_found=False)
        for order in self:
            if order.ems_study_id:
                order._ems_admit_student()
                order._ems_generate_enrollment_invoice()
                # The enrollment is settled: drop any pending comment-review tasks.
                if comment_type:
                    stale = order.activity_ids.filtered(
                        lambda a: a.activity_type_id == comment_type
                    )
                    stale.with_context(ems_activity_cascade=True).unlink()
        return res

    # ------------------------------------------------------------------
    # Admission (applicant -> student) and destination placement
    # ------------------------------------------------------------------
    def _ems_admit_student(self):
        """Formal admission act on enrollment confirmation.

        Always converts an applicant into a student, and consumes the GEDAC assignment
        of an internal continuer once the granted study is the one being confirmed.
        Placement (group + subject enrollments) only runs for latecomers whose
        destination study has already been transitioned; in the normal case (study still
        active) the transition wizard places everyone in bulk later.
        """
        self.ensure_one()
        partner = self.partner_id
        # Ex-students come back too: a graduate starting another study, or a returner
        # archived last year. The bulk placement of the transition wizard already
        # covered the three states, and the individual path has to match it or a
        # September confirmation would land on an archived alumni nobody can place.
        if partner.contact_type in ('applicant', 'alumni', 'withdrawal'):
            partner._ems_convert_to_student()
        # Spent assignment: clearing it keeps the "With GEDAC assignment" filter showing
        # only the continuers still pending enrollment. A different study being confirmed
        # (the manual escape hatch) leaves the assignment standing.
        if partner.preinscription_study_id \
                and partner.preinscription_study_id == self.ems_study_id:
            partner.write({
                'preinscription_study_id': False,
                'preinscription_shift': False,
                'preinscription_course': False,
            })
        if self._ems_placement_is_individual():
            self._ems_apply_destination_placement()

    def _ems_placement_is_individual(self):
        """Whether THIS enrollment has to place its student on its own.

        The bulk pass of the transition wizard has already run when either is true:

        - the destination study is 'transitioned' — a partial transition, the wizard
          did that study and the centre is still on the outgoing course; or
        - the enrollment is for the course that is already running. The global flip
          puts every study back to 'active', so after a complete transition — the
          normal end state — 'transitioned' is true for nobody and keying on it alone
          left September unable to place a single latecomer.

        An enrollment for a course that has not started yet is left to the wizard.
        """
        self.ensure_one()
        return self.ems_study_id.transition_state == 'transitioned' \
            or self.ems_course_id == self.env.company.current_course_id

    def _ems_suggest_group(self):
        """Suggest a destination group for this enrollment from its own data.

        Continuing student: the same acronym as the student's current group plus the
        enrollment shift, in the destination study/course. Newcomer: the lowest-letter
        group of the shift. Empty when there is no single match.

        What tells the two apart is whether there is a group to copy the letter FROM,
        not the contact type. Keying it on 'applicant' looked equivalent but stopped
        being true at exactly the wrong moment: confirming the enrollment runs
        _ems_admit_student(), which turns the applicant into a student, so from then on
        a newcomer awaiting the bulk placement fell through both branches and got no
        suggestion at all.
        """
        self.ensure_one()
        study = self.ems_study_id
        course = self.sale_order_template_id.study_year or self._ems_course_from_tutorship()
        if not (study and course):
            return self.env['ems.group']
        Group = self.env['ems.group']
        partner = self.partner_id
        current = partner.main_group_id
        if not current:
            domain = [('study_id', '=', study.id), ('course', '=', course)]
            shift = self.shift or partner.preinscription_shift
            if shift:
                domain.append(('shift', '=', shift))
            return Group.search(domain, order='acronym', limit=1)
        domain = [('study_id', '=', study.id), ('course', '=', course),
                  ('acronym', '=', current.acronym)]
        shift = self.shift or current.shift
        if shift:
            domain.append(('shift', '=', shift))
        matches = Group.search(domain)
        return matches if len(matches) == 1 else Group

    def _ems_course_from_tutorship(self):
        """Destination course of an enrollment that carries no template.

        A repeater re-enrolling only in what they failed never goes through a template,
        so sale_order_template_id.study_year is empty and the suggestion gave up. Their
        lines cannot be matched against a template as a whole either: they mix modules
        pending from an earlier course with the current one, plus the economic items
        (enrollment fee, AMPA), so no template is ever a superset of them.

        The tutorship is the handle. There is exactly one per enrollment and it is
        course-specific ("Tutoria 2n SMX"), so whichever templates sell it pin the
        course down. Anything ambiguous — no tutorship, more than one, or templates
        disagreeing on the year — returns nothing, and the caller leaves the group
        empty rather than guess.
        """
        self.ensure_one()
        tutorships = self.env['ems.subject'].search([
            ('product_id', 'in', self.order_line.mapped('product_id').ids),
            ('is_tutorship', '=', True)])
        if len(tutorships) != 1:
            return False
        years = {
            template.study_year
            for template in self.env['sale.order.template'].search([
                ('ems_study_id', '=', self.ems_study_id.id),
                ('study_year', '!=', False)])
            if tutorships.product_id in template.sale_order_template_line_ids.product_id
        }
        return years.pop() if len(years) == 1 else False

    def _ems_fill_suggested_group(self):
        """Fill ems_group_id with the suggestion on enrollments that have none.
        Returns the number of enrollments updated."""
        filled = 0
        for order in self:
            if order.ems_group_id:
                continue
            group = order._ems_suggest_group()
            if group:
                order.ems_group_id = group
                filled += 1
        return filled

    def _ems_place_on_group_assignment(self):
        """Place a confirmed enrollment whose destination group arrives late.

        The placement used to run only on confirmation and in the wizard's bulk pass,
        so an enrollment confirmed WITHOUT a destination group could never be repaired:
        writing the group did nothing, and action_confirm() refuses to run twice
        ("Some orders are not in a state requiring confirmation"). The student stayed
        with no group, no subject enrollments and no evaluation sessions, recoverable
        only by hand.

        Deliberately narrow: it only fires for a student that has NO group.
        _ems_apply_destination_placement() creates the enrollments of the new group but
        does not remove those of the old one, so re-pointing an already-placed student
        would leave it enrolled in two groups' subjects at once. Moving somebody is a
        different operation and does not belong here.
        """
        for order in self:
            if order.state != 'sale' or not order.ems_group_id:
                continue
            if not order._ems_placement_is_individual():
                continue  # the wizard's bulk pass will place them
            if order.partner_id.main_group_id:
                continue
            order._ems_apply_destination_placement()

    def _ems_apply_destination_placement(self):
        """Place the student in the destination group and materialize the subject
        enrollments from the order lines.

        Idempotent: an existing (student, group, subject) triple is not
        duplicated. Shared by action_confirm (individual latecomers) and the
        transition wizard (bulk). Runs with sudo because ems.enrollment blocks
        manual creation for non-admins and the secretary may be confirming.
        """
        self.ensure_one()
        group = self.ems_group_id
        if not group:
            return
        student = self.partner_id
        # Last chance to record the year that ends: the write below overwrites the origin
        # group, and a student placed by the run of ANOTHER study would otherwise lose it
        # (see ems.student.year_record.freeze_on_leaving). No-op when the history is
        # already there, which is the normal case of a student of the study being run.
        origin_group = student.main_group_id
        if origin_group and origin_group != group:
            self.env['ems.student.year_record'].sudo().freeze_on_leaving(student, origin_group)
        # Study and level travel with the group, they are not derived from it: leaving
        # them behind would keep a student who moves to another study (or an applicant
        # entering one) pointing at the previous one. Written together and only when
        # they differ, so re-running the placement stays a no-op.
        placement = {
            'main_group_id': group.id,
            'study_id': group.study_id.id,
            'level_id': group.level_id.id,
        }
        if any(student[field].id != value for field, value in placement.items()):
            student.sudo().write(placement)
        Enrollment = self.env['ems.enrollment'].sudo()
        subjects = self.env['ems.subject'].sudo().search([
            ('product_id', 'in', self.order_line.product_id.ids)])
        for subject in subjects:
            exists = Enrollment.search_count([
                ('student_id', '=', student.id),
                ('group_id', '=', group.id),
                ('subject_id', '=', subject.id)])
            if not exists:
                Enrollment.create({
                    'student_id': student.id,
                    'group_id': group.id,
                    'subject_id': subject.id,
                })

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------
    def _ems_billing_due_dates(self):
        """(first, second) default collection due dates for this enrollment.

        Default to 15-Jul / 15-Sep of the course start year. They are only a
        marker of the installment and the batch; the real SEPA collection date
        is chosen later, when the bank file is generated.
        """
        self.ensure_one()
        year = self.ems_course_id.start or fields.Date.context_today(self).year
        return date(year, 7, 15), date(year, 9, 15)

    def action_ems_reapply_benefits(self):
        """Apply the student's current benefit status to an already confirmed
        enrollment.

        Confirmed orders are frozen against benefit changes (see
        sale.order.line._ems_benefit_frozen_lines), so a bonification or
        exemption approved after confirmation needs this explicit action:
        cancel the posted (unpaid) invoice, recompute the fee lines with the
        current benefit status and regenerate the invoice, so that order,
        invoice and portal match again.
        """
        for order in self:
            if order.state != 'sale':
                raise ValidationError(_(
                    "Benefits can only be re-applied on a confirmed enrollment."))
            invoices = order.invoice_ids.filtered(
                lambda m: m.move_type == 'out_invoice' and m.state != 'cancel')
            paid = invoices.filtered(
                lambda m: m.amount_total and m.payment_state != 'not_paid')
            if paid:
                raise ValidationError(_(
                    "Invoice %s already has payments registered. "
                    "Issue a credit note manually instead.") % ', '.join(paid.mapped('name')))
            for inv in invoices.sudo():
                if inv.state == 'posted':
                    inv.button_draft()
                inv.button_cancel()
            lines = order.order_line.with_context(ems_reapply_benefits=True)
            lines._compute_price_unit()
            lines._compute_discount()
            order._ems_generate_enrollment_invoice()
            order.message_post(
                body=_("Benefits re-applied by %s: the invoice has been "
                       "regenerated with the student's current benefit status.")
                % self.env.user.name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def _ems_generate_enrollment_invoice(self):
        """Create, date and post the enrollment invoice. Idempotent.

        - Single-payment plan: one invoice due on the first date.
        - Deferred plan (fees split): one invoice with two due dates
          (first installment = non-fee items + 50% fees @ first date;
          second installment = 50% fees @ second date). The split percentage
          is computed PER enrollment from its own amounts.
        - Direct debit: the confirmed student IBAN is stored on the invoice
          (debtor account, ready for SEPA). Transfer: no student IBAN.
        - The enrollment code is referenced via invoice_origin (native) + ref
          + payment_reference, keeping the legal invoice numbering untouched.
        """
        self.ensure_one()
        existing = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state != 'cancel')
        if existing:
            return existing

        order = self.sudo()
        inv = order._create_invoices()[:1]
        if not inv:
            return inv

        today = fields.Date.context_today(self)
        due1, due2 = order._ems_billing_due_dates()
        total = inv.amount_total
        deferred = bool(
            order.payment_term_id
            and len(order.payment_term_id.line_ids) > 1
            and order.ems_second_installment > 0
            and total > 0
        )

        vals = {
            'invoice_date': today,
            'ref': order.name,
            'payment_reference': order.name,
        }
        if deferred:
            pct1 = round(order.ems_first_installment / total * 100.0, 6)
            term = self.env['account.payment.term'].sudo().create({
                'name': 'EMS %s' % order.name,
                'company_id': inv.company_id.id,
                'line_ids': [
                    (0, 0, {'value': 'percent', 'value_amount': pct1,
                            'delay_type': 'days_after', 'nb_days': (due1 - today).days}),
                    (0, 0, {'value': 'percent', 'value_amount': round(100.0 - pct1, 6),
                            'delay_type': 'days_after', 'nb_days': (due2 - today).days}),
                ],
            })
            vals['invoice_payment_term_id'] = term.id
        else:
            vals['invoice_payment_term_id'] = False
            vals['invoice_date_due'] = due1

        if order.ems_payment_method == 'direct_debit':
            bank = order.partner_id.bank_ids[:1]
            if bank:
                # Do not try to self-grant trust here: Odoo's own anti-fraud check
                # (res.partner.bank._user_can_trust()) exists specifically to stop an
                # automated/portal context from trusting a bank account on its own,
                # and silently attempting it anyway (the previous approach) does not
                # reliably work - confirmed against production data, 2026-07-30: 332
                # already-posted invoices ended up with no bank reference at all,
                # because Odoo's own account.move validation strips an untrusted
                # partner_bank_id under sudo/portal contexts regardless. An IBAN must
                # be genuinely approved first (action_approve(), or the portal renewal
                # flow, both of which set allow_out_payment) - see
                # plans/student_document_iban_renewal_allow_out_payment.md.
                if not bank.allow_out_payment:
                    raise ValidationError(_(
                        "Cannot generate a direct-debit invoice for '%(name)s': the "
                        "destination bank account is not approved yet. Approve the "
                        "student's IBAN document before confirming this enrollment.",
                        name=order.name,
                    ))
                vals['partner_bank_id'] = bank.id

        inv.write(vals)
        inv.action_post()
        return inv