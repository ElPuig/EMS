# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, format_datetime



STEP_CODES = [
    ('tutor_contact', 'Contact with the family'),
    ('coexistence_contact', 'Contact by Coexistence'),
    ('secretariat_notice', 'Notice to the family'),
    ('social_services', 'Notice to Social Services'),
    ('secretariat_warning', 'Ex officio withdrawal warning'),
    ('direction_approval', 'Green light from Direction'),
    ('withdrawal', 'Withdrawal'),
]

RESPONSIBLES = [
    ('tutor', 'Tutor'),
    ('coexistence', 'Coexistence or management team'),
    ('secretariat', 'Secretariat'),
    ('direction', 'Direction'),
]

# The protocols a case file can follow, and the one each educational stage of the student's level
# (ems.level.education_stage) follows.
CIRCUITS = [
    ('compulsory', 'Compulsory education'),
    ('post_compulsory', 'Post-compulsory education'),
]
CIRCUIT_BY_STAGE = {'compulsory': 'compulsory', 'post_compulsory': 'post_compulsory'}

# What a step can ask its responsible to confirm, each with the day it was done.
CHECK_CODES = [
    ('phone', 'Phone call to the family'),
    ('family_email', 'Email to the family'),
    ('enotum', 'eNotum'),
    ('esfera', 'Registered in Esfera'),
    ('saga', 'Registered in SAGA'),
    ('social_services_email', 'Email to Social Services'),
    ('inspection_email', 'Email to the Inspection'),
    ('approval', 'Green light to the withdrawal'),
]

# The protocol of each circuit, as Direction validated it (issue #726, 2026-11-03): step code,
# responsible, deadline from the first day of absence and what it asks to confirm (a phone call
# always where the protocol asks for contact; an email to the family where it asks to write). A
# deadline is either {'school_days': N} (the N-th school day of absence, the first one included)
# or relativedelta keywords (calendar days and months). See _ems_due_date().
STEP_CATALOG = {
    # Resolució EDF/293/2026, 8.6: the place is lost after 15 days. Counted in school days, so
    # nobody ever gets less margin than the regulation gives.
    'post_compulsory': (
        ('tutor_contact', 'tutor', {'school_days': 5}, ('phone',)),
        ('secretariat_warning', 'secretariat', {'school_days': 10}, ('family_email', 'enotum')),
        ('direction_approval', 'direction', {'school_days': 15}, ('approval',)),
        ('withdrawal', 'secretariat', {'school_days': 15}, ('esfera', 'saga', 'enotum', 'family_email')),
    ),
    # Two months, in calendar days, as the communication plan says.
    'compulsory': (
        ('tutor_contact', 'tutor', {'days': 7}, ('phone',)),
        ('coexistence_contact', 'coexistence', {'days': 15}, ('phone',)),
        ('secretariat_notice', 'secretariat', {'months': 1}, ('family_email',)),
        ('social_services', 'coexistence', {'months': 1}, ('social_services_email',)),
        ('secretariat_warning', 'secretariat', {'months': 1, 'days': 15}, ('family_email', 'enotum')),
        ('direction_approval', 'direction', {'months': 2}, ('approval', 'inspection_email')),
        ('withdrawal', 'secretariat', {'months': 2}, ('esfera',)),
    ),
}


def _check_sentences():
    """What the responsible confirms by ticking each check, followed by its date."""
    return {
        'phone': _("I confirm I phoned the family (or the student, if of age) on"),
        'family_email': _("I confirm I emailed the family (or the student, if of age) on"),
        'enotum': _("I confirm I sent the eNotum on"),
        'esfera': _("I confirm I registered the withdrawal in Esfera on"),
        'saga': _("I confirm I registered the withdrawal in SAGA on"),
        'social_services_email': _("I confirm I emailed Social Services on"),
        'inspection_email': _("I confirm I emailed the Inspection the procedure followed on"),
        'approval': _("I give the green light to the ex officio withdrawal on"),
    }


def _step_instructions(circuit, code):
    """What the responsible of a step has to do, in their language."""
    compulsory = circuit == 'compulsory'
    if code == 'tutor_contact':
        if compulsory:
            return _("Phone the family to find out why the student has stopped coming and remind them that "
                     "schooling is compulsory.")
        return _("Phone the family, or the student if they are of age, to find out why they have stopped "
                 "coming. If the student is not going to continue, urge them to request a voluntary withdrawal "
                 "at the secretariat.")
    if code == 'coexistence_contact':
        return _("Phone the family again: the student is still not coming two weeks after their first absence. "
                 "Write down in the notes what they tell you.")
    if code == 'secretariat_notice':
        return _("Email the family: the student has not come for a month, schooling is compulsory and they "
                 "must contact the centre.")
    if code == 'social_services':
        return _("Email Social Services that the student has not come since their first day of absence, "
                 "with what the centre has done so far.")
    if code == 'secretariat_warning':
        if compulsory:
            return _("Warn the family by email and eNotum: if the student does not come back within fifteen "
                     "days, the centre will process the ex officio withdrawal.")
        return _("Warn the family, or the student if they are of age, by email and eNotum: if they do not come "
                 "back, the centre will process the ex officio withdrawal. If they are not going to continue, "
                 "urge them to request a voluntary withdrawal instead.")
    if code == 'direction_approval':
        if compulsory:
            return _("Check in the history that every step was done and the student is still not coming. If so, "
                     "give the green light to the ex officio withdrawal and email the Inspection the procedure "
                     "followed. The Secretariat will then process it.")
        return _("Check in the history that every step was done and the student is still not coming. If so, "
                 "give the green light to the ex officio withdrawal. The Secretariat will then process it.")
    if compulsory:
        return _("Process the ex officio withdrawal in Esfera.")
    return _("Process the ex officio withdrawal in Esfera and SAGA, notify it through eNotum and email the "
             "family, or the student if they are of age.")

OPEN_STATES = ('proposal', 'in_progress', 'direction', 'secretariat')
# The states whose current step is somebody's task: the procedure has started.
STARTED_STATES = ('in_progress', 'direction', 'secretariat')
# The state a started case file is in while its current step is one of these.
STATE_BY_STEP = {'direction_approval': 'direction', 'withdrawal': 'secretariat'}

PROPOSAL_TASK = 'ems.mail_activity_ex_officio_withdrawal_proposal'
STEP_TASK = 'ems.mail_activity_ex_officio_withdrawal_step'

# A school-day deadline never reaches further than this many calendar days per school day
# (weekends plus the longest break), the window the holidays are read for in one search.
SCHOOL_DAY_WINDOW_FACTOR = 2
SCHOOL_DAY_WINDOW_MARGIN = 120


class EmsExOfficioWithdrawal(models.Model):
    """Case file of an ex officio withdrawal (issue #726): a student who stopped coming, the
    protocol's steps and who did each of them. See docs/en/developers/contacts/ex_officio_withdrawal.md."""
    _name = 'ems.ex_officio_withdrawal'
    _description = "Ex officio withdrawal case file"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'first_absence_date desc, id desc'

    name = fields.Char(string="Case file", readonly=True, copy=False, index=True)
    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 ondelete='restrict', index=True, tracking=True,
                                 domain="[('contact_type', '=', 'student')]")
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', readonly=True, ondelete='restrict',
                                default=lambda self: self.env.company.current_course_id)
    group_id = fields.Many2one(string="Group", comodel_name='ems.group', readonly=True, ondelete='set null')
    level_id = fields.Many2one(string="Level", comodel_name='ems.level', readonly=True, ondelete='restrict')
    circuit = fields.Selection(string="Circuit", selection=CIRCUITS, readonly=True)
    tutor_id = fields.Many2one(string="Tutor", related='student_id.tutor_id')
    first_absence_date = fields.Date(string="First day of absence", required=True, tracking=True,
                                     help="The deadlines of every step count from this day.")
    origin = fields.Selection(string="Origin", readonly=True, default='manual', selection=[
        ('manual', 'Opened by hand'),
        ('detected', 'Detected in the roll-calls'),
    ])
    state = fields.Selection(string="State", default='proposal', required=True, readonly=True, index=True,
                             copy=False, tracking=True, selection=[
                                 ('proposal', 'Proposal'),
                                 ('in_progress', 'In progress'),
                                 ('direction', 'Pending Direction'),
                                 ('secretariat', 'Pending the Secretariat'),
                                 ('done', 'Withdrawn'),
                                 ('cancelled', 'Cancelled'),
                             ])
    cancel_reason = fields.Selection(string="Cancel reason", readonly=True, copy=False, selection=[
        ('dismissed', 'Dismissed by the tutor'),
        ('came_back', 'The student came back'),
        ('justified', 'Absences justified'),
        ('voluntary', 'Voluntary withdrawal'),
    ])
    cancel_note = fields.Text(string="Cancel note", readonly=True, copy=False)
    step_ids = fields.One2many(string="Steps", comodel_name='ems.ex_officio_withdrawal.step',
                               inverse_name='withdrawal_id')
    current_step_id = fields.Many2one(string="Current step", comodel_name='ems.ex_officio_withdrawal.step',
                                      compute='_compute_current_step_id', store=True)
    next_due_date = fields.Date(string="Next deadline", related='current_step_id.due_date')
    can_decide_proposal = fields.Boolean(string="Can decide the proposal", compute='_compute_can_decide_proposal')
    can_accept_step = fields.Boolean(string="Can do the current step", compute='_compute_can_accept_step')
    # Whether the current step's day has come: before it, its block is read-only and has no button.
    current_step_open = fields.Boolean(string="Current step open", compute='_compute_current_step_open')
    # The block of whoever does the current step: what to do and by when, what to confirm (each
    # check with its date, saved as they go) and their notes. Everybody else gets one line saying
    # whose turn it is. The history replaces the steps list: read-only, done and pending steps.
    current_check_ids = fields.One2many(string="To confirm", comodel_name='ems.ex_officio_withdrawal.check',
                                        inverse_name='withdrawal_id', domain=[('is_current', '=', True)])
    current_step_notes = fields.Text(string="Notes", related='current_step_id.notes', readonly=False)
    current_step_instructions = fields.Html(string="What to do", compute='_compute_current_step_texts',
                                            sanitize=False)
    waiting_message = fields.Char(string="Whose turn it is", compute='_compute_current_step_texts')
    history_html = fields.Html(string="History", compute='_compute_history_html', sanitize=False)
    # The student picker of a new case file (the view's domain="student_domain"): a tutor is only
    # offered their own students, and nobody a student whose level has no circuit.
    student_domain = fields.Char(string="Student domain", compute='_compute_student_domain')

    @api.depends('step_ids.done_date', 'step_ids.due_date')
    def _compute_current_step_id(self):
        for withdrawal in self:
            step = withdrawal.step_ids.filtered(lambda pending: not pending.done_date)[:1]
            withdrawal.current_step_id = step

    @api.depends('student_id', 'state')
    @api.depends_context('uid')
    def _compute_can_decide_proposal(self):
        """The student's tutor and the chain above them (tutor scope), the Head of Studies (and
        the Director, who implies it), and the administrators, always on top."""
        manages = self._ems_user_manages()
        base = self.env['ems.base']
        for withdrawal in self:
            withdrawal.can_decide_proposal = withdrawal.state == 'proposal' and (
                manages or base.user_acts_as_tutor(withdrawal.student_id.sudo().tutor_id))

    @api.depends('state', 'current_step_id')
    @api.depends_context('uid')
    def _compute_can_accept_step(self):
        """The current step's responsible, except for the withdrawal itself, which is made from
        the student's withdrawal wizard."""
        for withdrawal in self:
            step = withdrawal.current_step_id
            withdrawal.can_accept_step = (withdrawal.state in STARTED_STATES and bool(step)
                                          and step.code != 'withdrawal'
                                          and withdrawal._ems_user_acts_as(step.responsible))

    @api.depends('current_step_id.due_date')
    def _compute_current_step_open(self):
        for withdrawal in self:
            withdrawal.current_step_open = withdrawal._ems_current_step_open()

    def _ems_current_step_open(self):
        """Whether the current step's day has come (read fresh, for the server-side checks)."""
        self.ensure_one()
        due = self.current_step_id.due_date
        return bool(due) and due <= self.env['ems.datetime_utils'].get_local_today()

    @api.depends('state', 'current_step_id', 'step_ids.due_date')
    @api.depends_context('uid', 'lang')
    def _compute_current_step_texts(self):
        """The current step's instructions and time frame for whoever does it; one line on whose
        turn it is for everybody else."""
        today = self.env['ems.datetime_utils'].get_local_today()
        responsibles = dict(self.env['ems.ex_officio_withdrawal.step']._fields['responsible']
                            ._description_selection(self.env))
        codes = dict(self.env['ems.ex_officio_withdrawal.step']._fields['code']._description_selection(self.env))
        for withdrawal in self:
            withdrawal.current_step_instructions = False
            withdrawal.waiting_message = False
            step = withdrawal.current_step_id
            if withdrawal.state == 'proposal' and not withdrawal.can_decide_proposal:
                withdrawal.waiting_message = _("Proposal: the tutor decides whether to start the procedure.")
            if withdrawal.state not in STARTED_STATES or not step:
                continue
            due = format_date(self.env, step.due_date)
            if not withdrawal.can_accept_step:
                withdrawal.waiting_message = _("Now it is the turn of %(responsible)s: %(step)s, from %(date)s.",
                                               responsible=responsibles[step.responsible],
                                               step=codes[step.code], date=due)
                continue
            later = withdrawal.step_ids.filtered(lambda other: other.sequence > step.sequence
                                                 and other.due_date > step.due_date)[:1]
            if later:
                frame = _("Do it from %(start)s and before %(end)s, when the next step is due.",
                          start=due, end=format_date(self.env, later.due_date))
            else:
                frame = _("Do it from %(start)s.", start=due)
            if step.due_date > today:
                status = _("It cannot be done yet: it opens on %(date)s.", date=due)
            elif later and later.due_date <= today:
                status = _("It is late: the next step was due on %(date)s. The following steps will be moved, so "
                           "every wait the protocol sets is kept.", date=format_date(self.env, later.due_date))
            else:
                status = False
            help_line = _("Tick each action as you do it and save: you can do it in several goes. "
                          "\"Accept and continue\" (Actions menu) hands the case file over once every one is ticked.")
            withdrawal.current_step_instructions = Markup(
                "<p><strong>{step}</strong></p><p>{what}</p><p>{frame}</p>{status}{help}"
            ).format(step=codes[step.code], what=_step_instructions(withdrawal.circuit, step.code), frame=frame,
                     status=Markup("<p class='text-danger'>{}</p>").format(status) if status else '',
                     help=Markup("<p class='text-muted'>{}</p>").format(help_line)
                     if step.due_date <= today else '')

    @api.depends('step_ids.done_date', 'step_ids.due_date', 'step_ids.notes', 'step_ids.check_ids.done',
                 'step_ids.check_ids.date')
    @api.depends_context('lang')
    def _compute_history_html(self):
        """Every step in order: when it is due (with the protocol's day when a late step moved it)
        and when it was really done, by whom, what was confirmed and the notes; the pending ones
        greyed out."""
        responsibles = dict(self.env['ems.ex_officio_withdrawal.step']._fields['responsible']
                            ._description_selection(self.env))
        codes = dict(self.env['ems.ex_officio_withdrawal.step']._fields['code']._description_selection(self.env))
        check_labels = dict(self.env['ems.ex_officio_withdrawal.check']._fields['code']
                            ._description_selection(self.env))
        tz = str(self.env['ems.datetime_utils'].current_tz())
        for withdrawal in self:
            if not withdrawal.step_ids:
                withdrawal.history_html = False
                continue
            current = withdrawal.current_step_id
            rows = []
            for step in withdrawal.step_ids:
                checks = Markup("<br/>").join(
                    Markup("{label}: {date}").format(label=check_labels[check.code],
                                                      date=format_date(self.env, check.date))
                    for check in step.check_ids if check.done)
                if step.done_date:
                    icon, css = Markup("<i class='fa fa-check text-success' title='Done'/>"), ''
                    who = _("%(date)s, %(user)s",
                            date=format_datetime(self.env, step.done_date, tz=tz, dt_format='short'),
                            user=step.done_by_id.name)
                else:
                    is_current = step == current
                    icon = Markup("<i class='fa fa-arrow-right text-warning' title='Current'/>") if is_current \
                        else Markup("<i class='fa fa-circle-o text-muted' title='Pending'/>")
                    css = 'fw-bold' if is_current else 'text-muted'
                    who = ''
                notes = Markup("<br/><em>{}</em>").format(step.notes) if step.notes else ''
                due = format_date(self.env, step.due_date)
                if step.planned_date and step.planned_date != step.due_date:
                    due = Markup("{due}<br/><small class='text-muted'>{protocol}</small>").format(
                        due=due, protocol=_("protocol: %s", format_date(self.env, step.planned_date)))
                rows.append(Markup(
                    "<tr class='{css}'><td>{icon}</td><td>{date}</td><td>{step}</td><td>{responsible}</td>"
                    "<td>{who}</td><td>{checks}{notes}</td></tr>"
                ).format(css=css, icon=icon, date=due, step=codes[step.code],
                         responsible=responsibles[step.responsible], who=who, checks=checks, notes=notes))
            withdrawal.history_html = Markup(
                "<table class='table table-sm o_ems_withdrawal_history'><thead><tr><th/><th>{date}</th><th>{step}</th>"
                "<th>{responsible}</th><th>{done}</th><th>{what}</th></tr></thead><tbody>{rows}</tbody></table>"
            ).format(date=_("Due"), step=_("Step"), responsible=_("Responsible"), done=_("Done"),
                     what=_("What was done"), rows=Markup("").join(rows))

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_student_domain(self):
        domain = [('contact_type', '=', 'student'),
                  '|', ('main_group_id.level_id.education_stage', 'in', list(CIRCUIT_BY_STAGE)),
                  ('main_group_id.study_id.level_id.education_stage', 'in', list(CIRCUIT_BY_STAGE))]
        if not self._ems_user_manages():
            domain.append(('tutor_id.tutor_scope_user_ids', '=', self.env.uid))
        for withdrawal in self:
            withdrawal.student_domain = str(domain)

    @api.constrains('student_id', 'state')
    def _check_one_open_per_student(self):
        for withdrawal in self.filtered(lambda record: record.state in OPEN_STATES):
            if self.sudo().search_count([('student_id', '=', withdrawal.student_id.id),
                                         ('state', 'in', OPEN_STATES), ('id', '!=', withdrawal.id)]):
                raise ValidationError(_("%(student)s already has an open ex officio withdrawal case file.",
                                        student=withdrawal.student_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        students = self.env['res.partner'].browse([vals['student_id'] for vals in vals_list]).sudo()
        for vals, student in zip(vals_list, students):
            group = student.main_group_id
            level = group.study_id.level_id or group.level_id
            circuit = self._ems_circuit_for_level(level)
            if not circuit:
                raise UserError(_("%(student)s's level is not of compulsory nor post-compulsory education: no ex "
                                  "officio withdrawal protocol applies to it.", student=student.display_name))
            vals.update({'group_id': group.id, 'level_id': level.id, 'circuit': circuit})
        withdrawals = super().create(vals_list)
        for withdrawal in withdrawals:
            withdrawal.sudo().name = self.env['ems.base'].next_course_number(
                'ems.ex_officio_withdrawal', "Ex officio withdrawals", 'BO', withdrawal.course_id)
            withdrawal._ems_schedule_task(PROPOSAL_TASK, withdrawal._ems_responsible_users('tutor'),
                                          self.env['ems.datetime_utils'].get_local_today())
        return withdrawals

    def write(self, vals):
        if not self.env.su:
            if 'state' in vals or 'student_id' in vals:
                raise UserError(_("The student and the state of a case file only change through its buttons."))
            if 'first_absence_date' in vals and self.filtered(lambda withdrawal: withdrawal.state != 'proposal'):
                raise UserError(_("The first day of absence can only change while the case file is a proposal."))
        return super().write(vals)

    def action_start(self):
        """Start the procedure: the circuit's steps are created with their deadlines."""
        self._ems_check_can_decide_proposal()
        Step = self.env['ems.ex_officio_withdrawal.step'].sudo()
        for withdrawal in self:
            Step.create([{
                'withdrawal_id': withdrawal.id,
                'sequence': index,
                'code': code,
                'responsible': responsible,
                'planned_date': withdrawal._ems_due_date(deadline),
                'due_date': withdrawal._ems_due_date(deadline),
                'check_ids': [(0, 0, {'sequence': position, 'code': check}) for position, check in enumerate(checks)],
            } for index, (code, responsible, deadline, checks) in enumerate(STEP_CATALOG[withdrawal.circuit])])
        self._ems_close_tasks()
        self._ems_move_on()

    def action_open_dismiss_wizard(self):
        self.ensure_one()
        self._ems_check_can_decide_proposal()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Dismiss the proposal"),
            'res_model': 'ems.ex_officio_withdrawal.dismiss_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_withdrawal_id': self.id},
        }

    def action_dismiss(self, note):
        """The tutor dismisses the proposal, saying why."""
        self._ems_check_can_decide_proposal()
        self.sudo().write({'state': 'cancelled', 'cancel_reason': 'dismissed', 'cancel_note': note})
        self._ems_close_tasks()
        for withdrawal in self:
            withdrawal._message_log(body=_("Proposal dismissed: %(note)s", note=note))

    def action_accept_step(self):
        """The current step is done: never before its day, and only with every off-EMS action it
        asks for ticked. Done late, it moves the following steps so the protocol's waits are kept
        (counted from today, the day it is accepted). The next step's task is scheduled on its day."""
        today = self.env['ems.datetime_utils'].get_local_today()
        for withdrawal in self:
            step = withdrawal.current_step_id
            if not withdrawal.can_accept_step:
                raise UserError(_("Only the responsible of the current step can do it."))
            if step.due_date > today:
                raise UserError(_("This step is due on %(date)s: it cannot be done before.",
                                  date=format_date(self.env, step.due_date)))
            labels = dict(step.check_ids._fields['code']._description_selection(self.env))
            missing = [labels[check.code] for check in step.check_ids if not check.done]
            if missing:
                raise UserError(_("Tick what this step asks for first: %s", ", ".join(missing)))
            step.sudo().write({'done_by_id': self.env.uid, 'done_date': fields.Datetime.now()})
            withdrawal._ems_shift_pending_steps(step, today)
            lines = [_("Step done: %s", dict(step._fields['code']._description_selection(self.env))[step.code])]
            lines += [f"{labels[check.code]}: {format_date(self.env, check.date)}" for check in step.check_ids]
            if step.notes:
                lines.append(step.notes)
            withdrawal._message_log(body=Markup("<br/>").join(lines))
        self._ems_close_tasks()
        self._ems_move_on()

    @api.model
    def _cron_ems_due_step_tasks(self):
        """Schedule the task of every current step whose day has come. Hourly, so a step is
        somebody's task shortly after midnight of its day, whatever the server's time zone."""
        today = self.env['ems.datetime_utils'].get_local_today()
        steps = self.env['ems.ex_officio_withdrawal.step'].search([
            ('done_date', '=', False), ('task_scheduled', '=', False), ('due_date', '<=', today),
            ('withdrawal_id.state', 'in', STARTED_STATES)])
        steps.withdrawal_id._ems_move_on()

    def _ems_move_on(self):
        """Bring started case files up to date with their current step: the state it belongs to,
        and its responsible's task once its day has come."""
        today = self.env['ems.datetime_utils'].get_local_today()
        for withdrawal in self.sudo():
            step = withdrawal.current_step_id
            state = STATE_BY_STEP.get(step.code, 'in_progress')
            if withdrawal.state != state:
                withdrawal.state = state
            if step and not step.task_scheduled and step.due_date <= today:
                step.task_scheduled = True
                withdrawal._ems_schedule_task(STEP_TASK, withdrawal._ems_responsible_users(step.responsible),
                                              step.due_date, step)

    def _ems_responsible_users(self, responsible):
        """Who a step's (or the proposal's) task goes to: the student's tutor; the Coexistence
        coordinator under the tutor's Head or Deputy Head of Studies (every coordinator when none
        is); the whole secretariat; the Director."""
        self.ensure_one()
        base = self.env['ems.base']
        tutor = self.student_id.sudo().tutor_id
        if responsible == 'tutor':
            return base.task_users(tutor.user_id, f"{self.name} (tutor)")
        if responsible == 'coexistence':
            coordinators = tutor._ems_coexistence_coordinators().user_id if tutor else self.env['res.users']
            if coordinators:
                return base.task_users(coordinators, f"{self.name} (coexistence)")
            return base.role_task_users('ems.role_coexistence')
        if responsible == 'secretariat':
            return base.secretariat_task_users()
        return base.role_task_users('ems.role_director')

    def _ems_user_acts_as(self, responsible):
        """Whether the current user may do a step of `responsible`: whoever gets its task, the
        Head of Studies for the tutor's and Coexistence's steps (they manage both), the Director
        group for Direction's, the secretariat group for the Secretariat's, and the
        administrators always on top."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group('ems.group_academic_admin') or user.has_group('base.group_system'):
            return True
        if responsible == 'tutor':
            return self._ems_user_manages() or self.env['ems.base'].user_acts_as_tutor(self.student_id.sudo().tutor_id)
        if responsible == 'coexistence':
            return self._ems_user_manages() or user in self._ems_responsible_users('coexistence')
        if responsible == 'secretariat':
            return user.has_group('ems.group_secretary')
        return user.has_group('ems.group_director')

    def _ems_schedule_task(self, xmlid, users, deadline, step=None):
        """A task in each user's to-do list, its summary in their language: the step's (or the
        proposal's) name and the student. mail_activity_quick_update: the task itself is the
        notice, Odoo's "X has assigned you an activity" email would be a second one."""
        self.ensure_one()
        for user in users:
            withdrawal = self.sudo().with_context(lang=user.lang, mail_activity_quick_update=True)
            withdrawal.activity_schedule(act_type_xmlid=xmlid, summary=withdrawal._ems_task_summary(step),
                                         user_id=user.id, date_deadline=deadline)

    def _ems_task_summary(self, step):
        if step:
            label = dict(step._fields['code']._description_selection(self.env))[step.code]
        else:
            label = _("Ex officio withdrawal proposal")
        return f"{label}: {self.student_id.display_name}"

    def _ems_close_tasks(self):
        """Drop every pending proposal or step task: what had to be done is done."""
        task_types = self.env.ref(PROPOSAL_TASK) | self.env.ref(STEP_TASK)
        self.sudo().activity_ids.filtered(lambda activity: activity.activity_type_id in task_types).unlink()

    def _ems_user_manages(self):
        """Whoever may act on every case file: the Head of Studies (the Director implies it) and
        the administrators."""
        user = self.env.user
        return self.env.su or any(user.has_group(group) for group in (
            'ems.group_head_of_studies', 'ems.group_academic_admin', 'base.group_system'))

    def _ems_check_can_decide_proposal(self):
        for withdrawal in self:
            if withdrawal.state != 'proposal':
                raise UserError(_("Only a proposal can be started or dismissed."))
            if not withdrawal.can_decide_proposal:
                raise UserError(_("Only the student's tutor, the people above them and the Head of Studies "
                                  "can decide this proposal."))

    @api.model
    def _ems_circuit_for_level(self, level):
        """The protocol a student of `level` follows, from its educational stage (False: none)."""
        return CIRCUIT_BY_STAGE.get(level.education_stage, False)

    def _ems_due_date(self, deadline):
        """The day a step is due by the protocol, counted from the first day of absence (the one
        place the circuit's deadlines are computed). {'school_days': N}: the N-th school day of
        absence, the first day included, skipping weekends and the centre's holidays and breaks.
        Otherwise calendar days and months (relativedelta keywords)."""
        self.ensure_one()
        start = self.first_absence_date
        if 'school_days' not in deadline:
            return start + relativedelta(**deadline)
        return self._ems_nth_school_day(start, deadline['school_days'], include_start=True)

    def _ems_nth_school_day(self, start, count, include_start=False):
        """The `count`-th school day from `start` (`start` itself counted when `include_start`);
        `start` when `count` is 0."""
        if not count:
            return start
        window_end = start + timedelta(days=count * SCHOOL_DAY_WINDOW_FACTOR + SCHOOL_DAY_WINDOW_MARGIN)
        closed = self.env['resource.calendar.leaves']._ems_holiday_dates(start, window_end)
        day, seen = (start, 0) if include_start else (start + timedelta(days=1), 0)
        while True:
            if day.weekday() < 5 and day not in closed:
                seen += 1
                if seen == count:
                    return day
            day += timedelta(days=1)

    def _ems_after_wait(self, previous, step, done_day):
        """The earliest day `step` may be done when the step before it, `previous`, was done on
        `done_day`: the protocol's wait between them (school days in a school-day circuit, the
        calendar days between their protocol dates otherwise) counted from that day."""
        self.ensure_one()
        catalog = STEP_CATALOG[self.circuit]
        before, after = catalog[previous.sequence][2], catalog[step.sequence][2]
        if 'school_days' in after:
            return self._ems_nth_school_day(done_day, after['school_days'] - before['school_days'])
        return done_day + timedelta(days=(step.planned_date - previous.planned_date).days)

    def _ems_shift_pending_steps(self, done_step, done_day):
        """A step done later than its protocol date moves the ones after it, so every wait the
        protocol sets between two steps is kept: each pending step is due on the later of its
        protocol date and the previous one's day plus the wait between them."""
        self.ensure_one()
        previous, previous_day = done_step, done_day
        for step in self.step_ids.filtered(lambda later: later.sequence > done_step.sequence):
            due = max(step.planned_date, self._ems_after_wait(previous, step, previous_day))
            if step.due_date != due:
                step.sudo().due_date = due
            previous, previous_day = step, due

class EmsExOfficioWithdrawalStep(models.Model):
    """One step of a case file's protocol: who does it, by when, and what they did."""
    _name = 'ems.ex_officio_withdrawal.step'
    _description = "Ex officio withdrawal step"
    _order = 'withdrawal_id, sequence, id'

    withdrawal_id = fields.Many2one(string="Case file", comodel_name='ems.ex_officio_withdrawal', required=True,
                                    ondelete='cascade', index=True)
    sequence = fields.Integer(string="Sequence")
    code = fields.Selection(string="Step", selection=STEP_CODES, required=True, readonly=True)
    responsible = fields.Selection(string="Responsible", selection=RESPONSIBLES, required=True, readonly=True)
    # The protocol's day (from the first day of absence) and the day the step is really due: later
    # when an earlier step was done late, so the protocol's waits are always kept.
    planned_date = fields.Date(string="Protocol day", readonly=True)
    due_date = fields.Date(string="Due", readonly=True)
    check_ids = fields.One2many(string="To confirm", comodel_name='ems.ex_officio_withdrawal.check',
                                inverse_name='step_id')
    notes = fields.Text(string="Notes")
    done_by_id = fields.Many2one(string="Done by", comodel_name='res.users', readonly=True)
    done_date = fields.Datetime(string="Done on", readonly=True)
    task_scheduled = fields.Boolean(string="Task scheduled", readonly=True, copy=False,
                                    help="Its responsible already got the task (on its day).")
    # Stored, so the case file's current_check_ids can filter its checks on it.
    is_current = fields.Boolean(string="Current step", compute='_compute_is_current', store=True)

    @api.depends('withdrawal_id.current_step_id')
    def _compute_is_current(self):
        for step in self:
            step.is_current = step == step.withdrawal_id.current_step_id

    def write(self, vals):
        """Only the current step's responsible ticks its checks or writes its notes."""
        if not self.env.su:
            if set(vals) - {'notes'}:
                raise UserError(_("A step only changes through its case file's buttons."))
            if any(not step.is_current or not step.withdrawal_id.can_accept_step
                   or not step.withdrawal_id._ems_current_step_open() for step in self):
                raise UserError(_("Only the responsible of the current step can change it."))
        return super().write(vals)


class EmsExOfficioWithdrawalCheck(models.Model):
    """One thing a step asks its responsible to confirm (a phone call, an eNotum, a record in
    Esfera...), with the day it was done. They are ticked one by one, in as many goes as needed;
    the step is only accepted once every one is."""
    _name = 'ems.ex_officio_withdrawal.check'
    _description = "Ex officio withdrawal step check"
    _order = 'step_id, sequence, id'

    step_id = fields.Many2one(string="Step", comodel_name='ems.ex_officio_withdrawal.step', required=True,
                              ondelete='cascade', index=True)
    withdrawal_id = fields.Many2one(string="Case file", related='step_id.withdrawal_id', store=True, index=True)
    is_current = fields.Boolean(string="Of the current step", related='step_id.is_current', store=True)
    sequence = fields.Integer(string="Sequence")
    code = fields.Selection(string="Action", selection=CHECK_CODES, required=True, readonly=True)
    label = fields.Char(string="I confirm", compute='_compute_label')
    done = fields.Boolean(string="Done")
    date = fields.Date(string="On", default=lambda self: self.env['ems.datetime_utils'].get_local_today())

    @api.depends('code')
    @api.depends_context('lang')
    def _compute_label(self):
        sentences = _check_sentences()
        for check in self:
            check.label = sentences.get(check.code)

    @api.constrains('done', 'date')
    def _check_date(self):
        today = self.env['ems.datetime_utils'].get_local_today()
        for check in self.filtered('done'):
            if not check.date:
                raise ValidationError(_("Say on which day it was done."))
            if check.date > today:
                raise ValidationError(_("The day it was done cannot be in the future."))
            if check.date < check.withdrawal_id.first_absence_date:
                raise ValidationError(_("The day it was done cannot be before the first day of absence."))

    def write(self, vals):
        """Only the current step's responsible ticks its checks and their days."""
        if not self.env.su:
            if set(vals) - {'done', 'date'}:
                raise UserError(_("A step only changes through its case file's buttons."))
            if any(not check.is_current or not check.withdrawal_id.can_accept_step
                   or not check.withdrawal_id._ems_current_step_open() for check in self):
                raise UserError(_("Only the responsible of the current step can change it."))
        return super().write(vals)


class EmsExOfficioWithdrawalDismissWizard(models.TransientModel):
    """Dismiss a proposal, saying why (issue #726)."""
    _name = 'ems.ex_officio_withdrawal.dismiss_wizard'
    _description = "Dismiss an ex officio withdrawal proposal"

    withdrawal_id = fields.Many2one(string="Case file", comodel_name='ems.ex_officio_withdrawal', required=True,
                                    ondelete='cascade')
    note = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.withdrawal_id.action_dismiss(self.note)
        return {'type': 'ir.actions.act_window_close'}


class EmsExOfficioWithdrawalPartner(models.Model):
    """The student form's smart button towards their case files."""
    _inherit = 'res.partner'

    # Only for who may read case files at all; each sees the ones their rules let them.
    ex_officio_withdrawal_count = fields.Integer(
        string="Ex officio withdrawals", compute='_compute_ex_officio_withdrawal_count',
        groups='ems.group_tutor,ems.group_student_data_reader,ems.group_secretary,ems.group_academic_admin')

    def _compute_ex_officio_withdrawal_count(self):
        counts = dict(self.env['ems.ex_officio_withdrawal']._read_group(
            [('student_id', 'in', self._origin.ids)], ['student_id'], ['__count']))
        for partner in self:
            partner.ex_officio_withdrawal_count = counts.get(partner._origin, 0)

    # The Actions entry "Request ex officio withdrawal". Not restricted by groups: a field the
    # dropdown's invisible= reads must reach every user who opens the form (issue #434).
    can_request_ex_officio_withdrawal = fields.Boolean(
        string="Can request an ex officio withdrawal", compute='_compute_can_request_ex_officio_withdrawal')

    @api.depends('contact_type', 'active', 'main_group_id', 'tutor_id')
    @api.depends_context('uid')
    def _compute_can_request_ex_officio_withdrawal(self):
        """A student whose level has a circuit and no open case file, for their tutor and the
        chain above them, the Head of Studies and the administrators (the same people who may
        open one by hand)."""
        Withdrawal = self.env['ems.ex_officio_withdrawal']
        students = self.filtered(lambda partner: partner.contact_type == 'student' and partner.active)
        with_open = set(Withdrawal.sudo().search([('student_id', 'in', students._origin.ids),
                                                  ('state', 'in', OPEN_STATES)]).student_id.ids)
        manages = Withdrawal._ems_user_manages()
        base = self.env['ems.base']
        for partner in self:
            student = partner.sudo()
            group = student.main_group_id
            partner.can_request_ex_officio_withdrawal = (
                partner in students and partner._origin.id not in with_open
                and bool(Withdrawal._ems_circuit_for_level(group.study_id.level_id or group.level_id))
                and (manages or base.user_acts_as_tutor(student.tutor_id)))

    def action_request_ex_officio_withdrawal(self):
        """Open a new case file for this student, to fill in the first day of absence."""
        self.ensure_one()
        if not self.can_request_ex_officio_withdrawal:
            raise UserError(_("Only the student's tutor, the people above them and the Head of Studies can request "
                              "an ex officio withdrawal, for a student whose level has a circuit and no open case "
                              "file."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ex officio withdrawal"),
            'res_model': 'ems.ex_officio_withdrawal',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'default_student_id': self.id},
        }

    def action_view_ex_officio_withdrawals(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_ex_officio_withdrawal')
        action['domain'] = [('student_id', '=', self.id)]
        action['context'] = {'default_student_id': self.id}
        return action
