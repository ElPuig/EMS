# -*- coding: utf-8 -*-
"""Staff calls in the backend (the 2026-11-04 review with Juan Morote and adriamt): the portal is
for students and families only, so a teacher applies to a staff call, follows their application
and prepares their mobility from the Erasmus+ app ("My participation"). The screens only read the
user's own records (record rules, security/rules/erasmus.xml); everything that changes something
goes through the actions below and the wizards of staff_wizards.py, which call the same model
methods the portal uses (`_ems_portal_*`), as superuser once the record is checked to be the
user's own. See docs/en/developers/erasmus/erasmus.md, "Staff in the backend"."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .application import ANSWER_FIELDS
from .mobility import OPEN_STATES

# P17 (adriamt, 2026-11-13): when a teacher may tick their steps on return.
RETURN_TICK_PHASES = ('stay', 'return', 'done')


def staff_action(env, xmlid, record=None):
    """The window action `xmlid`, opened on `record`'s form when given."""
    action = env['ir.actions.act_window']._for_xml_id(xmlid)
    if record:
        action.update({'res_id': record.id, 'view_mode': 'form',
                       'views': [(view_id, kind) for view_id, kind in action['views'] if kind == 'form']})
    return action


def staff_wizard(env, model, name, **defaults):
    """A wizard (`model`) in a dialog, with its defaults (staff screens and the team's mobility dialogs)."""
    return {'type': 'ir.actions.act_window', 'res_model': model, 'name': name, 'view_mode': 'form',
            'target': 'new', 'context': {f'default_{key}': value for key, value in defaults.items()}}


class EmsErasmusMailLink(models.AbstractModel):
    """Where an email sends the applicant: the portal's Erasmus+ page for a student (as ever), the
    backend for staff, who never use the portal (the 2026-11-04 review). `_ems_mail_place()` says
    where in words ("on the school portal", "in EMS") and `_ems_mail_url()` links there."""
    _name = 'ems.erasmus.mail.link'
    _description = 'Erasmus+ link in the emails'

    # (action of the staff screen, portal path) of each model; the record's id is appended to the
    # staff link, and to a portal path ending in "/".
    _ems_mail_paths = ('ems.action_erasmus_my_applications', '/my/erasmus')

    def _ems_mail_staff(self):
        return self.audience == 'staff'

    def _ems_mail_record(self):
        """The record the staff link opens."""
        return self

    def _ems_mail_place(self):
        self.ensure_one()
        return _("in EMS") if self._ems_mail_staff() else _("on the school portal")

    def _ems_mail_url(self):
        self.ensure_one()
        record = self._ems_mail_record()
        action, portal = record._ems_mail_paths
        if self._ems_mail_staff():
            return f"{self.get_base_url()}/odoo/action-{action}/{record.id}"
        return f"{self.get_base_url()}{portal}{record.id if portal.endswith('/') else ''}"


class EmsErasmusCall(models.Model):
    _name = 'ems.erasmus.call'
    _inherit = ['ems.erasmus.call', 'ems.erasmus.mail.link']
    _ems_mail_paths = ('ems.action_erasmus_staff_calls', '/my/erasmus/call/')

    staff_mine = fields.Boolean(string="Open to me", compute='_compute_staff_mine', search='_search_staff_mine',
                                help="A staff call the current user can apply to, or has applied to.")
    staff_application_id = fields.Many2one(string="My application", comodel_name='ems.erasmus.application',
                                           compute='_compute_staff_mine')

    @api.depends_context('uid')
    def _compute_staff_mine(self):
        partner = self.env.user.partner_id
        mine = self._ems_staff_calls_of(partner)
        applications = {application.call_id.id: application.id
                        for application in partner._ems_erasmus_applications()}
        for call in self:
            call.staff_mine = call in mine
            call.staff_application_id = applications.get(call.id, False)

    def _search_staff_mine(self, operator, value):
        if operator not in ('=', '!='):
            raise UserError(_("Unsupported search on %s.", self._fields['staff_mine'].string))
        ids = self._ems_staff_calls_of(self.env.user.partner_id).ids
        return [('id', 'in' if (operator == '=') == bool(value) else 'not in', ids)]

    @api.model
    def _ems_staff_calls_of(self, partner):
        """The staff calls an internal user (`partner`) can apply to, or has applied to."""
        if not partner.sudo().user_ids.filtered(lambda user: not user.share):
            return self.browse()
        calls = partner._ems_erasmus_calls() | partner._ems_erasmus_applications().call_id
        return calls.filtered(lambda call: call.audience == 'staff').with_env(self.env)

    def action_staff_apply(self):
        """The staff member opens their application to this call, created as a draft the first
        time (same rules as ever: published, accepting applications, and they may apply to it).
        While nothing is filled in and it can still be changed, its form's dialog opens straight
        away, so they know where to write (issue #802)."""
        self.ensure_one()
        if self.env.user.share or self.audience != 'staff':
            raise UserError(_("You cannot apply to this call."))
        application = self.env['ems.erasmus.application'].sudo()._ems_portal_get_or_create(
            self.sudo(), self.env.user.partner_id).with_env(self.env)
        if application.staff_editable and not application.staff_answered:
            return application.action_staff_edit(open_application=True)
        return application._ems_staff_form()

    def get_formview_id(self, access_uid=None):
        """A staff call opens in the staff's form for whoever can apply to it and doesn't manage the
        calls (from the notice in their daily summary, a link)."""
        user = self.env['res.users'].browse(access_uid) if access_uid else self.env.user
        if len(self) == 1 and self.sudo().audience == 'staff' and \
                not self.env['ems.erasmus.application'].with_user(user)._ems_can_manage() and \
                self.with_user(user).staff_mine:
            return self.env.ref('ems.view_erasmus_call_staff_form').id
        return super().get_formview_id(access_uid=access_uid)


class EmsErasmusApplication(models.Model):
    _name = 'ems.erasmus.application'
    _inherit = ['ems.erasmus.application', 'ems.erasmus.mail.link']

    staff_own = fields.Boolean(string="Mine", compute='_compute_staff')
    staff_editable = fields.Boolean(string="Can be changed", compute='_compute_staff')
    staff_answered = fields.Boolean(string="Filled in", compute='_compute_staff',
                                    help="Some answer of the form is filled in.")
    staff_can_submit = fields.Boolean(string="Can be submitted", compute='_compute_staff')
    staff_claimable = fields.Boolean(string="Can claim", compute='_compute_staff')
    staff_offer_id = fields.Many2one(string="Place offered", comodel_name='ems.erasmus.offer', compute='_compute_staff')
    staff_mobility_id = fields.Many2one(string="My mobility", comodel_name='ems.erasmus.mobility',
                                        compute='_compute_staff')
    staff_next_step = fields.Char(string="What to do now", compute='_compute_staff')
    staff_next_level = fields.Char(string="Next step colour", compute='_compute_staff')
    staff_next_deadline = fields.Char(string="Before", compute='_compute_staff')
    # support_needs is the Erasmus team's (groups=TEAM): its author reads their own answer here.
    staff_support_needs = fields.Text(string="My support needs", compute='_compute_staff')
    rules_document = fields.Binary(string="Call rules (PDF)", related='call_id.rules_document')
    rules_filename = fields.Char(string="Call rules file name", related='call_id.rules_filename')

    @api.depends('state', 'offer_ids.state', 'mobility_ids', 'resolution_line_ids', *ANSWER_FIELDS['staff'])
    @api.depends_context('uid')
    def _compute_staff(self):
        partner = self.env.user.partner_id
        empty = {'staff_own': False, 'staff_editable': False, 'staff_answered': False, 'staff_can_submit': False,
                 'staff_claimable': False, 'staff_offer_id': False, 'staff_mobility_id': False, 'staff_next_step': False,
                 'staff_next_level': False, 'staff_next_deadline': False, 'staff_support_needs': False}
        for application in self:
            own = application.sudo()
            if own.partner_id != partner or own.audience != 'staff' or self.env.user.share:
                application.update(empty)
                continue
            editable = own._ems_portal_editable()
            application.update({
                **own._ems_staff_next(),
                'staff_own': True,
                'staff_editable': editable,
                'staff_answered': any(own[name] for name in ANSWER_FIELDS['staff']),
                'staff_can_submit': editable or own._ems_subsanation_open(),
                'staff_claimable': bool(own._ems_portal_claimable()),
                'staff_offer_id': own.offer_ids.filtered(lambda offer: offer.state == 'pending')[:1].id,
                'staff_mobility_id': own.mobility_ids[:1].id,
                'staff_support_needs': own.support_needs,
            })

    def get_formview_id(self, access_uid=None):
        """A staff member's own application opens in their form (from a task, a link, a mention)."""
        user = self.env['res.users'].browse(access_uid) if access_uid else self.env.user
        if len(self) == 1 and not self.with_user(user)._ems_can_manage() and \
                self.sudo().partner_id == user.partner_id and self.sudo().audience == 'staff':
            return self.env.ref('ems.view_erasmus_application_staff_form').id
        return super().get_formview_id(access_uid=access_uid)

    def _ems_staff_check(self):
        """This application, as superuser, once checked to be the current user's own staff one."""
        self.ensure_one()
        own = self.sudo()
        if self.env.user.share or own.partner_id != self.env.user.partner_id or own.audience != 'staff':
            raise AccessError(_("This is not your application."))
        return own

    def _ems_staff_form(self):
        """The application opened in its form (after a dialog launched from the call)."""
        return staff_action(self.env, 'ems.action_erasmus_my_applications', self)

    def _ems_staff_reload(self, message, next_action=None):
        """Back to the application's form, refreshed (or on to `next_action`), with `message` as a
        notification."""
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'message': message, 'type': 'success',
            'next': next_action or {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}

    def _ems_staff_next(self):
        """The portal's "what to do now" box, for the teacher's own application and mobility forms."""
        self.ensure_one()
        nxt = self._ems_portal_progress()['next']
        if self.state == 'draft' and self._ems_portal_editable():
            # The portal's "Complete your application", with where to do it in the backend.
            nxt = {**nxt, 'text': _("Fill in your application with the Fill in the form button, and submit it.")}
        deadline = nxt['deadline']
        deadline = deadline.strftime('%d/%m/%Y') if nxt['is_date'] else self.call_id._ems_local_format(deadline)
        return {'staff_next_step': nxt['text'], 'staff_next_level': nxt['level'],
                'staff_next_deadline': deadline or False}

    def action_staff_edit(self, open_application=False):
        """The form's dialog. `open_application`: launched from the call, so saving opens the
        application instead of refreshing the screen behind the dialog."""
        own = self._ems_staff_check()
        if not own._ems_portal_editable():
            raise UserError(_("The application can no longer be changed."))
        return staff_wizard(self.env, 'ems.erasmus.staff.application.wizard', _("My application"),
                            application_id=self.id, open_application=open_application)

    def action_staff_submit(self):
        self._ems_staff_check().action_submit()
        return self._ems_staff_reload(_("Application submitted. You will receive a receipt by email."))

    def action_staff_claim(self):
        own = self._ems_staff_check()
        if not own._ems_portal_claimable():
            raise UserError(_("You cannot claim now."))
        return staff_wizard(self.env, 'ems.erasmus.staff.claim.wizard', _("Claim"), application_id=self.id)

    def action_staff_accept_offer(self):
        offer = self._ems_staff_pending_offer()
        offer.action_accept()
        return self._ems_staff_reload(_("Place accepted. Your mobility is under My participation."))

    def action_staff_renounce_offer(self):
        self._ems_staff_pending_offer()
        return staff_wizard(self.env, 'ems.erasmus.staff.renounce.wizard', _("Renounce the place"),
                            application_id=self.id)

    def _ems_staff_pending_offer(self):
        offer = self._ems_staff_check().offer_ids.filtered(lambda offer: offer.state == 'pending')[:1]
        if not offer:
            raise UserError(_("No place is waiting for your answer."))
        return offer

    def action_staff_open_mobility(self):
        mobility = self._ems_staff_check().mobility_ids[:1]
        if not mobility:
            raise UserError(_("This application has no mobility yet."))
        return staff_action(self.env, 'ems.action_erasmus_my_mobilities', mobility.with_env(self.env))


class EmsErasmusResolutionLine(models.Model):
    _name = 'ems.erasmus.resolution.line'
    _inherit = ['ems.erasmus.resolution.line', 'ems.erasmus.mail.link']

    def _ems_mail_record(self):
        return self.application_id

    def action_staff_download(self):
        """The staff member downloads the published resolution they appear on (the PDF lists
        everyone in it, so it is rendered by the export controller as superuser)."""
        self.ensure_one()
        line = self.sudo()
        if self.env.user.share or line.application_id.partner_id != self.env.user.partner_id \
                or line.resolution_id.state != 'published':
            raise AccessError(_("This is not your resolution."))
        return {'type': 'ir.actions.act_url', 'target': 'download',
                'url': f"/ems/erasmus/resolution/{line.resolution_id.id}/pdf"}


class EmsErasmusMobility(models.Model):
    _name = 'ems.erasmus.mobility'
    _inherit = ['ems.erasmus.mobility', 'ems.erasmus.mail.link']
    _ems_mail_paths = ('ems.action_erasmus_my_mobilities', '/my/erasmus')

    staff_own = fields.Boolean(string="Mine", compute='_compute_staff')
    staff_can_propose = fields.Boolean(string="Can send a proposal", compute='_compute_staff')
    staff_self_assessment_open = fields.Boolean(string="Self-assessment to answer", compute='_compute_staff')
    staff_eu_survey_open = fields.Boolean(string="EU Survey to answer", compute='_compute_staff')
    staff_can_renounce = fields.Boolean(string="Can renounce", compute='_compute_staff')
    # Issue #787 (P11, P14): the same "what to do now" box as on the application, in every state.
    staff_next_step = fields.Char(string="What to do now", compute='_compute_staff')
    staff_next_level = fields.Char(string="Next step colour", compute='_compute_staff')
    staff_next_deadline = fields.Char(string="Before", compute='_compute_staff')

    @api.depends('state', 'proposal_state', 'self_assessment_ids', 'eu_survey_state', 'date_start', 'date_end')
    @api.depends_context('uid')
    def _compute_staff(self):
        partner = self.env.user.partner_id
        for mobility in self:
            own = mobility.sudo()
            mine = not self.env.user.share and own.partner_id == partner and own.audience == 'staff'
            mobility.update({
                'staff_own': mine,
                'staff_can_propose': mine and (own._ems_can_change_proposal() or (
                    own.state == 'choosing' and own.proposal_state != 'pending')),
                'staff_self_assessment_open': mine and bool(own._ems_self_assessments_open()),
                'staff_eu_survey_open': mine and own._ems_eu_survey_open() and own.eu_survey_state == 'pending',
                'staff_can_renounce': mine and own._ems_can_renounce(),
                **(own.application_id._ems_staff_next() if mine else
                   {'staff_next_step': False, 'staff_next_level': False, 'staff_next_deadline': False}),
            })

    def get_formview_id(self, access_uid=None):
        """A staff member's own mobility opens in their form (from the weekly task, a link)."""
        user = self.env['res.users'].browse(access_uid) if access_uid else self.env.user
        if len(self) == 1 and not self.with_user(user)._ems_can_manage() and \
                self.sudo().partner_id == user.partner_id and self.sudo().audience == 'staff':
            return self.env.ref('ems.view_erasmus_mobility_staff_form').id
        return super().get_formview_id(access_uid=access_uid)

    def _ems_staff_check(self):
        """This mobility, as superuser, once checked to be the current user's own staff one."""
        self.ensure_one()
        own = self.sudo()
        if self.env.user.share or own.partner_id != self.env.user.partner_id or own.audience != 'staff':
            raise AccessError(_("This is not your mobility."))
        return own

    def action_staff_propose(self):
        self._ems_staff_check()
        if not self.staff_can_propose:
            raise UserError(_("You cannot send a proposal now."))
        return staff_wizard(self.env, 'ems.erasmus.staff.proposal.wizard', _("Activity proposal"),
                            mobility_id=self.id)

    def action_staff_commitment(self):
        own = self._ems_staff_check()
        if not own.commitment_pending:
            raise UserError(_("There is no commitment letter to sign."))
        return staff_wizard(self.env, 'ems.erasmus.staff.commitment.wizard', _("Commitment letter"),
                            mobility_id=self.id)

    def action_staff_self_assessment(self):
        self._ems_staff_check()
        if not self.staff_self_assessment_open:
            raise UserError(_("This week's self-assessment cannot be answered now."))
        return staff_wizard(self.env, 'ems.erasmus.staff.self_assessment.wizard', _("Weekly self-assessment"),
                            mobility_id=self.id)

    def action_staff_eu_survey(self):
        self._ems_staff_check()._ems_portal_eu_survey()
        return self.env['ems.erasmus.application']._ems_staff_reload(_("Thank you: the Erasmus team will check it."))

    def action_staff_renounce(self):
        if not self._ems_staff_check()._ems_can_renounce():
            raise UserError(_("The place of %s can no longer be renounced (the stay has begun): talk to the Erasmus "
                              "team.",
                              self.sudo().partner_id.name))
        return staff_wizard(self.env, 'ems.erasmus.staff.renounce.wizard', _("Renounce the place"),
                            mobility_id=self.id)


class EmsErasmusApplicationDocument(models.Model):
    _inherit = 'ems.erasmus.application.document'

    staff_can_upload = fields.Boolean(string="Can hand in", compute='_compute_staff')
    staff_sign_url = fields.Char(string="Signature link", compute='_compute_staff')

    @api.depends('attachment_ids', 'review_state', 'correction_requested')
    @api.depends_context('uid')
    def _compute_staff(self):
        partner = self.env.user.partner_id
        for line in self:
            own = line.sudo()
            line.staff_can_upload = own._ems_staff_uploadable(partner)
            line.staff_sign_url = own._ems_portal_sign_url(partner) if own.signature_ids else False

    def _ems_staff_uploadable(self, partner):
        """A staff member can hand in this line (as superuser): of their own application while it
        can be changed (or this document was asked to be corrected), or of their own mobility
        while it is open, unless the Erasmus team handles it."""
        self.ensure_one()
        application, mobility = self.application_id, self.mobility_id
        if mobility:
            return mobility.partner_id == partner and mobility.audience == 'staff' and \
                mobility.state in OPEN_STATES and self.handled_by != 'team' and self._ems_is_open()
        return application.partner_id == partner and application.audience == 'staff' and (
            application._ems_portal_editable() or self in application._ems_portal_correctable())

    def _ems_staff_check(self):
        self.ensure_one()
        own = self.sudo()
        if self.env.user.share or not own._ems_staff_uploadable(self.env.user.partner_id):
            raise AccessError(_("You cannot hand in this document now."))
        return own

    def action_staff_upload(self):
        self._ems_staff_check()
        return staff_wizard(self.env, 'ems.erasmus.staff.document.wizard', self.sudo().name, line_id=self.id)

    def action_staff_sign(self):
        self.ensure_one()
        if not self.staff_sign_url:
            raise UserError(_("There is nothing for you to sign in this document."))
        return {'type': 'ir.actions.act_url', 'target': 'new', 'url': self.staff_sign_url}


class EmsErasmusOffer(models.Model):
    _name = 'ems.erasmus.offer'
    _inherit = ['ems.erasmus.offer', 'ems.erasmus.mail.link']

    def _ems_mail_staff(self):
        return self.call_id.audience == 'staff'

    def _ems_mail_record(self):
        return self.application_id


class EmsErasmusClaim(models.Model):
    _name = 'ems.erasmus.claim'
    _inherit = ['ems.erasmus.claim', 'ems.erasmus.mail.link']

    def _ems_mail_staff(self):
        return self.call_id.audience == 'staff'

    def _ems_mail_record(self):
        return self.application_id


class EmsErasmusMobilityTask(models.Model):
    """Issue #787 (8.8): the teacher sees the steps of their own mobility and ticks theirs, as the
    portal guides the students; the team still ticks any of them."""
    _inherit = 'ems.erasmus.mobility.task'

    staff_can_tick = fields.Boolean(string="Can tick", compute='_compute_staff_can_tick')
    staff_can_untick = fields.Boolean(string="Can untick", compute='_compute_staff_can_tick')

    @api.depends('done', 'done_user_id', 'stage', 'mobility_id.state', 'mobility_id.phase')
    @api.depends_context('uid')
    def _compute_staff_can_tick(self):
        """A step before leaving while the mobility is open; a step on return only once the stay has
        started, closed mobility included (P17: the news piece is often written on the last day)."""
        partner = self.env.user.partner_id
        for task in self:
            own = task.sudo()
            mobility = own.mobility_id
            in_time = (mobility.phase in RETURN_TICK_PHASES if own.stage == 'return'
                       else mobility.state in OPEN_STATES)
            open_own = (not self.env.user.share and mobility.partner_id == partner and mobility.audience == 'staff'
                        and in_time)
            task.staff_can_tick = open_own and not own.done
            task.staff_can_untick = open_own and own.done and own.done_user_id == self.env.user

    def action_staff_done(self):
        self.ensure_one()
        if not self.staff_can_tick:
            raise UserError(_("You cannot tick this step."))
        self.sudo().done = True

    def action_staff_undo(self):
        self.ensure_one()
        if not self.staff_can_untick:
            raise UserError(_("Only the Erasmus team can untick this step."))
        self.sudo().done = False
