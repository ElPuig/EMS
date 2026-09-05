# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class EmsNotice(models.Model):
    _name = "ems.notice"
    _description = "Notice: a bulk email sent to groups of students and/or their families."
    _inherit = ['ems.base']
    _order = "create_date desc"

    subject = fields.Char(string="Subject", required=True)
    group_ids = fields.Many2many(string="Groups", comodel_name="ems.group")
    recipient_type = fields.Selection(
        string="Send to",
        selection=[('students', 'Students'), ('families', 'Families'), ('both', 'Both')],
        required=True,
        default='both',
    )
    use_schedule = fields.Boolean(string="Schedule sending", default=False)
    scheduled_date = fields.Datetime(string="Scheduled on")
    message = fields.Html(string="Message", required=True, sanitize=True)
    state = fields.Selection(
        string="State",
        selection=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sent', 'Sent'), ('failed', 'Failed')],
        default='draft',
        readonly=True,
        copy=False,
    )
    sent_date = fields.Datetime(string="Sent on", readonly=True, copy=False)
    sent_by = fields.Many2one(string="Sent by", comodel_name="res.users", readonly=True, copy=False)
    notice_line_ids = fields.One2many(
        string="Recipient list",
        comodel_name="ems.notice.line",
        inverse_name="notice_id",
        copy=True
    )
    recipient_count = fields.Integer(
        string="# Recipients",
        compute="_compute_recipient_count",
        store=False,
    )
    has_families = fields.Boolean(
        string="Includes families",
        compute="_compute_has_families",
        store=False,
    )
    can_cancel = fields.Boolean(
        string="Can cancel",
        compute="_compute_can_cancel",
        store=False,
    )

    @api.depends('notice_line_ids')
    def _compute_recipient_count(self):
        for notice in self:
            notice.recipient_count = len(notice.notice_line_ids)

    @api.depends('recipient_type')
    def _compute_has_families(self):
        for notice in self:
            notice.has_families = notice.recipient_type in ('families', 'both')

    @api.depends('state', 'use_schedule', 'notice_line_ids.notification_id.state')
    def _compute_can_cancel(self):
        RUNNING = {'started', 'done', 'failed'}
        for notice in self:
            if notice.state != 'scheduled' or not notice.use_schedule:
                notice.can_cancel = False
                continue
            notice.can_cancel = not any(
                line.notification_id and line.notification_id.state in RUNNING
                for line in notice.notice_line_ids
            )

    def _compute_display_name(self):
        for notice in self:
            notice.display_name = notice.subject or _("(New notice)")

    def _build_auto_lines(self, groups, recipient_type, seen_emails):
        """Return a list of ems.notice.line virtual records for the given groups."""
        new_lines = self.env['ems.notice.line']
        for group in groups:
            for student in group.main_student_ids.filtered(lambda s: s.contact_type == 'student'):
                if recipient_type in ('students', 'both'):
                    email = student.student_email or student.email
                    if email and email not in seen_emails:
                        seen_emails.add(email)
                        new_lines |= self.env['ems.notice.line'].new({
                            'partner_id': student.id,
                            'email': email,
                            'student_id': student.id,
                            'recipient_type': 'student',
                            'source_group_id': group.id,
                        })

                if recipient_type in ('families', 'both'):
                    if not student.is_adult or student.auth_share:
                        for relation in student.relation_all_ids:
                            family = relation.other_partner_id
                            if family.contact_type == 'family' and family.email:
                                if family.email not in seen_emails:
                                    seen_emails.add(family.email)
                                    new_lines |= self.env['ems.notice.line'].new({
                                        'partner_id': family.id,
                                        'email': family.email,
                                        'student_id': student.id,
                                        'recipient_type': 'family',
                                        'source_group_id': group.id,
                                    })
        return new_lines

    @api.onchange('group_ids', 'recipient_type')
    def _onchange_groups(self):
        # Manual lines: those not linked to any auto-populated group
        manual_lines = self.notice_line_ids.filtered(lambda l: not l.source_group_id)
        seen_emails = set(manual_lines.mapped('email'))
        new_auto_lines = self._build_auto_lines(self.group_ids, self.recipient_type, seen_emails)
        self.notice_line_ids = manual_lines | new_auto_lines

    def unlink(self):
        sent = self.filtered(lambda notice: notice.state != 'draft')
        if sent:
            raise UserError(_(
                "Cannot delete a notice that has already been scheduled, sent or failed to "
                "send. Please archive it instead."
            ))
        return super().unlink()

    def action_send(self):
        self.ensure_one()
        if self.state not in ('draft',):
            raise UserError(_("Only draft notices can be sent."))

        lines_to_send = self.notice_line_ids.filtered(lambda l: not l.notification_id)
        if not lines_to_send:
            raise UserError(_("No recipients to send to. Add recipients in the 'Sending status' section."))

        eta = self.scheduled_date if self.use_schedule else False
        for line in lines_to_send:
            job_rec = line.with_delay(
                eta=eta,
                description=f"Notice '{self.subject}': line ID={line.id}",
            ).send_notification()
            job = self.sudo().env['queue.job'].search([('uuid', '=', job_rec.uuid)]) or False
            if job:
                line.sudo().write({'notification_id': job.id})

        self.write({'state': 'scheduled', 'sent_by': self.env.uid})
        self.chatter(_("Notice scheduled. %d email(s) enqueued.") % len(lines_to_send))
        return True

    def _check_and_finalize(self, just_succeeded_line=None):
        """Update state once all jobs reach a terminal state.

        Called after each successful send (just_succeeded_line = the line whose job
        just finished but whose queue.job record is still 'started') and by the cron
        to handle failed jobs.
        """
        PENDING = {'draft', 'pending', 'enqueued', 'started'}
        for notice in self:
            if notice.state != 'scheduled':
                continue
            has_pending = False
            has_failed = False
            for line in notice.notice_line_ids:
                if just_succeeded_line and line.id == just_succeeded_line.id:
                    continue  # treat as done — the job is about to transition
                status = line.display_status
                if status in PENDING:
                    has_pending = True
                elif status == 'failed':
                    has_failed = True
            if has_pending:
                continue
            if has_failed:
                notice.write({'state': 'failed'})
            else:
                notice.write({'state': 'sent', 'sent_date': fields.Datetime.now()})

    def action_cancel(self):
        self.ensure_one()
        if not self.can_cancel:
            raise UserError(_("This notice cannot be cancelled: it has already been sent or is being processed."))
        for line in self.notice_line_ids:
            if line.notification_id and line.notification_id.state in ('pending', 'enqueued'):
                line.notification_id.button_cancelled()
            line.write({'notification_id': False})
        self.write({'state': 'draft'})
        self.chatter(_("Notice cancelled and returned to draft."))
        return True


class EmsNoticeLine(models.Model):
    _name = "ems.notice.line"
    _description = "Notice line: one email recipient per row."
    _inherit = ['ems.base']

    notice_id = fields.Many2one(
        string="Notice",
        comodel_name="ems.notice",
        ondelete='cascade',
        required=True,
    )
    partner_id = fields.Many2one(string="Contact", comodel_name="res.partner")
    email = fields.Char(string="Email", required=True)
    student_id = fields.Many2one(
        string="Student",
        comodel_name="res.partner",
        domain="[('contact_type', '=', 'student')]",
    )
    recipient_type = fields.Selection(
        string="Type",
        selection=[('student', 'Student'), ('family', 'Family')],
    )
    source_group_id = fields.Many2one(
        string="Source group",
        comodel_name="ems.group",
        ondelete='set null',
    )
    notification_id = fields.Many2one(string="Notification", comodel_name="queue.job", copy=False)
    schedule_date = fields.Datetime(string="Scheduled on", related="notification_id.eta")
    exception = fields.Text(string="Exception", related="notification_id.exc_info")
    display_status = fields.Selection(
        string="Status",
        selection=[
            ('draft', 'Not queued'),
            ('pending', 'Pending'),
            ('enqueued', 'Enqueued'),
            ('started', 'In progress'),
            ('done', 'Sent'),
            ('failed', 'Failed'),
        ],
        compute="_compute_display_status",
        store=False,
    )

    @api.depends('notification_id', 'notification_id.state')
    def _compute_display_status(self):
        for line in self:
            job_state = line.notification_id.state if line.notification_id else 'draft'
            line.display_status = 'draft' if job_state == 'cancelled' else job_state

    def send_notification(self):
        self.ensure_one()

        # Register a postrollback hook so that if this job fails (transaction
        # rolls back), the notice state is still updated. Queue.job marks
        # the job as 'failed' in a separate committed cursor BEFORE the rollback,
        # so by the time this hook runs the job state is already 'failed' in the DB.
        notice_id = self.notice_id.id
        db_name = self.env.cr.dbname

        def _on_failure():
            import odoo
            with odoo.registry(db_name).cursor() as cr:
                odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})['ems.notice']\
                    .browse(notice_id)._check_and_finalize()

        self.env.cr.postrollback.add(_on_failure)

        template = self.env.ref('ems.mail_notice', raise_if_not_found=True)
        lang = self.partner_id.lang if self.partner_id else False
        tmpl = template.with_context(lang=lang).sudo() if lang else template.sudo()

        rendered = tmpl._generate_template([self.id], ['body_html'])
        body_html = rendered.get(self.id, {}).get('body_html', '')
        body_html = self._prepare_body_for_email(body_html)

        tmpl.send_mail(
            self.id,
            force_send=True,
            email_values={'email_to': self.email, 'body_html': body_html},
        )
        self.notice_id.sudo()._check_and_finalize(just_succeeded_line=self)
        return True

    def _prepare_body_for_email(self, body_html):
        """Replace image URLs/data-URIs with publicly accessible access-token URLs."""
        import re
        from markupsafe import Markup
        from lxml import html as lxml_html

        if not body_html:
            return body_html

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')

        try:
            doc = lxml_html.fromstring(f'<div>{body_html}</div>')
        except Exception:
            return body_html

        for img in doc.iter('img'):
            src = img.get('src') or ''

            if src.startswith('data:image/'):
                m = re.match(r'data:(image/[^;]+);base64,(.+)', src, re.DOTALL)
                if not m:
                    continue
                mime_type, b64_data = m.group(1), m.group(2).strip()
                ext = mime_type.split('/')[-1]
                try:
                    attachment = self.env['ir.attachment'].sudo().create({
                        'name': f'image.{ext}',
                        'datas': b64_data,
                        'mimetype': mime_type,
                        'res_model': self._name,
                        'res_id': self.id,
                    })
                    attachment.generate_access_token()
                    img.set('src', f'{base_url}/web/image/{attachment.id}?access_token={attachment.access_token}')
                except Exception:
                    pass

            else:
                m = re.search(r'/web/image/(\d+)', src)
                if not m:
                    continue
                attachment_id = int(m.group(1))
                attachment = self.env['ir.attachment'].sudo().browse(attachment_id)
                if not attachment.exists():
                    continue
                if not attachment.access_token:
                    attachment.generate_access_token()
                img.set('src', f'{base_url}/web/image/{attachment_id}?access_token={attachment.access_token}')

        result = lxml_html.tostring(doc, encoding='unicode', method='html')
        if result.startswith('<div>') and result.endswith('</div>'):
            result = result[5:-6]
        return Markup(result)

    def open_notification_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'queue.job',
            'res_id': self.notification_id.id,
            'view_id': self.env.ref('queue_job.view_queue_job_form').id,
            'view_mode': 'form',
            'target': 'new',
        }

    def open_exception_popup(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Error details'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('ems.view_notice_line_exception_popup').id,
            'target': 'new',
            'flags': {'mode': 'readonly'},
        }
