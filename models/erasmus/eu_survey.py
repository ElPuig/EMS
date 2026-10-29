# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError

EU_SURVEY_STATES = [('pending', "Pending"), ('done', "Answered"), ('validated', "Validated")]


class EmsErasmusEuSurvey(models.AbstractModel):
    """The EU Survey (the participant report of the European Commission) a mobility answers on
    return: pending until whoever answers it says so (the participant of an individual mobility, from
    the portal; the leader teacher, or whoever the team chooses, for a group one), then validated by
    the Erasmus team, which a mobility needs to close. Used by the individual mobilities (audit D-8)
    and the group ones (issue #704); each says when it opens and who may say it is answered."""
    _name = 'ems.erasmus.eu.survey'
    _description = 'Erasmus+ EU Survey'

    eu_survey_deadline = fields.Date(string="EU Survey deadline", tracking=True)
    eu_survey_state = fields.Selection(string="EU Survey", selection=EU_SURVEY_STATES, default='pending',
                                       tracking=True, readonly=True, copy=False)

    def _ems_eu_survey_name(self):
        return self.display_name

    def _ems_eu_survey_answered(self):
        """Answered: in the chatter, and a task for the Erasmus team to validate it."""
        for record in self:
            if record.eu_survey_state != 'pending':
                raise UserError(_("The EU Survey of %s is already answered.", record._ems_eu_survey_name()))
        self.sudo().write({'eu_survey_state': 'done'})
        team = self.env['ems.erasmus.call']._ems_erasmus_team()
        for record in self:
            record.sudo().chatter(_("EU Survey answered."))
            record._ems_schedule(team, _("Erasmus+: validate the EU Survey of %s", record._ems_eu_survey_name()))

    def _ems_eu_survey_validate(self):
        for record in self:
            if record.eu_survey_state != 'done':
                raise UserError(_("The EU Survey of %s is not answered yet.", record._ems_eu_survey_name()))
        self.sudo().write({'eu_survey_state': 'validated'})

    def _ems_schedule(self, users, summary, deadline=None):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for record in self.sudo():
            for user in users:
                record.activity_schedule(activity_type_id=activity_type.id, user_id=user.id, summary=summary,
                                         **(deadline and {'date_deadline': deadline} or {}))
