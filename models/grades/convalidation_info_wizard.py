# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models


class EmsConvalidationInfoWizard(models.TransientModel):
    _name = 'ems.convalidation.info_wizard'
    _description = "Ask the applicant of a convalidation request for more information."

    convalidation_id = fields.Many2one(string="Request", comodel_name='ems.convalidation', required=True,
                                       ondelete='cascade')
    student_id = fields.Many2one(string="Student", related='convalidation_id.student_id')
    message = fields.Text(string="What is missing", required=True,
                          help="Sent to the student (or the family of a minor) by email, and shown on the "
                               "portal, where they can answer and attach the documents asked for.")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if 'message' in fields_list and not vals.get('message'):
            vals['message'] = _("To resolve your convalidation request we need the following documentation:\n\n")
        return vals

    def action_send(self):
        """Email the request for information and record it on the portal. The request itself
        does not move: it stays where it was until the missing documents arrive."""
        self.ensure_one()
        convalidation = self.convalidation_id
        convalidation._ems_check_state(('pending', 'in_progress'))
        template = self.env.ref('ems.email_template_convalidation_info_request', raise_if_not_found=False)
        recipients = convalidation.student_id._ems_notification_recipients().filtered('email')
        body = Markup("<p>{}</p>").format(self.message)
        for recipient in recipients:
            template.with_context(
                lang=recipient.lang or convalidation.student_id.lang,
                ems_info_request=self.message,
            ).sudo().send_mail(convalidation.id, force_send=False, email_values={'email_to': recipient.email})
        convalidation._ems_post_communication(_("Documentation requested"), body)
        if recipients:
            note = _("Information requested from %s.") % ", ".join(recipients.mapped('email'))
        else:
            note = _("The request for information could not be emailed: nobody to notify has an email address.")
        convalidation.sudo().message_post(body=note, message_type='comment', subtype_xmlid='mail.mt_note')
        return {'type': 'ir.actions.act_window_close'}
