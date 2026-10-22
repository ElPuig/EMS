# -*- coding: utf-8 -*-

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmsErasmusCall(models.Model):
    """Issue #683 - one Erasmus+ call: who can apply (its modalities' levels), when, and which
    documents it asks for. See docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.call'
    _description = 'Erasmus+ call'
    _inherit = ['ems.base']
    _order = 'date_open desc, id desc'

    name = fields.Char(string="Name", required=True, tracking=True)
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', ondelete='restrict',
                                default=lambda self: self.env.company.current_course_id)
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False,
                             selection=[('draft', "Draft"), ('published', "Published"), ('closed', "Closed")])
    date_open = fields.Datetime(string="Applications open", required=True, tracking=True)
    date_close = fields.Datetime(string="Applications close", required=True, tracking=True)
    subsanation_deadline = fields.Datetime(string="Corrections deadline", tracking=True, copy=False,
                                           help="Until when applicants can upload the corrections asked for.")
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
    application_count = fields.Integer(string="Number of applications", compute='_compute_application_count')
    is_accepting = fields.Boolean(string="Accepting applications", compute='_compute_is_accepting',
                                  help="Published, and the closing date has not passed yet.")

    @api.depends('application_ids')
    def _compute_application_count(self):
        counts = dict(self.env['ems.erasmus.application']._read_group(
            [('call_id', 'in', self.ids)], ['call_id'], ['__count']))
        for call in self:
            call.application_count = counts.get(call, 0)

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
            if not call.document_ids.filtered(lambda document: document.requirement == 'required'):
                raise UserError(_("Add at least one required document before publishing the call."))
        self._ems_set_state('draft', 'published')

    def action_back_to_draft(self):
        if self.application_ids.filtered(lambda application: application.state != 'draft'):
            raise UserError(_("A call with submitted applications cannot go back to draft."))
        self._ems_set_state('published', 'draft')

    def action_close(self):
        """Close the applications: those never submitted stay as not submitted."""
        self._ems_set_state('published', 'closed')
        drafts = self.application_ids.filtered(lambda application: application.state == 'draft')
        drafts._ems_set_state('not_submitted')

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
        if not self.subsanation_deadline:
            return ''
        local = self.env['ems.datetime_utils'].utc_datetime_to_local(
            self.subsanation_deadline.replace(tzinfo=UTC))
        return local.strftime('%d/%m/%Y %H:%M')

    def _ems_modality_for(self, partner):
        """The modality `partner` competes in: the one whose levels include their main group's."""
        self.ensure_one()
        level = partner.contact_type == 'student' and partner.main_group_id.level_id
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
    level_ids = fields.Many2many(string="Levels", comodel_name='ems.level', required=True,
                                 help="Students whose main group is of one of these levels apply in this modality.")
    project = fields.Selection(string="Project", selection=[('ka121_vet', "KA121-VET"), ('ka131_hed', "KA131-HED")])
    places = fields.Integer(string="Places")
    period = fields.Char(string="Period")
    destinations = fields.Char(string="Destinations")

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
