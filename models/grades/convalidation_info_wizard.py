# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, fields, models

from .convalidation import REVIEW_STATES


class EmsConvalidationInfoWizard(models.TransientModel):
    _name = 'ems.convalidation.info_wizard'
    _description = "Ask the applicant of a convalidation request for more information."

    convalidation_id = fields.Many2one(string="Request", comodel_name='ems.convalidation', required=True,
                                       ondelete='cascade')
    student_id = fields.Many2one(string="Student", related='convalidation_id.student_id')
    reason_id = fields.Many2one(string="Reason", comodel_name='ems.convalidation.info_reason', required=True,
                                default=lambda self: self._default_reason_id())
    message = fields.Text(string="Details",
                          help="Sent to the student (and their family, when it follows their convalidations) by email "
                               "after the reason, and shown on the portal, where they can answer and attach the "
                               "documents asked for.")

    def _default_reason_id(self):
        """First active reason by its own order: the most usual one, like the strike reasons."""
        return self.env['ems.convalidation.info_reason'].search([], limit=1)

    def _ems_request_text(self, lang):
        """The reason, in the reader's language, followed by the details."""
        reason = self.reason_id.with_context(lang=lang).name
        return f"{reason}\n\n{self.message}" if (self.message or '').strip() else reason

    def action_send(self):
        """Email the request for information and record it on the portal. The request then waits
        for the documentation (state 'documentation') until the applicant answers or the Head of
        Studies marks it as received."""
        self.ensure_one()
        convalidation = self.convalidation_id
        convalidation._ems_check_state(REVIEW_STATES)
        template = self.env.ref('ems.email_template_convalidation_info_request', raise_if_not_found=False)
        recipients = convalidation.student_id._ems_convalidation_recipients().filtered('email')
        for recipient in recipients:
            lang = recipient.lang or convalidation.student_id.lang
            template.with_context(
                lang=lang,
                ems_info_request=self._ems_request_text(lang),
            ).sudo().send_mail(convalidation.id, force_send=False, email_values={'email_to': recipient.email})
        convalidation.sudo().write({'info_request_reason_id': self.reason_id.id,
                                    'info_request': self.message,
                                    'info_request_date': fields.Date.context_today(self)})
        convalidation._ems_wait_for_documentation()
        body = Markup("<p style=\"white-space: pre-line;\">{}</p>").format(self._ems_request_text(self.env.lang))
        convalidation._ems_post_communication(_("Documentation requested"), body)
        if recipients:
            note = _("Information requested from %s.") % ", ".join(recipients.mapped('email'))
        else:
            note = _("The request for information could not be emailed: nobody to notify has an email address.")
        convalidation._ems_post_note(note)
        return {'type': 'ir.actions.act_window_close'}
