# -*- coding: utf-8 -*-

import base64
import csv
import io

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PENDING_STATES = ['draft', 'sent']
CLOSE_ACTIONS = [
    ('delete', 'Delete the person'),
    ('archive', 'Archive'),
    ('ex_student', 'Back to alumni/withdrawal'),
    ('withdraw', 'Withdraw'),
    ('cancel', 'Cancel the enrollment only'),
    ('review', 'Review by hand (payment)'),
]
ACTION_ICONS = {'delete': '🗑️', 'archive': '📦', 'ex_student': '🎓', 'withdraw': '🚪',
                'cancel': '✖️', 'review': '⚠️'}


class EmsEnrollmentCloseWizard(models.TransientModel):
    """Close the enrollments nobody confirmed (issue #643): one action per person, previewed
    before anything is applied. See docs/en/developers/enrollment/close_unconfirmed_wizard.md."""
    _name = 'ems.enrollment_close_wizard'
    _description = 'Close unconfirmed enrollments'

    exit_date = fields.Date(string='Exit date', required=True,
                            default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    exit_reason = fields.Text(string='Exit reason',
                              default=lambda self: _("Enrollment not formalised"))
    line_ids = fields.One2many('ems.enrollment_close_wizard.line', 'wizard_id', string='People')
    has_withdrawals = fields.Boolean(compute='_compute_preview')
    preview_html = fields.Html(string='What will happen', compute='_compute_preview')
    result_html = fields.Html(string='Result', readonly=True)
    log_file = fields.Binary(string='Log (CSV)', readonly=True)
    log_file_name = fields.Char()

    @api.depends('line_ids.action', 'line_ids.order_ids')
    def _compute_preview(self):
        for wizard in self:
            actions = wizard.line_ids.mapped('action')
            wizard.has_withdrawals = 'withdraw' in actions
            counts = {action: actions.count(action) for action in dict(CLOSE_ACTIONS)}
            wizard.preview_html = Markup("<p><strong>{}</strong></p>{}").format(
                _("People: %(people)s. Enrollments: %(enrollments)s.",
                  people=len(wizard.line_ids), enrollments=len(wizard.line_ids.order_ids)),
                self._summary_html(counts, self._action_explanations()))

    @api.model
    def _action_explanations(self):
        return {
            'delete': _("they were never students: the person is deleted, with their portal user, "
                        "enrollments, authorizations and documents."),
            'archive': _("they were never students but have a corporate account or a convalidation: "
                         "the enrollment is cancelled, the portal revoked and the contact archived."),
            'ex_student': _("they had studied here: the enrollment is cancelled and they go back to "
                            "graduate (with a title) or withdrawal, with the Google account's grace period."),
            'withdraw': _("students without a group: withdrawn as with the withdrawal assistant, with the "
                          "exit date and reason below."),
            'cancel': _("they stay as they are: only the enrollment is cancelled."),
            'review': _("nothing is done: an enrollment has a payment or an invoice, review it by hand."),
        }

    @api.model
    def _summary_html(self, counts, details):
        """One line per action that applies to somebody: icon, label, how many and `details`."""
        labels = dict(self.env['ems.enrollment_close_wizard.line']._fields['action']._description_selection(self.env))
        rows = [Markup("<li>{} <strong>{}: {}</strong> - {}</li>").format(
                    ACTION_ICONS[action], labels[action], count, details[action])
                for action, count in counts.items() if count]
        return Markup("<ul class='list-unstyled'>{}</ul>").format(Markup("").join(rows))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        self._check_can_close()
        context = self.env.context
        records = self.env[context.get('active_model') or 'sale.order'].browse(context.get('active_ids') or [])
        if records._name == 'sale.order':
            partners = records.filtered(lambda order: order.state in PENDING_STATES).partner_id
        else:
            partners = records
        lines = []
        for partner in partners:
            orders = self.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id), ('state', 'in', PENDING_STATES)])
            action = self._resolve_action(partner.sudo(), orders)
            if action:
                lines.append((0, 0, {'partner_id': partner.id, 'order_ids': [(6, 0, orders.ids)],
                                     'action': action}))
        if not lines:
            raise UserError(_("None of the selected records has an enrollment left to close."))
        res['line_ids'] = lines
        return res

    @api.model
    def action_open(self, records):
        """Open the wizard on selected enrollments or applicants."""
        return {
            'type': 'ir.actions.act_window',
            'name': _("Close unconfirmed enrollments"),
            'res_model': self._name,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {'active_model': records._name, 'active_ids': records.ids},
        }

    def _check_can_close(self):
        if not self.env['res.partner']._ems_user_can_register_exits():
            raise UserError(_("Only the secretary, the head of studies or an administrator can close enrollments."))

    @api.model
    def _resolve_action(self, partner, orders):
        """What happens to `partner`, holding the pending `orders` (possibly none, when launched
        on an applicant). False: nothing to do with this contact (not a student-like one)."""
        contact_type = partner.contact_type
        if contact_type not in ('student', 'applicant', 'alumni', 'withdrawal', 'expelled'):
            return False
        if orders._ems_has_payment():
            return 'review'
        # A confirmed enrollment for the running course or a later one: they are staying, even
        # while still waiting for a group (one live enrollment per course, so it is never one
        # of `orders`).
        current_start = self.env.company.current_course_id.start or 0
        staying = partner.sale_order_ids.filtered(
            lambda order: order.state == 'sale' and order.ems_course_id.start >= current_start)
        if staying or contact_type in ('expelled', 'alumni', 'withdrawal') \
                or (contact_type == 'student' and partner.main_group_id):
            return 'cancel' if orders else False
        if contact_type == 'student':
            return 'withdraw'
        if partner.year_record_ids or partner.has_graduated:
            return 'ex_student'
        if partner.student_email or self.env['ems.convalidation'].sudo().search_count(
                [('student_id', '=', partner.id)], limit=1):
            return 'archive'
        return 'delete'

    def action_apply(self):
        """Apply each person's action, then show the result in the wizard with a CSV log of what
        happened to every person (downloaded on its own)."""
        self.ensure_one()
        self._check_can_close()
        counts = dict.fromkeys(dict(CLOSE_ACTIONS), 0)
        revoked = 0
        issues = []
        log = []
        for line in self.line_ids:
            partner = line.partner_id.sudo()
            orders = line.order_ids.sudo()
            action = line.action
            row = [partner.display_name, partner.contact_type or '', " ".join(orders.mapped('name')), action]
            summary = {'revoked': 0, 'issues': []}
            if action == 'delete' and not self._delete(partner, orders, summary['issues']):
                action = 'archive'
            elif action == 'withdraw':
                summary = partner._ems_register_exit('withdrawal', self.exit_date, self.exit_reason)
            elif action in ('cancel', 'archive', 'ex_student'):
                orders._action_cancel()
            if action == 'ex_student':
                summary = partner._ems_return_to_ex_student()
            elif action == 'archive':
                archived = self._archive(partner)
                archived['issues'] = summary['issues'] + archived['issues']
                summary = archived
            counts[action] += 1
            revoked += summary['revoked']
            issues += summary['issues']
            log.append(row + [action, " | ".join(summary['issues'])])
        self.log_file = self._build_log_csv(log)
        self.log_file_name = (f"close_enrollments_"
                              f"{self.env['ems.datetime_utils'].get_local_datetime().strftime('%Y%m%d_%H%M%S')}.csv")
        self.result_html = self._build_result_html(counts, revoked, issues)
        return self._reopen()

    def _build_log_csv(self, log):
        labels = dict(self.line_ids._fields['action']._description_selection(self.env))
        types = dict(self.env['res.partner']._fields['contact_type']._description_selection(self.env))
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([_("Person"), _("Contact Type"), _("Enrollments"), _("Planned action"),
                         _("Action applied"), _("Issues")])
        for name, contact_type, orders, planned, applied, issues in log:
            writer.writerow([name, types.get(contact_type, ''), orders, labels[planned], labels[applied], issues])
        return base64.b64encode(output.getvalue().encode('utf-8-sig'))

    def _build_result_html(self, counts, revoked, issues):
        done = {action: _("done.") for action in counts}
        done['review'] = _("left untouched, review them by hand.")
        html = Markup("<p><strong>{}</strong></p>{}").format(
            _("People processed: %(people)s.", people=sum(counts.values())), self._summary_html(counts, done))
        if revoked:
            html += Markup("<p>🔒 <strong>{}:</strong> {}</p>").format(_("Portal accesses revoked"), revoked)
        if issues:
            html += Markup("<p><strong>{} ({}):</strong></p>{}").format(
                _("Issues"), len(issues), self.env['ems.base'].build_html_list(issues))
        return html

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Close unconfirmed enrollments"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    def _delete(self, partner, orders, issues):
        """Delete a person who was never a student, with everything that only existed for them.
        False if something still references them: the savepoint undoes the attempt and the caller
        archives them instead."""
        name = partner.display_name
        try:
            with self.env.cr.savepoint():
                # The family keeps its access while another child is enrolled.
                partner._ems_revoke_student_portal()
                orders._action_cancel()
                self.env['sale.order'].sudo().search([('partner_id', '=', partner.id)]).unlink()
                self.env['res.users'].sudo().with_context(active_test=False).search(
                    [('partner_id', '=', partner.id)]).unlink()
                partner.unlink()
        except Exception as error:
            self.env.invalidate_all()
            issues.append(_("%(name)s: could not be deleted, archived instead (%(error)s)",
                            name=name, error=error))
            orders._action_cancel()
            return False
        return True

    def _archive(self, partner):
        """Cancelled enrollments are already done; revoke the portal and archive."""
        summary = partner._ems_revoke_student_portal()
        issues = list(summary['issues'])
        if partner._has_active_portal_user():
            issues.append(_("%(student)s: portal access could not be revoked, kept active",
                            student=partner.display_name))
        else:
            partner.write({'active': False})
        return {'revoked': len(summary['revoked']), 'issues': issues}


class EmsEnrollmentCloseWizardLine(models.TransientModel):
    _name = 'ems.enrollment_close_wizard.line'
    _description = 'Close unconfirmed enrollments: one person'

    wizard_id = fields.Many2one('ems.enrollment_close_wizard', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Person')
    contact_type = fields.Selection(related='partner_id.contact_type')
    order_ids = fields.Many2many('sale.order', string='Enrollments')
    action = fields.Selection(CLOSE_ACTIONS, string='Action')
