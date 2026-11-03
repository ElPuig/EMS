# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CIRCUITS = [
    ('compulsory', 'Compulsory education'),
    ('post_compulsory', 'Post-compulsory education'),
]

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
                               inverse_name='withdrawal_id', readonly=True)
    current_step_id = fields.Many2one(string="Current step", comodel_name='ems.ex_officio_withdrawal.step',
                                      compute='_compute_current_step_id')
    next_due_date = fields.Date(string="Next deadline", compute='_compute_current_step_id')
    can_decide_proposal = fields.Boolean(string="Can decide the proposal", compute='_compute_can_decide_proposal')

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
            withdrawal.sudo().state = 'in_progress'

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
        for withdrawal in self:
            withdrawal._message_log(body=_("Proposal dismissed: %(note)s", note=note))

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

    @api.depends('code', 'withdrawal_id.circuit')
    def _compute_needs(self):
        checks_by_step = {(circuit, code): checks
                          for circuit, steps in STEP_CATALOG.items() for code, _resp, _deadline, checks in steps}
        for step in self:
            checks = checks_by_step.get((step.withdrawal_id.circuit, step.code), ())
            for check in CHECKS:
                step[f'needs_{check}'] = check in checks


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
