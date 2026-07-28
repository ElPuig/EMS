# -*- coding: utf-8 -*-
from markupsafe import Markup, escape
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class EmsStudentDocument(models.Model):
    _name = 'ems.student.document'
    _description = 'Student document submission'
    _order = 'upload_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    doc_type = fields.Selection([
        ('dni',      'DNI / NIE'),
        ('passport', 'Passport'),
        ('medical',  'Medical card (TIS)'),
        ('iban',     'Bank account (IBAN)'),
        ('benefit',  'Bonification / Exemption'),
        ('google_credentials', 'Google Workspace credentials'),
        ('other',    'Other'),
    ], required=True, string='Document type')

    # Text data — only meaningful for doc_type == 'iban'
    doc_value  = fields.Char(string='IBAN')
    doc_value2 = fields.Char(string='Account holder')

    # Benefit type — only meaningful for doc_type == 'benefit'
    benefit_type = fields.Char(string='Benefit type')

    expiry_date = fields.Date(string='Expiry date')

    # File data — for physical document scans
    doc_file      = fields.Binary(string='File', attachment=True)
    doc_file_name = fields.Char()
    doc_file_link = fields.Html(string='File link', compute='_compute_doc_file_link', sanitize=False)

    status = fields.Selection([
        ('pending',   'Pending review'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('cancelled', 'Cancelled'),
    ], default='pending', required=True, index=True, string='Status', tracking=True)

    upload_date      = fields.Datetime(default=fields.Datetime.now, readonly=True)
    review_date      = fields.Datetime(readonly=True)
    review_uid       = fields.Many2one('res.users', string='Reviewed by', readonly=True)
    rejection_reason = fields.Char(string='Rejection reason')

    def _doc_label(self):
        """Human-readable label for this document's doc_type, in the current language."""
        self.ensure_one()
        return dict(self._fields['doc_type'].selection).get(self.doc_type, self.doc_type or '')

    @api.depends('doc_type', 'partner_id', 'benefit_type')
    def _compute_name(self):
        for document in self:
            doc_label = document._doc_label()
            if document.doc_type == 'benefit' and document.benefit_type:
                benefit_labels = dict(self.env['ems.student.benefit']._fields['benefit_type'].selection)
                benefit_label = benefit_labels.get(document.benefit_type, document.benefit_type)
                doc_label = f'{doc_label} – {benefit_label}'
            student = document.partner_id.name or ''
            document.name = f'Document Submission: {doc_label} – {student}'

    @api.depends('doc_file', 'doc_file_name')
    def _compute_doc_file_link(self):
        Attachment = self.env['ir.attachment'].sudo()
        for document in self:
            if not document.doc_file or not document.doc_file_name:
                document.doc_file_link = ''
                continue
            attachment = Attachment.search([
                ('res_model', '=', self._name),
                ('res_field', '=', 'doc_file'),
                ('res_id', '=', document.id),
            ], limit=1)
            if attachment:
                url = f'/web/content/{attachment.id}?download=false'
                document.doc_file_link = Markup(f'<a href="{url}" target="_blank">{escape(document.doc_file_name)}</a>')
            else:
                document.doc_file_link = escape(document.doc_file_name)

    @api.constrains('partner_id', 'doc_type', 'status')
    def _check_single_pending_iban(self):
        for document in self:
            if document.doc_type == 'iban' and document.status == 'pending':
                duplicates = self.search([
                    ('partner_id', '=', document.partner_id.id),
                    ('doc_type', '=', 'iban'),
                    ('status', '=', 'pending'),
                    ('id', '!=', document.id),
                ])
                if duplicates:
                    raise ValidationError(_("There is already a pending IBAN submission for this student."))

    def _schedule_review_activities(self):
        """Schedule a 'to-do' review activity for each configured reviewer.

        Recipients come from Academic Management > Configuration > Task Assignment,
        not from a security group: who reviews documents is a matter of
        organisation, not of access rights.

        ``mail_activity_quick_update`` suppresses the assignation email Odoo sends to
        every assignee on mail.activity.create() ("X has assigned you the following
        activity"). The task in the systray is the reviewer's notice — and the author
        of that email would be whoever created the document, i.e. the family writing
        from the portal, which reads as if a family were assigning work to the office.
        """
        users = self.env['mail.activity.type']._ems_get_task_users(
            'ems.mail_activity_student_document_review')
        for document in self:
            doc_label = document._doc_label()
            for user in users:
                document.with_context(mail_activity_quick_update=True).activity_schedule(
                    act_type_xmlid='ems.mail_activity_student_document_review',
                    summary=_('Review document: %s') % doc_label,
                    user_id=user.id,
                )
        # Scheduling an activity auto-subscribes the assignee, which would email the
        # reviewers every status change on top of their to-do. The task is their only
        # notice (same rule as enrollment comments), so keep them out of the followers.
        self._unsubscribe_reviewers(users)

    def _unsubscribe_reviewers(self, users):
        """Keep the task recipients out of the followers (their to-do is the notice)."""
        partner_ids = users.mapped('partner_id').ids
        if partner_ids:
            for document in self:
                document.message_unsubscribe(partner_ids=partner_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for document in records:
            # Only the student follows the document: they are the one who must hear
            # back about it by email. Reviewers get a task instead (see
            # _schedule_review_activities).
            document.message_subscribe(partner_ids=[document.partner_id.id])

            if document.status == 'pending':
                # Internal log note — does NOT email followers (the reviewer is
                # notified via the review activity instead, avoiding a duplicate email)
                document.message_post(
                    body=Markup(
                        f"<b>{_('Document submitted for review:')}</b> {escape(document._doc_label())}"
                        f"<br/>{_('Student:')} {escape(document.partner_id.name)}"
                    ),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

        # Only schedule review activities for documents that actually need review
        pending_records = records.filtered(lambda r: r.status == 'pending')
        pending_records._schedule_review_activities()
        return records

    def action_approve(self):
        for document in self:
            # Remove previously approved document of the same type for this student
            # For benefit documents, also match benefit_type to avoid removing other benefit types
            domain = [
                ('partner_id', '=', document.partner_id.id),
                ('doc_type', '=', document.doc_type),
                ('status', '=', 'approved'),
                ('id', '!=', document.id),
            ]
            if document.doc_type == 'benefit' and document.benefit_type:
                domain.append(('benefit_type', '=', document.benefit_type))
            self.search(domain).unlink()

            document.write({
                'status': 'approved',
                'review_date': fields.Datetime.now(),
                'review_uid': self.env.user.id,
            })
            if document.doc_type == 'iban' and document.doc_value:
                document._apply_bank_account()
            elif document.doc_type == 'benefit' and document.benefit_type:
                document._apply_benefit()

            document.activity_ids.unlink()

            document.message_post(
                body=Markup(
                    f"<b>{_('Document approved:')}</b> {escape(document._doc_label())}"
                    f"<br/>{_('Student:')} {escape(document.partner_id.name)}"
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def action_reject(self):
        for document in self:
            document.write({
                'status': 'rejected',
                'review_date': fields.Datetime.now(),
                'review_uid': self.env.user.id,
            })
            document.activity_ids.unlink()

            body = Markup(
                f"<b>{_('Document rejected:')}</b> {escape(document._doc_label())}"
                f"<br/>{_('Student:')} {escape(document.partner_id.name)}"
            )
            if document.rejection_reason:
                body += Markup(f"<br/>{_('Reason:')} {escape(document.rejection_reason)}")
            document.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def action_cancel(self):
        for document in self:
            document.write({'status': 'cancelled'})
            document.activity_ids.unlink()

            document.message_post(
                body=Markup(
                    f"<b>{_('Document submission cancelled:')}</b> {escape(document._doc_label())}"
                    f"<br/>{_('Student:')} {escape(document.partner_id.name)}"
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def action_reset_to_pending(self):
        for document in self:
            # Drop any leftover activities and reschedule a fresh review task
            document.activity_ids.unlink()
            document.write({
                'status': 'pending',
                'review_uid': False,
                'review_date': False,
                'rejection_reason': False,
            })
            document._schedule_review_activities()

            # Internal log note — does NOT email followers (the secretary is
            # notified via the review activity instead, avoiding a duplicate email)
            document.message_post(
                body=Markup(
                    f"<b>{_('Document reopened for review:')}</b> {escape(document._doc_label())}"
                    f"<br/>{_('Student:')} {escape(document.partner_id.name)}"
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def _apply_benefit(self):
        self.ensure_one()
        BenefitModel = self.env['ems.student.benefit']
        # Remove existing approved benefit of the same type for this student
        BenefitModel.search([
            ('student_id', '=', self.partner_id.id),
            ('benefit_type', '=', self.benefit_type),
        ]).unlink()
        # Compute renewal_date using the model's onchange logic
        virtual = BenefitModel.new({'benefit_type': self.benefit_type})
        virtual._onchange_benefit_type()
        BenefitModel.create({
            'student_id': self.partner_id.id,
            'benefit_type': self.benefit_type,
            'document': self.doc_file,
            'document_name': self.doc_file_name,
            'renewal_date': virtual.renewal_date,
        })

    def _apply_bank_account(self):
        self.ensure_one()
        student = self.partner_id
        iban = self.doc_value.strip().upper()
        holder = self.doc_value2 or False
        BankAccount = self.env['res.partner.bank'].with_context(active_test=False)
        existing = BankAccount.search([
            ('partner_id', '=', student.id),
            ('acc_number', '=', iban),
        ], limit=1)
        # allow_out_payment: the secretary has just validated the IBAN, so mark
        # the account as trusted — otherwise posting a direct-debit invoice
        # that references it is blocked (or the bank data silently dropped).
        if existing:
            existing.write({
                'active': True,
                'acc_holder_name': holder,
                'allow_out_payment': True,
            })
            BankAccount.search([
                ('partner_id', '=', student.id),
                ('id', '!=', existing.id),
            ]).write({'active': False})
        else:
            BankAccount.search([('partner_id', '=', student.id)]).write({'active': False})
            self.env['res.partner.bank'].create({
                'acc_number': iban,
                'partner_id': student.id,
                'acc_holder_name': holder,
                'allow_out_payment': True,
            })
