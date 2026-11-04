# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date

from ..curriculum.level import CIRCUITS


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

# The off-EMS actions a step can ask its responsible to tick.
CHECKS = ('phone', 'enotum', 'esfera', 'saga', 'external_email')

# The protocol of each circuit, as Direction validated it (issue #726, 2026-11-03): step code,
# responsible, deadline from the first day of absence and the off-EMS checks it asks for. A
# deadline is either {'school_days': N} (the N-th school day of absence, the first one included)
# or relativedelta keywords (calendar days and months). See _ems_due_date().
STEP_CATALOG = {
    # Resolució EDF/293/2026, 8.6: the place is lost after 15 days. Counted in school days, so
    # nobody ever gets less margin than the regulation gives.
    'post_compulsory': (
        ('tutor_contact', 'tutor', {'school_days': 5}, ('phone',)),
        ('secretariat_warning', 'secretariat', {'school_days': 10}, ('enotum',)),
        ('direction_approval', 'direction', {'school_days': 15}, ()),
        ('withdrawal', 'secretariat', {'school_days': 15}, ('esfera', 'saga', 'enotum')),
    ),
    # Two months, in calendar days, as the communication plan says.
    'compulsory': (
        ('tutor_contact', 'tutor', {'days': 7}, ('phone',)),
        ('coexistence_contact', 'coexistence', {'days': 15}, ('phone',)),
        ('secretariat_notice', 'secretariat', {'months': 1}, ()),
        ('social_services', 'coexistence', {'months': 1}, ('external_email',)),
        ('secretariat_warning', 'secretariat', {'months': 1, 'days': 15}, ('enotum',)),
        ('direction_approval', 'direction', {'months': 2}, ('external_email',)),
        ('withdrawal', 'secretariat', {'months': 2}, ('esfera',)),
    ),
}

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
                                      compute='_compute_current_step_id')
    next_due_date = fields.Date(string="Next deadline", compute='_compute_current_step_id')
    can_decide_proposal = fields.Boolean(string="Can decide the proposal", compute='_compute_can_decide_proposal')
    can_accept_step = fields.Boolean(string="Can do the current step", compute='_compute_can_accept_step')

    @api.depends('step_ids.done_date', 'step_ids.due_date')
    def _compute_current_step_id(self):
        for withdrawal in self:
            step = withdrawal.step_ids.filtered(lambda pending: not pending.done_date)[:1]
            withdrawal.current_step_id = step
            withdrawal.next_due_date = step.due_date

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
            if not level.withdrawal_circuit:
                raise UserError(_("%(student)s's level has no ex officio withdrawal circuit: set it on the level "
                                  "first.", student=student.display_name))
            vals.update({'group_id': group.id, 'level_id': level.id, 'circuit': level.withdrawal_circuit})
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
                'due_date': withdrawal._ems_due_date(deadline),
            } for index, (code, responsible, deadline, _checks) in enumerate(STEP_CATALOG[withdrawal.circuit])])
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
        asks for ticked. The next step's task is scheduled on its own day."""
        today = self.env['ems.datetime_utils'].get_local_today()
        for withdrawal in self:
            step = withdrawal.current_step_id
            if not withdrawal.can_accept_step:
                raise UserError(_("Only the responsible of the current step can do it."))
            if step.due_date > today:
                raise UserError(_("This step is due on %(date)s: it cannot be done before.",
                                  date=format_date(self.env, step.due_date)))
            missing = [step._fields[f'{check}_done'].get_description(self.env)['string']
                       for check in CHECKS if step[f'needs_{check}'] and not step[f'{check}_done']]
            if missing:
                raise UserError(_("Tick what this step asks for first: %s", ", ".join(missing)))
            step.sudo().write({'done_by_id': self.env.uid, 'done_date': fields.Datetime.now()})
            body = _("Step done: %s", dict(step._fields['code']._description_selection(self.env))[step.code])
            if step.notes:
                body = f"{body}\n{step.notes}"
            withdrawal._message_log(body=body)
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

    def _ems_due_date(self, deadline):
        """The day a step is due, counted from the first day of absence (the one place the circuit's
        deadlines are computed). {'school_days': N}: the N-th school day of absence, the first day
        included, skipping weekends and the centre's holidays and breaks. Otherwise calendar days
        and months (relativedelta keywords)."""
        self.ensure_one()
        start = self.first_absence_date
        if 'school_days' not in deadline:
            return start + relativedelta(**deadline)
        count = deadline['school_days']
        window_end = start + timedelta(days=count * SCHOOL_DAY_WINDOW_FACTOR + SCHOOL_DAY_WINDOW_MARGIN)
        closed = self.env['resource.calendar.leaves']._ems_holiday_dates(start, window_end)
        day, seen = start, 0
        while True:
            if day.weekday() < 5 and day not in closed:
                seen += 1
                if seen == count:
                    return day
            day += timedelta(days=1)


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
    due_date = fields.Date(string="Due", readonly=True)
    phone_done = fields.Boolean(string="Phone call made")
    enotum_done = fields.Boolean(string="eNotum sent")
    esfera_done = fields.Boolean(string="Registered in Esfera")
    saga_done = fields.Boolean(string="Registered in SAGA")
    external_email_done = fields.Boolean(string="Email sent by hand")
    needs_phone = fields.Boolean(string="Asks for a phone call", compute='_compute_needs')
    needs_enotum = fields.Boolean(string="Asks for eNotum", compute='_compute_needs')
    needs_esfera = fields.Boolean(string="Asks for Esfera", compute='_compute_needs')
    needs_saga = fields.Boolean(string="Asks for SAGA", compute='_compute_needs')
    needs_external_email = fields.Boolean(string="Asks for an email sent by hand", compute='_compute_needs')
    notes = fields.Text(string="Notes")
    done_by_id = fields.Many2one(string="Done by", comodel_name='res.users', readonly=True)
    done_date = fields.Datetime(string="Done on", readonly=True)
    task_scheduled = fields.Boolean(string="Task scheduled", readonly=True, copy=False,
                                    help="Its responsible already got the task (on its day).")
    is_current = fields.Boolean(string="Current step", compute='_compute_is_current')

    @api.depends('code', 'withdrawal_id.circuit')
    def _compute_needs(self):
        checks_by_step = {(circuit, code): checks
                          for circuit, steps in STEP_CATALOG.items() for code, _resp, _deadline, checks in steps}
        for step in self:
            checks = checks_by_step.get((step.withdrawal_id.circuit, step.code), ())
            for check in CHECKS:
                step[f'needs_{check}'] = check in checks


    @api.depends('withdrawal_id.current_step_id')
    def _compute_is_current(self):
        for step in self:
            step.is_current = step == step.withdrawal_id.current_step_id

    def write(self, vals):
        """Only the current step's responsible ticks its checks or writes its notes."""
        if not self.env.su:
            if set(vals) - {f'{check}_done' for check in CHECKS} - {'notes'}:
                raise UserError(_("A step only changes through its case file's buttons."))
            if any(not step.is_current or not step.withdrawal_id.can_accept_step for step in self):
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

    def action_view_ex_officio_withdrawals(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_ex_officio_withdrawal')
        action['domain'] = [('student_id', '=', self.id)]
        action['context'] = {'default_student_id': self.id}
        return action
