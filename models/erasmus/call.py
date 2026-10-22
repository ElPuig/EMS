# -*- coding: utf-8 -*-

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .application import RANKED_STATES, SUBMITTED_STATES
from .offer import HOLDING_STATES


class EmsErasmusCall(models.Model):
    """Issue #683 - one Erasmus+ call: who can apply (its modalities' levels), when, and which
    documents it asks for. Issue #686: a call is for students or for staff (`audience`); a staff
    call has a panel that rates the mobility plans and ranks everyone in one list. See
    docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.call'
    _description = 'Erasmus+ call'
    _inherit = ['ems.base']
    _order = 'date_open desc, id desc'

    name = fields.Char(string="Name", required=True, tracking=True)
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', ondelete='restrict',
                                default=lambda self: self.env.company.current_course_id)
    audience = fields.Selection(string="Applicants", required=True, default='student', tracking=True,
                                selection=[('student', "Students"), ('staff', "Staff")],
                                help="Students apply in the modality of their level. Staff apply once, are "
                                     "ranked in one list, and the Erasmus team assigns each selected person a "
                                     "modality (project and period) afterwards.")
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False,
                             selection=[('draft', "Draft"), ('published', "Published"), ('closed', "Closed")])
    date_open = fields.Datetime(string="Applications open", required=True, tracking=True)
    date_close = fields.Datetime(string="Applications close", required=True, tracking=True)
    subsanation_deadline = fields.Datetime(string="Corrections deadline", tracking=True, copy=False,
                                           help="Until when applicants can upload the corrections asked for.")
    interview_deadline = fields.Datetime(string="Score correction deadline", tracking=True, copy=False,
                                         help="Until when evaluators can reopen and change their interviews or "
                                              "mobility plan ratings.")
    claims_deadline = fields.Datetime(string="Claims deadline", tracking=True, copy=False,
                                      help="Until when applicants can claim against the provisional resolution "
                                           "(shown to them on the portal).")
    acceptance_deadline = fields.Datetime(string="Acceptance deadline", tracking=True, copy=False,
                                          help="Until when the selected can accept the place offered when the "
                                               "definitive resolution is published.")
    min_score = fields.Float(string="Minimum score", default=50.0, tracking=True,
                             help="Score needed to be eligible. The staff call has none.")
    description = fields.Html(string="Information for applicants",
                              help="Shown on the portal above the application form.")
    rules_document = fields.Binary(string="Published call", attachment=True, copy=False)
    rules_filename = fields.Char(string="Published call file name", copy=False)
    modality_ids = fields.One2many(string="Modalities", comodel_name='ems.erasmus.call.modality',
                                   inverse_name='call_id', copy=True)
    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.call.document',
                                   inverse_name='call_id', copy=True)
    application_ids = fields.One2many(string="Applications", comodel_name='ems.erasmus.application',
                                      inverse_name='call_id')
    resolution_ids = fields.One2many(string="Resolutions", comodel_name='ems.erasmus.resolution',
                                     inverse_name='call_id')
    offer_ids = fields.One2many(string="Place offers", comodel_name='ems.erasmus.offer', inverse_name='call_id')
    claim_ids = fields.One2many(string="Claims", comodel_name='ems.erasmus.claim', inverse_name='call_id')
    panel_ids = fields.One2many(string="Panel", comodel_name='ems.erasmus.call.panel', inverse_name='call_id',
                                copy=True, help="Staff call: who rates the mobility plans (all of them rate "
                                                "every plan).")
    free_places = fields.Integer(string="Free places", compute='_compute_offers',
                                 help="Staff call: places not accepted nor offered to someone still to answer.")
    next_reserve_id = fields.Many2one(string="Next reserve", comodel_name='ems.erasmus.application',
                                      compute='_compute_offers',
                                      help="Staff call: the best-ranked reserve without an offer waiting or accepted.")
    has_final_resolution = fields.Boolean(string="Definitive resolution published",
                                          compute='_compute_has_final_resolution')
    application_count = fields.Integer(string="Number of applications", compute='_compute_application_count')
    is_accepting = fields.Boolean(string="Accepting applications", compute='_compute_is_accepting',
                                  help="Published, and the closing date has not passed yet.")

    @api.depends('application_ids')
    def _compute_application_count(self):
        counts = dict(self.env['ems.erasmus.application']._read_group(
            [('call_id', 'in', self.ids)], ['call_id'], ['__count']))
        for call in self:
            call.application_count = counts.get(call, 0)

    @api.depends('resolution_ids.state', 'resolution_ids.kind')
    def _compute_has_final_resolution(self):
        for call in self:
            call.has_final_resolution = 'definitive' in call._ems_published_resolutions().mapped('kind')

    @api.depends('audience', 'modality_ids.places', 'offer_ids.state', 'application_ids.state', 'application_ids.rank')
    def _compute_offers(self):
        """Issue #686: a staff call offers its places as one pool, whatever the modality."""
        for call in self:
            is_staff = call.audience == 'staff'
            call.free_places = is_staff and call._ems_free_places()
            call.next_reserve_id = is_staff and call._ems_next_reserve()

    @api.depends('state', 'date_open', 'date_close')
    def _compute_is_accepting(self):
        now = self._ems_now()
        for call in self:
            call.is_accepting = call.state == 'published' and call.date_open <= now < call.date_close

    @api.constrains('date_open', 'date_close')
    def _check_dates(self):
        for call in self:
            if call.date_close <= call.date_open:
                raise ValidationError(_("The call must close after it opens."))

    @api.onchange('audience')
    def _onchange_audience(self):
        self.min_score = 0.0 if self.audience == 'staff' else 50.0

    def write(self, vals):
        if 'audience' in vals and self.filtered(
                lambda call: call.audience != vals['audience'] and call.application_ids):
            raise UserError(_("A call with applications cannot change who it is for."))
        return super().write(vals)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        default = default or {}
        for call, vals in zip(self, vals_list):
            if 'name' not in default:
                vals['name'] = _("%s (copy)", call.name)
        return vals_list

    def action_publish(self):
        for call in self:
            if not call.modality_ids:
                raise UserError(_("Add at least one modality before publishing the call."))
            if call.audience == 'student' and call.modality_ids.filtered(lambda modality: not modality.level_ids):
                raise UserError(_("Every modality of a students' call needs the levels whose students apply in it."))
            if not call.document_ids.filtered(lambda document: document.requirement == 'required'):
                raise UserError(_("Add at least one required document before publishing the call."))
        self._ems_set_state('draft', 'published')

    def action_back_to_draft(self):
        if self.application_ids.filtered(lambda application: application.state != 'draft'):
            raise UserError(_("A call with submitted applications cannot go back to draft."))
        self._ems_set_state('published', 'draft')

    def action_close(self):
        """Close the applications: those never submitted stay as not submitted, and the scoring
        data of the submitted ones is frozen (issue #684)."""
        self._ems_set_state('published', 'closed')
        drafts = self.application_ids.filtered(lambda application: application.state == 'draft')
        drafts._ems_set_state('not_submitted')
        self.filtered(lambda call: call.audience == 'student').application_ids.filtered(
            lambda application: application.state in SUBMITTED_STATES)._ems_freeze_scoring_data()

    def action_send_to_panel(self):
        """Issue #686: one rating per admitted application and panel member, for those still
        without one. A member who is a candidate in the call abstains (art. 10): their rating waits
        for the substitute the Director appoints."""
        Rating = self.env['ems.erasmus.plan_rating']
        for call in self:
            if call.audience != 'staff' or call.state != 'closed':
                raise UserError(_("Only a closed staff call sends the mobility plans to the panel."))
            if not call.panel_ids:
                raise UserError(_("Add the panel members first."))
            candidates = call._ems_candidate_partners()
            vals_list = []
            for application in call.application_ids.filtered(lambda application: application.state == 'admitted'):
                rated = application.sudo().plan_rating_ids.panel_member_id
                for member in call.panel_ids.user_id - rated:
                    is_candidate = member.partner_id in candidates
                    vals_list.append({
                        'application_id': application.id, 'panel_member_id': member.id,
                        'evaluator_id': not is_candidate and member.id,
                        'abstention_reason': is_candidate and _("Candidate in this call"),
                    })
            if not vals_list:
                raise UserError(_("Every admitted application already has its ratings."))
            Rating.create(vals_list)

    def action_view_ranking(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_ranking')
        action['domain'] = [('call_id', '=', self.id), ('state', 'in', RANKED_STATES)]
        if self.audience == 'staff':
            action['views'] = [(self.env.ref('ems.view_erasmus_staff_ranking_list').id, 'list'), (False, 'form')]
        return action

    def action_offer_place(self):
        """Issue #685: offer a free place to the next reserve (the team confirms it in the wizard)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_offer_wizard')
        action['context'] = {'default_call_id': self.id}
        return action

    def action_export_participants(self):
        self.ensure_one()
        return self.application_ids.action_export_participants()

    def _ems_candidate_partners(self):
        """Who applied to this call (submitted at least once): they never rate in it."""
        self.ensure_one()
        return self.sudo().application_ids.filtered(
            lambda application: application.state not in ('draft', 'not_submitted')).partner_id

    def _ems_holding_applications(self, modality=None):
        """The applications holding a place (offer waiting or accepted), of `modality` for a
        students' call, of the whole call for a staff one."""
        self.ensure_one()
        offers = self.offer_ids.filtered(lambda offer: offer.state in HOLDING_STATES and (
            self.audience == 'staff' or offer.modality_id == modality))
        return offers.application_id

    def _ems_free_places(self, modality=None):
        self.ensure_one()
        places = sum(self.modality_ids.mapped('places')) if self.audience == 'staff' else modality.places
        return places - len(self._ems_holding_applications(modality))

    def _ems_next_reserve(self, modality=None):
        """The best-ranked reserve without a place, of `modality` (students) or the call (staff)."""
        self.ensure_one()
        holding = self._ems_holding_applications(modality)
        reserves = self.application_ids.filtered(
            lambda application: application.state == 'reserve' and application not in holding and (
                self.audience == 'staff' or application.modality_id == modality))
        return reserves.sorted('rank')[:1]

    def _ems_published_resolutions(self):
        self.ensure_one()
        return self.resolution_ids.filtered(lambda resolution: resolution.state == 'published')

    def action_view_applications(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_application')
        action['domain'] = [('call_id', '=', self.id)]
        action['context'] = {'default_call_id': self.id}
        return action

    def _ems_set_state(self, from_state, to_state):
        for call in self:
            if call.state != from_state:
                raise UserError(_("The call %s is not in the right state for this action.", call.name))
        self.write({'state': to_state})

    def _ems_now(self):
        """Now, from the centre's clock (ems.datetime_utils), as Odoo stores datetimes: naive UTC."""
        utils = self.env['ems.datetime_utils']
        return utils.datetime_to_odoo(utils.local_datetime_to_utc(utils.get_local_datetime()))

    def _ems_local_deadline(self):
        """The corrections deadline as the applicant reads it: in the centre's timezone."""
        self.ensure_one()
        return self._ems_local_format(self.subsanation_deadline)

    @api.model
    def _ems_local_format(self, value):
        """A stored (UTC) datetime as the centre reads it, for the emails."""
        if not value:
            return ''
        return self.env['ems.datetime_utils'].utc_datetime_to_local(value.replace(tzinfo=UTC)).strftime(
            '%d/%m/%Y %H:%M')

    def _ems_modality_for(self, partner):
        """The modality `partner` competes in: the one whose levels include their main group's."""
        self.ensure_one()
        level = self.audience == 'student' and partner.contact_type == 'student' and partner.main_group_id.level_id
        if not level:
            return self.env['ems.erasmus.call.modality']
        return self.modality_ids.filtered(lambda modality: level in modality.level_ids)[:1]


class EmsErasmusCallModality(models.Model):
    """A selection list of a call, with its own places (e.g. GM and GS), and the levels whose
    students compete in it."""
    _name = 'ems.erasmus.call.modality'
    _description = 'Erasmus+ call modality'
    _order = 'call_id, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    level_ids = fields.Many2many(string="Levels", comodel_name='ems.level',
                                 help="Students' call: students whose main group is of one of these levels apply in "
                                      "this modality.")
    project = fields.Selection(string="Project", selection=[('ka121_vet', "KA121-VET"), ('ka131_hed', "KA131-HED")])
    places = fields.Integer(string="Places")
    period = fields.Char(string="Period")
    destinations = fields.Char(string="Destinations")
    free_places = fields.Integer(string="Free places", compute='_compute_offers',
                                 help="Places not accepted nor offered to someone still to answer.")
    next_reserve_id = fields.Many2one(string="Next reserve", comodel_name='ems.erasmus.application',
                                      compute='_compute_offers',
                                      help="The best-ranked reserve without an offer waiting or accepted.")

    @api.depends('places', 'call_id.audience', 'call_id.offer_ids.state', 'call_id.application_ids.state',
                 'call_id.application_ids.rank')
    def _compute_offers(self):
        """Issue #685: places still to offer, and to whom EMS proposes offering the next one. A
        staff call offers its places as one pool (the call's own fields), not per modality."""
        for modality in self:
            call = modality.call_id
            is_student = call.audience == 'student'
            modality.free_places = is_student and call._ems_free_places(modality)
            modality.next_reserve_id = is_student and call._ems_next_reserve(modality)

    @api.constrains('level_ids', 'call_id')
    def _check_one_modality_per_level(self):
        for call in self.call_id:
            levels = call.modality_ids.level_ids
            if len(levels) != sum(len(modality.level_ids) for modality in call.modality_ids):
                raise ValidationError(_("A level can only belong to one modality of the call."))


class EmsErasmusCallDocument(models.Model):
    """A document the call asks applicants for."""
    _name = 'ems.erasmus.call.document'
    _description = 'Erasmus+ call document'
    _order = 'call_id, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Instructions", help="Shown to the applicant next to the upload.")
    requirement = fields.Selection(string="Requirement", required=True, default='required', selection=[
        ('required', "Required"), ('optional', "Optional"), ('minor', "Required for minors")])
    confidential = fields.Boolean(string="Confidential",
                                  help="Only the Erasmus team sees these files (e.g. evidence of fewer opportunities).")
    panel_visible = fields.Boolean(string="Shown to the panel",
                                   help="Staff call: the panel members see these files when they rate (the mobility "
                                        "plan), and nothing else of the application.")
