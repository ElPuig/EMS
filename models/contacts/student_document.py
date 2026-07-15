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

    @api.depends('doc_type', 'partner_id', 'benefit_type')
    def _compute_name(self):
        for rec in self:
            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, '') if rec.doc_type else ''
            if rec.doc_type == 'benefit' and rec.benefit_type:
                benefit_labels = dict(self.env['ems.student.benefit']._fields['benefit_type'].selection)
                benefit_label = benefit_labels.get(rec.benefit_type, rec.benefit_type)
                doc_label = '%s – %s' % (doc_label, benefit_label)
            student = rec.partner_id.name or ''
            rec.name = 'Document Submission: %s – %s' % (doc_label, student)

    def _compute_doc_file_link(self):
        Attachment = self.env['ir.attachment'].sudo()
        for rec in self:
            if not rec.doc_file or not rec.doc_file_name:
                rec.doc_file_link = ''
                continue
            att = Attachment.search([
                ('res_model', '=', self._name),
                ('res_field', '=', 'doc_file'),
                ('res_id', '=', rec.id),
            ], limit=1)
            if att:
                url = '/web/content/%d?download=false' % att.id
                rec.doc_file_link = Markup('<a href="%s" target="_blank">%s</a>') % (
                    url, escape(rec.doc_file_name)
                )
            else:
                rec.doc_file_link = escape(rec.doc_file_name)

    @api.constrains('partner_id', 'doc_type', 'status')
    def _check_single_pending_iban(self):
        for rec in self:
            if rec.doc_type == 'iban' and rec.status == 'pending':
                duplicates = self.search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('doc_type', '=', 'iban'),
                    ('status', '=', 'pending'),
                    ('id', '!=', rec.id),
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
        for rec in self:
            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, rec.doc_type)
            for user in users:
                rec.with_context(mail_activity_quick_update=True).activity_schedule(
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
            for rec in self:
                rec.message_unsubscribe(partner_ids=partner_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, rec.doc_type)

            # Only the student follows the document: they are the one who must hear
            # back about it by email. Reviewers get a task instead (see
            # _schedule_review_activities).
            rec.message_subscribe(partner_ids=[rec.partner_id.id])

            if rec.status == 'pending':
                # Internal log note — does NOT email followers (the reviewer is
                # notified via the review activity instead, avoiding a duplicate email)
                rec.message_post(
                    body=Markup('<b>Document submitted for review:</b> %s<br/>Student: %s') % (
                        escape(doc_label), escape(rec.partner_id.name)
                    ),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

        # Only schedule review activities for documents that actually need review
        pending_records = records.filtered(lambda r: r.status == 'pending')
        pending_records._schedule_review_activities()
        return records

    def action_approve(self):
        for rec in self:
            # Remove previously approved document of the same type for this student
            # For benefit documents, also match benefit_type to avoid removing other benefit types
            domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('doc_type', '=', rec.doc_type),
                ('status', '=', 'approved'),
                ('id', '!=', rec.id),
            ]
            if rec.doc_type == 'benefit' and rec.benefit_type:
                domain.append(('benefit_type', '=', rec.benefit_type))
            self.search(domain).unlink()

            rec.write({
                'status': 'approved',
                'review_date': fields.Datetime.now(),
                'review_uid': self.env.user.id,
            })
            if rec.doc_type == 'iban' and rec.doc_value:
                rec._apply_bank_account()
            elif rec.doc_type == 'benefit' and rec.benefit_type:
                rec._apply_benefit()

            rec.activity_ids.unlink()

            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, rec.doc_type)
            rec.message_post(
                body=Markup('<b>Document approved:</b> %s<br/>Student: %s') % (
                    escape(doc_label), escape(rec.partner_id.name)
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def action_reject(self):
        for rec in self:
            rec.write({
                'status': 'rejected',
                'review_date': fields.Datetime.now(),
                'review_uid': self.env.user.id,
            })
            rec.activity_ids.unlink()

            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, rec.doc_type)
            body = Markup('<b>Document rejected:</b> %s<br/>Student: %s') % (
                escape(doc_label), escape(rec.partner_id.name)
            )
            if rec.rejection_reason:
                body += Markup('<br/>Reason: %s') % escape(rec.rejection_reason)
            rec.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def action_cancel(self):
        for rec in self:
            rec.write({'status': 'cancelled'})
            rec.activity_ids.unlink()

            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, rec.doc_type)
            rec.message_post(
                body=Markup('<b>Document submission cancelled:</b> %s<br/>Student: %s') % (
                    escape(doc_label), escape(rec.partner_id.name)
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def action_reset_to_pending(self):
        for rec in self:
            # Drop any leftover activities and reschedule a fresh review task
            rec.activity_ids.unlink()
            rec.write({
                'status': 'pending',
                'review_uid': False,
                'review_date': False,
                'rejection_reason': False,
            })
            rec._schedule_review_activities()

            doc_label = dict(rec._fields['doc_type'].selection).get(rec.doc_type, rec.doc_type)
            # Internal log note — does NOT email followers (the secretary is
            # notified via the review activity instead, avoiding a duplicate email)
            rec.message_post(
                body=Markup('<b>Document reopened for review:</b> %s<br/>Student: %s') % (
                    escape(doc_label), escape(rec.partner_id.name)
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
