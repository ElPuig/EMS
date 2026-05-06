# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ems_communication(models.Model):
    _name = "ems.communication"
    _description = "Communication: a bulk email sent to groups of students and/or their families."
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
    scheduled_date = fields.Datetime(string="Send on")
    message = fields.Html(string="Message", required=True, sanitize=True)
    state = fields.Selection(
        string="State",
        selection=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sent', 'Sent'), ('cancelled', 'Cancelled')],
        default='draft',
        readonly=True,
    )
    sent_date = fields.Datetime(string="Sent on", readonly=True)
    sent_by = fields.Many2one(string="Sent by", comodel_name="res.users", readonly=True)
    communication_line_ids = fields.One2many(
        string="Recipient list",
        comodel_name="ems.communication.line",
        inverse_name="communication_id",
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

    @api.depends('communication_line_ids')
    def _compute_recipient_count(self):
        for rec in self:
            rec.recipient_count = len(rec.communication_line_ids)

    @api.depends('recipient_type')
    def _compute_has_families(self):
        for rec in self:
            rec.has_families = rec.recipient_type in ('families', 'both')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.subject or _("(New communication)")

    def _collect_recipients(self):
        seen_emails = set()
        vals_list = []

        for group in self.group_ids:
            for student in group.main_student_ids.filtered(lambda s: s.contact_type == 'student'):
                if self.recipient_type in ('students', 'both'):
                    email = student.student_email or student.email
                    if email and email not in seen_emails:
                        seen_emails.add(email)
                        vals_list.append({
                            'communication_id': self.id,
                            'partner_id': student.id,
                            'email': email,
                            'student_id': student.id,
                            'recipient_type': 'student',
                        })

                if self.recipient_type in ('families', 'both'):
                    # Mirror the consent logic from attendance_session.py
                    if not student.is_adult or student.auth_share:
                        for relation in student.relation_all_ids:
                            family = relation.other_partner_id
                            if family.contact_type == 'family' and family.email:
                                if family.email not in seen_emails:
                                    seen_emails.add(family.email)
                                    vals_list.append({
                                        'communication_id': self.id,
                                        'partner_id': family.id,
                                        'email': family.email,
                                        'student_id': student.id,
                                        'recipient_type': 'family',
                                    })

        return vals_list

    def action_send(self):
        self.ensure_one()
        if self.state not in ('draft',):
            raise UserError(_("Only draft communications can be sent."))

        # Use existing lines (manually edited) if present; otherwise auto-populate from groups.
        lines_to_send = self.communication_line_ids.filtered(lambda l: not l.notification_id)
        if not lines_to_send and not self.communication_line_ids:
            if not self.group_ids:
                raise UserError(_("Please add recipients or select at least one group before sending."))
            vals_list = self._collect_recipients()
            if not vals_list:
                raise UserError(_(
                    "No recipients found. Check that the selected groups have students "
                    "with email addresses."
                ))
            lines_to_send = self.env['ems.communication.line'].create(vals_list)

        if not lines_to_send:
            raise UserError(_("All recipients already have a notification queued."))

        eta = self.scheduled_date if self.use_schedule else False
        for line in lines_to_send:
            job_rec = line.with_delay(
                eta=eta,
                description=f"Communication '{self.subject}': line ID={line.id}",
            ).send_notification()
            job = self.sudo().env['queue.job'].search([('uuid', '=', job_rec.uuid)]) or False
            if job:
                line.sudo().write({'notification_id': job.id})

        new_state = 'scheduled' if (self.use_schedule and self.scheduled_date) else 'sent'
        self.write({
            'state': new_state,
            'sent_date': fields.Datetime.now(),
            'sent_by': self.env.uid,
        })
        self.chatter(_("Communication %s. %d email(s) enqueued.") % (new_state, len(lines_to_send)))
        return True

    def action_cancel(self):
        self.ensure_one()
        for line in self.communication_line_ids:
            if line.notification_id and line.notification_id.state in ('pending', 'enqueued'):
                line.notification_id.button_cancelled()
        self.write({'state': 'cancelled'})
        self.chatter(_("Communication cancelled."))
        return True


class ems_communication_line(models.Model):
    _name = "ems.communication.line"
    _description = "Communication line: one email recipient per row."
    _inherit = ['ems.base']

    communication_id = fields.Many2one(
        string="Communication",
        comodel_name="ems.communication",
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
    notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")
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
            ('cancelled', 'Cancelled'),
        ],
        compute="_compute_display_status",
        store=False,
    )

    @api.depends('notification_id', 'notification_id.state')
    def _compute_display_status(self):
        for rec in self:
            if not rec.notification_id:
                rec.display_status = 'draft'
            else:
                rec.display_status = rec.notification_id.state

    def send_notification(self):
        self.ensure_one()
        template = self.env.ref('ems.mail_communication', raise_if_not_found=True)
        lang = self.partner_id.lang if self.partner_id else False
        tmpl = template.with_context(lang=lang).sudo() if lang else template.sudo()
        tmpl.send_mail(self.id, force_send=True, email_values={'email_to': self.email})
        return True

    def open_exception_popup(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Error details'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('ems.view_communication_line_exception_popup').id,
            'target': 'new',
            'flags': {'mode': 'readonly'},
        }
