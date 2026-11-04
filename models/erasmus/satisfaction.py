# -*- coding: utf-8 -*-

import statistics
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# The two indicators of the Erasmus+ quality system (ISO 9001) and the Mobilitat FP network.
SATISFACTION_TARGET = 8.5
STUDENT_INTEREST_TARGET = 5.0
# A score this low or lower asks for confirmation and for what did not work.
LOW_SCORE = 6
# Days after the survey opens to remind a student who has not answered it yet.
REMINDER_DAYS = (3, 7)
# Never a mass email at night: the hourly cron sends nothing before this hour in the centre.
SEND_HOUR = 9
STATES = [('pending', "Pending"), ('answered', "Answered"), ('not_answered', "Not answered")]
PARTICIPANT_TYPES = [
    ('student_gm', "Students, intermediate level"),
    ('student_gs', "Students, higher level"),
    ('student_specialisation', "Students, specialisation course"),
    ('student_other', "Students, other levels"),
    ('staff', "Staff"),
]
LEVEL_TYPES = {'CFGM': 'student_gm', 'CFGS': 'student_gs', 'EFPS': 'student_specialisation'}
# Who sees each participant's name: the coordinator alone (and the administrator, above everyone).
NAMES_GROUPS = 'ems.group_erasmus_coordinator,ems.group_academic_admin'
# An application counts as an applicant once submitted: a draft never sent does not.
NOT_APPLIED = ('draft', 'not_submitted')
ADMITTED = ('admitted', 'selected', 'reserve', 'not_selected', 'accepted', 'renounced')
SELECTED = ('selected', 'accepted', 'renounced')


class EmsErasmusSatisfaction(models.Model):
    """The satisfaction survey of one participant of an Erasmus+ mobility (individual, or a group
    mobility's student or teacher): one question, a score from 1 to 10, what did not work when the
    score is 6 or lower, and an optional comment. It opens on its own the day after the stay ends and
    the mobility does not close until it is answered, or the coordinator marks it as not answered.
    The Erasmus team sees every answer without the name; only the coordinator sees who answered
    what. See docs/en/developers/erasmus/quality.md."""
    _name = 'ems.erasmus.satisfaction'
    _description = 'Erasmus+ satisfaction survey'
    _order = 'open_date desc, id desc'
    _sql_constraints = [
        ('mobility_unique', 'unique(mobility_id)', "A mobility has one satisfaction survey."),
        ('participant_unique', 'unique(group_participant_id)', "A group participant has one satisfaction survey."),
        ('score_range', 'CHECK(score IS NULL OR (score >= 1 AND score <= 10))', "The score goes from 1 to 10."),
    ]

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', ondelete='cascade',
                                  index=True, readonly=True, groups=NAMES_GROUPS)
    group_participant_id = fields.Many2one(string="Group participant", comodel_name='ems.erasmus.group.participant',
                                           ondelete='cascade', index=True, readonly=True, groups=NAMES_GROUPS)
    partner_id = fields.Many2one(string="Participant", comodel_name='res.partner', required=True, readonly=True,
                                 index=True, groups=NAMES_GROUPS)
    kind = fields.Selection(string="Kind of mobility", selection=[('individual', "Individual"), ('group', "Group")],
                            required=True, readonly=True)
    participant_type = fields.Selection(string="Participant type", selection=PARTICIPANT_TYPES, required=True,
                                        readonly=True)
    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', readonly=True, index=True)
    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        readonly=True, index=True)
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', readonly=True)
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', readonly=True, index=True,
                                help="The course of the call (or of the group mobility), not the year the stay ends.")
    level_id = fields.Many2one(string="Level", comodel_name='ems.level', readonly=True)
    study_id = fields.Many2one(string="Cycle", comodel_name='ems.study', readonly=True)
    host_partner_id = fields.Many2one(string="Host entity", comodel_name='res.partner', readonly=True)
    country_id = fields.Many2one(string="Country", comodel_name='res.country', readonly=True)
    open_date = fields.Date(string="Opened on", readonly=True)
    state = fields.Selection(string="State", selection=STATES, required=True, default='pending', readonly=True,
                             index=True)
    score = fields.Integer(string="Score", readonly=True, aggregator='avg')
    is_low = fields.Boolean(string="Score of 6 or lower", compute='_compute_is_low', store=True)
    what_failed = fields.Text(string="What did not work", readonly=True)
    comment = fields.Text(string="Comment", readonly=True)
    answer_date = fields.Datetime(string="Answered on", readonly=True)
    reminder_count = fields.Integer(string="Reminders sent", readonly=True)
    not_answered_reason = fields.Text(string="Why it is closed without an answer")
    not_answered_by_id = fields.Many2one(string="Closed without an answer by", comodel_name='res.users',
                                         readonly=True)
    activity_id = fields.Many2one(string="To-do", comodel_name='mail.activity', ondelete='set null', readonly=True)
    improvement_action_id = fields.Many2one(string="Improvement action", comodel_name='ems.quality.action',
                                            readonly=True, ondelete='set null')
    improvement_state = fields.Selection(string="Improvement action state",
                                         related='improvement_action_id.state', related_sudo=True)

    @api.depends('score')
    def _compute_is_low(self):
        for survey in self:
            survey.is_low = bool(survey.score) and survey.score <= LOW_SCORE

    @api.depends('call_id', 'group_mobility_id', 'participant_type')
    def _compute_display_name(self):
        """Never the participant's name: the team reads the answers without it."""
        labels = dict(self._fields['participant_type']._description_selection(self.env))
        for survey in self:
            origin = survey.call_id or survey.group_mobility_id
            survey.display_name = f"{origin.display_name} - {labels.get(survey.participant_type, '')}"

    # --- opening, reminders and answer --------------------------------------------------------

    @api.model
    def _cron_satisfaction(self):
        """Hourly, from 9:00 in the centre: open the survey of every participant whose stay is over,
        and remind the students who have not answered it at 3 and 7 days. Staff have a to-do of
        their own instead, which their daily summary repeats every day while it is pending."""
        local_now = self.env['ems.datetime_utils'].get_local_datetime()
        if local_now.hour < SEND_HOUR:
            return
        self._ems_open_ended()
        today = local_now.date()
        for count, days in enumerate(REMINDER_DAYS):
            due = self.sudo().search([('state', '=', 'pending'), ('reminder_count', '=', count),
                                      ('open_date', '<=', today - timedelta(days=days))])
            students = due.filtered(lambda survey: not survey._ems_staff_user())
            students._ems_send_mail()
            due.write({'reminder_count': count + 1})

    @api.model
    def _ems_open_ended(self):
        """The surveys of every stay already over: an individual mobility under way whose last day
        has passed, and every active participant of a group mobility back home (or whose last day
        has passed)."""
        today = self.env['ems.datetime_utils'].get_local_today()
        mobilities = self.env['ems.erasmus.mobility'].sudo().search([
            ('state', '=', 'preparing'), ('date_end', '<', today), ('satisfaction_ids', '=', False)])
        participants = self.env['ems.erasmus.group.participant'].sudo().search([
            ('state', '=', 'active'), ('satisfaction_ids', '=', False), '|',
            ('group_mobility_id.state', '=', 'return'),
            '&', ('group_mobility_id.state', '=', 'stay'), ('group_mobility_id.date_end', '<', today)])
        return self._ems_open(mobilities, participants)

    @api.model
    def _ems_open(self, mobilities, participants):
        """Create the surveys of `mobilities` and of the group `participants` that have none, and
        tell each participant: a student by email, staff with a to-do."""
        today = self.env['ems.datetime_utils'].get_local_today()
        values = [mobility._ems_satisfaction_values() for mobility in mobilities.filtered(
            lambda mobility: not mobility.satisfaction_ids)]
        values += [participant._ems_satisfaction_values() for participant in participants.filtered(
            lambda participant: not participant.satisfaction_ids)]
        surveys = self.sudo().create([{**vals, 'open_date': today} for vals in values])
        staff = surveys.filtered(lambda survey: survey._ems_staff_user())
        (surveys - staff)._ems_send_mail()
        staff._ems_schedule_todo()
        return surveys

    @api.model
    def _ems_participant_type(self, level, staff=False):
        if staff:
            return 'staff'
        return LEVEL_TYPES.get(level.acronym, 'student_other')

    def _ems_staff_user(self):
        """The internal user of a staff participant, who gets a to-do instead of emails."""
        self.ensure_one()
        if self.participant_type != 'staff':
            return self.env['res.users']
        return self.sudo().partner_id.user_ids.filtered(lambda user: not user.share)[:1]

    def _ems_send_mail(self):
        template = self.env.ref('ems.email_template_erasmus_satisfaction').sudo()
        for survey in self.sudo().filtered('partner_id.email'):
            template.with_context(lang=survey.partner_id.lang).send_mail(
                survey.id, force_send=False, email_values={'email_to': survey.partner_id.email})

    def _ems_schedule_todo(self):
        """Staff (as with their mobility documents): a to-do on their own contact, since staff
        answer on the portal and do not open the survey in the backend."""
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for survey in self.sudo():
            user = survey._ems_staff_user()
            survey.activity_id = survey.partner_id.activity_schedule(
                activity_type_id=activity_type.id, user_id=user.id,
                summary=_("Erasmus+: answer the satisfaction survey"),
                note=Markup(_("Answer it on the portal: %s")) % Markup(
                    '<a href="{url}">{url}</a>').format(url=survey._ems_portal_url()),
                date_deadline=survey.open_date + timedelta(days=REMINDER_DAYS[-1]))

    def _ems_portal_url(self):
        self.ensure_one()
        return f"{self.get_base_url()}/my/erasmus/satisfaction/{self.id}"

    def _ems_portal_answer(self, score, what_failed=False, comment=False):
        """The participant answers on the portal. A score of 6 or lower needs what did not work."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("This survey is already answered."))
        if not isinstance(score, int) or not 1 <= score <= 10:
            raise UserError(_("Choose a score from 1 to 10."))
        what_failed = (what_failed or '').strip()
        if score <= LOW_SCORE and not what_failed:
            raise UserError(_("Tell us what did not work."))
        self.sudo().write({'state': 'answered', 'score': score, 'what_failed': what_failed or False,
                           'comment': (comment or '').strip() or False, 'answer_date': fields.Datetime.now()})
        self._ems_done()

    def action_mark_not_answered(self):
        """The coordinator closes the survey without an answer, as an exception, with the reason."""
        if not (self.env.user.has_group('ems.group_erasmus_coordinator')
                or self.env.user.has_group('ems.group_academic_admin')):
            raise AccessError(_("Only the Erasmus coordinator can close a survey without an answer."))
        for survey in self:
            if survey.state != 'pending':
                raise UserError(_("Only a pending survey can be closed without an answer."))
            if not (survey.not_answered_reason or '').strip():
                raise UserError(_("Write why it is closed without an answer first."))
        self.sudo().write({'state': 'not_answered', 'not_answered_by_id': self.env.uid})
        self._ems_done()

    def _ems_done(self):
        self.sudo().activity_id.unlink()

    def action_create_improvement(self):
        """An improvement action of the Quality app for a low score, created as the current member of
        the team (who then manages it there, like any other action), with what did not work and
        without the participant's name: it is the evidence the ISO audit asks for."""
        self.ensure_one()
        if not (self.env.user.has_group('ems.group_erasmus') or self.env.user.has_group('ems.group_academic_admin')):
            raise AccessError(_("Only the Erasmus team creates improvement actions from the surveys."))
        survey = self.sudo()
        if not survey.is_low or survey.improvement_action_id:
            raise UserError(_("An improvement action is only created once, for a score of 6 or lower."))
        labels = dict(self._fields['participant_type']._description_selection(self.env))
        details = [(_("Survey"), survey.display_name), (_("Participant type"), labels[survey.participant_type]),
                   (_("Host entity"), survey.host_partner_id.name), (_("Score"), f"{survey.score} / 10"),
                   (_("What did not work"), survey.what_failed), (_("Comment"), survey.comment)]
        description = Markup('').join(Markup("<p><strong>{}:</strong> {}</p>").format(label, value)
                                      for label, value in details if value)
        employee = self.env.user.employee_id
        # Created as the team member, who then manages it like any action of theirs; one who may not
        # create actions in the Quality app (not a teacher) leaves it to the quality committee.
        Action = self.env['ems.quality.action']
        action = (Action if Action.has_access('create') else Action.sudo()).create({
            'type': 'improvement',
            'name': _("Erasmus+ satisfaction: %s", (survey.what_failed or '').strip()[:100]),
            'description': description,
            'course_id': (survey.course_id or self.env.company.current_course_id).id,
            'responsible_employee_ids': [(6, 0, employee.ids)] if employee else False,
        })
        survey.improvement_action_id = action
        return {'type': 'ir.actions.act_window', 'res_model': 'ems.quality.action', 'res_id': action.id,
                'view_mode': 'form'}


class EmsErasmusMobility(models.Model):
    _inherit = 'ems.erasmus.mobility'

    satisfaction_ids = fields.One2many(string="Satisfaction surveys", comodel_name='ems.erasmus.satisfaction',
                                       inverse_name='mobility_id', groups=NAMES_GROUPS)
    satisfaction_state = fields.Selection(string="Satisfaction survey", selection=STATES,
                                          compute='_compute_satisfaction_state', compute_sudo=True)

    @api.depends('satisfaction_ids.state')
    def _compute_satisfaction_state(self):
        for mobility in self:
            mobility.satisfaction_state = mobility.satisfaction_ids[:1].state

    def _ems_satisfaction_values(self):
        self.ensure_one()
        staff = self.audience == 'staff'
        return {
            'mobility_id': self.id, 'partner_id': self.partner_id.id, 'kind': 'individual',
            'participant_type': self.env['ems.erasmus.satisfaction']._ems_participant_type(self.level_id, staff),
            'call_id': self.call_id.id, 'project_id': self.project_id.id, 'course_id': self.call_id.course_id.id,
            'level_id': self.level_id.id, 'study_id': not staff and self.partner_id.main_group_id.study_id.id,
            'host_partner_id': self.host_partner_id.id, 'country_id': self.country_id.id,
        }

    def _ems_portal_satisfaction(self):
        """The survey the participant still has to answer on the portal, if any."""
        self.ensure_one()
        return self.sudo().satisfaction_ids.filtered(lambda survey: survey.state == 'pending')

    def action_open_satisfaction(self):
        """The coordinator opens the survey (to close it without an answer, with the reason)."""
        self.ensure_one()
        survey = self.satisfaction_ids[:1]
        return {'type': 'ir.actions.act_window', 'res_model': 'ems.erasmus.satisfaction', 'res_id': survey.id,
                'view_mode': 'form'}

    def _ems_check_satisfaction(self):
        """Closing needs the satisfaction survey answered, or closed without an answer by the
        coordinator. A stay just over may not have it yet (the cron opens it hourly): opened here."""
        self.ensure_one()
        mobility = self.sudo()
        if not mobility.satisfaction_ids and mobility.date_end \
                and mobility.date_end < self.env['ems.datetime_utils'].get_local_today():
            self.env['ems.erasmus.satisfaction']._ems_open(mobility, self.env['ems.erasmus.group.participant'])
        if mobility.satisfaction_ids[:1].state not in ('answered', 'not_answered'):
            raise UserError(_("The satisfaction survey of %s is not answered yet: wait for the answer, or the "
                              "Erasmus coordinator closes it without an answer, with the reason.",
                              mobility.partner_id.name))


class EmsErasmusGroupParticipant(models.Model):
    _inherit = 'ems.erasmus.group.participant'

    satisfaction_ids = fields.One2many(string="Satisfaction survey", comodel_name='ems.erasmus.satisfaction',
                                       inverse_name='group_participant_id', groups=NAMES_GROUPS)

    def _ems_satisfaction_values(self):
        self.ensure_one()
        group = self.group_mobility_id
        staff = self.role != 'student'
        level = self.env['ems.level'] if staff else self.partner_id.main_group_id.level_id
        return {
            'group_participant_id': self.id, 'partner_id': self.partner_id.id, 'kind': 'group',
            'participant_type': self.env['ems.erasmus.satisfaction']._ems_participant_type(level, staff),
            'group_mobility_id': group.id, 'project_id': group.project_id.id, 'course_id': group.course_id.id,
            'level_id': level.id, 'study_id': not staff and self.partner_id.main_group_id.study_id.id,
            'host_partner_id': group.host_partner_id.id, 'country_id': group.country_id.id,
        }


class EmsErasmusGroupMobility(models.Model):
    _inherit = 'ems.erasmus.group.mobility'

    satisfaction_progress = fields.Char(string="Satisfaction surveys", compute='_compute_satisfaction_progress',
                                        compute_sudo=True,
                                        help="Answered (or closed without an answer by the coordinator) out of the "
                                             "participants' surveys.")

    @api.depends('participant_ids.satisfaction_ids.state')
    def _compute_satisfaction_progress(self):
        for mobility in self:
            surveys = mobility.participant_ids.satisfaction_ids
            done = surveys.filtered(lambda survey: survey.state != 'pending')
            mobility.satisfaction_progress = f"{len(done)} / {len(surveys)}" if surveys else False

    def action_end_stay(self):
        result = super().action_end_stay()
        self.env['ems.erasmus.satisfaction']._ems_open(
            self.env['ems.erasmus.mobility'],
            self.sudo().participant_ids.filtered(lambda participant: participant.state == 'active'))
        return result

    def _ems_check_satisfaction(self):
        """Closing needs every active participant's satisfaction survey answered, or closed without
        an answer by the coordinator."""
        self.ensure_one()
        mobility = self.sudo()
        active = mobility.participant_ids.filtered(lambda participant: participant.state == 'active')
        self.env['ems.erasmus.satisfaction']._ems_open(self.env['ems.erasmus.mobility'], active)
        if active.satisfaction_ids.filtered(lambda survey: survey.state == 'pending'):
            raise UserError(_("Every participant's satisfaction survey must be answered first, or closed without an "
                              "answer by the Erasmus coordinator, with the reason (%s).",
                              mobility.satisfaction_progress))


class EmsErasmusCall(models.Model):
    _inherit = 'ems.erasmus.call'

    # The interest indicator, frozen when the definitive resolution is published so that the history
    # never changes (later enrolments or leavers do not move it).
    interest_applicant_count = fields.Integer(string="Applicants (frozen)", readonly=True, copy=False)
    interest_target_count = fields.Integer(string="Target population (frozen)", readonly=True, copy=False)
    interest_date = fields.Datetime(string="Interest frozen on", readonly=True, copy=False)

    def _ems_interest(self):
        """(applicants, target population) of the call: who submitted an application, out of
        everybody who could apply (`_ems_eligible_partners`: the students of its levels, or the
        teachers of its FP levels plus the Direction that validates). Frozen once the definitive
        resolution is published; counted live until then."""
        self.ensure_one()
        if self.interest_date:
            return self.interest_applicant_count, self.interest_target_count
        applicants = self.sudo().application_ids.filtered(lambda application: application.state not in NOT_APPLIED)
        return len(applicants.partner_id), len(self.sudo()._ems_eligible_partners())

    def _ems_freeze_interest(self):
        for call in self.sudo().filtered(lambda call: not call.interest_date):
            applicants, target = call._ems_interest()
            call.write({'interest_applicant_count': applicants, 'interest_target_count': target,
                        'interest_date': fields.Datetime.now()})


class EmsErasmusResolution(models.Model):
    _inherit = 'ems.erasmus.resolution'

    def _ems_after_publish(self):
        result = super()._ems_after_publish()
        if self.kind == 'definitive' and self.call_id:
            self.call_id._ems_freeze_interest()
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _ems_erasmus_satisfaction_pending(self):
        """The satisfaction surveys this person still has to answer."""
        self.ensure_one()
        return self.env['ems.erasmus.satisfaction'].sudo().search([('partner_id', '=', self.id),
                                                                    ('state', '=', 'pending')])

    def _ems_erasmus_portal_visible(self):
        return super()._ems_erasmus_portal_visible() or bool(self._ems_erasmus_satisfaction_pending())


class EmsErasmusQualityPanel(models.TransientModel):
    """Erasmus+ › Quality: the two indicators (interest, satisfaction) with their target, the
    response rate, the satisfaction by participant type and by host entity, each call's funnel and
    the evolution by course, for the filters chosen. Only totals and averages: never a name. The
    figures are computed on the fly from the surveys and the calls (a few hundred records at most)."""
    _name = 'ems.erasmus.quality.panel'
    _description = 'Erasmus+ quality panel'

    course_id = fields.Many2one(string="Course", comodel_name='ems.course')
    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call')
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project')
    participant_type = fields.Selection(string="Participant type", selection=PARTICIPANT_TYPES)
    study_id = fields.Many2one(string="Cycle", comodel_name='ems.study')
    host_partner_id = fields.Many2one(string="Host entity", comodel_name='res.partner',
                                      domain="[('is_erasmus_host', '=', True)]")
    indicators_html = fields.Html(string="Indicators", compute='_compute_panel', sanitize=False)
    breakdown_html = fields.Html(string="Satisfaction breakdown", compute='_compute_panel', sanitize=False)
    funnel_html = fields.Html(string="Calls", compute='_compute_panel', sanitize=False)
    evolution_html = fields.Html(string="Evolution by course", compute='_compute_panel', sanitize=False)

    @api.depends('course_id', 'call_id', 'project_id', 'participant_type', 'study_id', 'host_partner_id')
    def _compute_panel(self):
        self._ems_check_access()
        for panel in self:
            data = panel._ems_data()
            panel.indicators_html = panel._ems_table(
                [_("Indicator"), _("Value"), _("Target"), _("Met"), _("n"), _("Median")],
                [panel._ems_indicator_row(row) for row in data['indicators']])
            panel.breakdown_html = Markup('').join([
                Markup("<h5>{}</h5>").format(_("By participant type")),
                panel._ems_table([_("Participant type"), _("Average"), _("Median"), _("n")], data['by_type']),
                Markup("<h5>{}</h5>").format(_("By host entity")),
                panel._ems_table([_("Host entity"), _("Average"), _("Median"), _("n")], data['by_host']),
            ])
            panel.funnel_html = panel._ems_table(
                [_("Call"), _("Cycle"), _("Applications"), _("Admitted"), _("With a place"), _("Mobilities done"),
                 _("Renounced or cancelled")], data['funnel'])
            panel.evolution_html = panel._ems_table(
                [_("Course"), _("Student interest"), _("Staff interest"), _("Satisfaction"), _("n")],
                data['evolution'])

    def _ems_check_access(self):
        if not (self.env.user.has_group('ems.group_erasmus') or self.env.user.has_group('ems.group_academic_admin')):
            raise AccessError(_("Only the Erasmus team sees the quality panel."))

    # --- figures ---------------------------------------------------------------------------------

    def _ems_survey_domain(self, course=True):
        domain = []
        for name in ('call_id', 'project_id', 'study_id', 'host_partner_id') + (('course_id',) if course else ()):
            if self[name]:
                domain.append((name, '=', self[name].id))
        if self.participant_type:
            domain.append(('participant_type', '=', self.participant_type))
        return domain

    def _ems_calls(self, course=True):
        """The calls the interest is computed on: the call chosen, or those of the course. A
        participant type narrows it to the students' or the staff's calls."""
        domain = [('state', '!=', 'draft')]
        if self.call_id:
            domain.append(('id', '=', self.call_id.id))
        if course and self.course_id:
            domain.append(('course_id', '=', self.course_id.id))
        if self.participant_type:
            domain.append(('audience', '=', 'staff' if self.participant_type == 'staff' else 'student'))
        return self.env['ems.erasmus.call'].sudo().search(domain)

    @api.model
    def _ems_stats(self, scores):
        """(average, median, n) of a list of scores, None for an empty one."""
        if not scores:
            return None, None, 0
        return statistics.fmean(scores), statistics.median(scores), len(scores)

    @api.model
    def _ems_interest(self, calls):
        """Applicants out of the target population of `calls`, as a percentage, and both counts."""
        applicants = target = 0
        for call in calls:
            call_applicants, call_target = call._ems_interest()
            applicants += call_applicants
            target += call_target
        return (100.0 * applicants / target if target else None), applicants, target

    def _ems_data(self):
        """Every figure of the panel as plain values, shared by the panel and its export."""
        self.ensure_one()
        Survey = self.env['ems.erasmus.satisfaction'].sudo()
        surveys = Survey.search(self._ems_survey_domain())
        answered = surveys.filtered(lambda survey: survey.state == 'answered')
        calls = self._ems_calls()
        student_rate, student_applicants, student_target = self._ems_interest(
            calls.filtered(lambda call: call.audience == 'student'))
        staff_rate, staff_applicants, staff_target = self._ems_interest(
            calls.filtered(lambda call: call.audience == 'staff'))
        average, median, count = self._ems_stats(answered.mapped('score'))
        indicators = [
            {'name': _("Student interest"), 'value': student_rate, 'unit': '%', 'target': STUDENT_INTEREST_TARGET,
             'n': f"{student_applicants} / {student_target}"},
            {'name': _("Staff interest"), 'value': staff_rate, 'unit': '%', 'target': None,
             'n': f"{staff_applicants} / {staff_target}"},
            {'name': _("Satisfaction (1-10)"), 'value': average, 'unit': '', 'target': SATISFACTION_TARGET,
             'n': count, 'median': median},
            {'name': _("Survey response rate"), 'value': 100.0 * len(answered) / len(surveys) if surveys else None,
             'unit': '%', 'target': None, 'n': f"{len(answered)} / {len(surveys)}"},
        ]
        labels = dict(Survey._fields['participant_type']._description_selection(self.env))
        by_type = [self._ems_stats_row(labels[key], answered.filtered(lambda survey: survey.participant_type == key))
                   for key in labels if answered.filtered(lambda survey, key=key: survey.participant_type == key)]
        by_host = [self._ems_stats_row(host.name or _("Not set"), group)
                   for host, group in answered.grouped('host_partner_id').items()]
        return {
            'indicators': indicators, 'by_type': by_type,
            'by_host': sorted(by_host, key=lambda row: str(row[0])),
            'funnel': self._ems_funnel(calls), 'evolution': self._ems_evolution(),
            'surveys': surveys,
        }

    def _ems_stats_row(self, label, surveys):
        average, median, count = self._ems_stats(surveys.mapped('score'))
        return [label, self._ems_number(average), self._ems_number(median), count]

    def _ems_funnel(self, calls):
        """Each call's way from the applications to the mobilities done, in total and by cycle
        (the study of the applicant's group; staff have none)."""
        rows = []
        Mobility = self.env['ems.erasmus.mobility'].sudo()
        for call in calls.sorted(lambda call: (call.course_id.name or '', call.name or '')):
            applications = call.sudo().application_ids.filtered(
                lambda application: application.state not in NOT_APPLIED)
            mobilities = Mobility.search([('call_id', '=', call.id)])
            by_study = applications.grouped(lambda application: application.partner_id.main_group_id.study_id)
            groups = [(_("Total"), applications)]
            if call.audience == 'student' and len(by_study) > 1:
                groups += sorted(((study.acronym or study.name or _("Not set"), group)
                                  for study, group in by_study.items()), key=lambda item: str(item[0]))
            for label, group in groups:
                group_mobilities = mobilities.filtered(lambda mobility: mobility.application_id in group)
                rows.append([
                    call.name if label == _("Total") else '', label, len(group),
                    len(group.filtered(lambda application: application.state in ADMITTED)),
                    len(group.filtered(lambda application: application.state in SELECTED)),
                    len(group_mobilities.filtered(lambda mobility: mobility.state == 'done')),
                    len(group.filtered(lambda application: application.state == 'renounced'))
                    + len(group_mobilities.filtered(lambda mobility: mobility.state == 'cancelled')),
                ])
        return rows

    def _ems_evolution(self):
        """The two indicators course by course (every course with a call or a survey), with the
        filters other than the course."""
        Survey = self.env['ems.erasmus.satisfaction'].sudo()
        answered = Survey.search(self._ems_survey_domain(course=False) + [('state', '=', 'answered')])
        calls = self._ems_calls(course=False)
        courses = (answered.course_id | calls.course_id).sorted('name')
        rows = []
        for course in courses:
            course_calls = calls.filtered(lambda call: call.course_id == course)
            student_rate = self._ems_interest(course_calls.filtered(lambda call: call.audience == 'student'))[0]
            staff_rate = self._ems_interest(course_calls.filtered(lambda call: call.audience == 'staff'))[0]
            average, _median, count = self._ems_stats(
                answered.filtered(lambda survey: survey.course_id == course).mapped('score'))
            rows.append([course.name, self._ems_number(student_rate, '%'), self._ems_number(staff_rate, '%'),
                         self._ems_number(average), count])
        return rows

    # --- rendering -------------------------------------------------------------------------------

    @api.model
    def _ems_number(self, value, unit=''):
        if value is None:
            return '-'
        return f"{value:.1f}{' ' + unit if unit else ''}".replace('.', ',')

    def _ems_indicator_row(self, row):
        value, target = row['value'], row['target']
        met = '-' if value is None or target is None else (_("Yes") if value > target else _("No"))
        return [row['name'], self._ems_number(value, row['unit']),
                f"> {self._ems_number(target, row['unit'])}" if target is not None else '-',
                met, row['n'], self._ems_number(row.get('median'))]

    @api.model
    def _ems_table(self, header, rows):
        if not rows:
            return Markup('<p class="text-muted">{}</p>').format(_("No data yet."))
        head = Markup('').join(Markup('<th>{}</th>').format(cell) for cell in header)
        body = Markup('').join(
            Markup('<tr>{}</tr>').format(Markup('').join(Markup('<td>{}</td>').format(escape(cell)) for cell in row))
            for row in rows)
        return Markup('<table class="table table-sm table-striped o_ems_erasmus_quality_table">'
                      '<thead><tr>{}</tr></thead><tbody>{}</tbody></table>').format(head, body)
