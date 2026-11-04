# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, format_datetime, html2plaintext



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
    ('phone_attempt', 'Unanswered phone call'),
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
        ('tutor_contact', 'tutor', {'school_days': 5}, ('phone', 'family_email')),
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
        'phone_attempt': _("I phoned the family and did not reach them on"),
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

def _family_email_labels():
    """How the case file names each email to the family once sent."""
    return {
        'ems.email_template_ex_officio_withdrawal_tutor_confirmation': _("confirmation of the phone call"),
        'ems.email_template_ex_officio_withdrawal_tutor_unreachable': _("could not reach them by phone"),
        'ems.email_template_ex_officio_withdrawal_family_notice': _("notice to the family"),
        'ems.email_template_ex_officio_withdrawal_family_warning': _("withdrawal warning"),
    }


OPEN_STATES = ('proposal', 'in_progress', 'direction', 'secretariat')
# The states whose current step is somebody's task: the procedure has started.
STARTED_STATES = ('in_progress', 'direction', 'secretariat')
# The state a started case file is in while its current step is one of these.
STATE_BY_STEP = {'direction_approval': 'direction', 'withdrawal': 'secretariat'}

# The emails to the family each step offers (mails/contacts/ex_officio_withdrawal.xml), sent only when
# its responsible asks, one button each: the tutor's two depend on whether the phone call reached
# the family. Sending one ticks the step's "Email to the family", which nobody ticks by hand.
FAMILY_TEMPLATES = {
    ('post_compulsory', 'tutor_contact'): ('ems.email_template_ex_officio_withdrawal_tutor_confirmation',
                                           'ems.email_template_ex_officio_withdrawal_tutor_unreachable'),
    ('post_compulsory', 'secretariat_warning'): ('ems.email_template_ex_officio_withdrawal_family_warning',),
    ('compulsory', 'secretariat_notice'): ('ems.email_template_ex_officio_withdrawal_family_notice',),
    ('compulsory', 'secretariat_warning'): ('ems.email_template_ex_officio_withdrawal_family_warning',),
}
# Every step's phone call is confirmed from the contact window, saying how it went: one button per
# outcome. Where the step also writes to the family, the window sends its email too (reached: the
# first text; not reached: the second); not reached can instead try again the next school day.
CALL_OUTCOMES = [('reached', 'Reached them'), ('not_reached', 'Did not reach them')]

# The texts a step's responsible copies and sends themselves (no address in EMS), in the centre
# language; the Inspection's goes with the case file PDF.
COPY_TEMPLATES = {
    ('compulsory', 'social_services'): 'ems.email_template_ex_officio_withdrawal_social_services',
    ('compulsory', 'direction_approval'): 'ems.email_template_ex_officio_withdrawal_inspection',
}
CASE_FILE_REPORT = 'ems.action_report_ex_officio_withdrawal'

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
    # Phase 3: what the current step's block offers its responsible, once the step is open.
    # The contact part of the block, right after what to do. A step with a phone call shows one
    # button per call outcome until it is confirmed (call_pending); its email, if any, goes with it.
    # Otherwise the family email is 'ready' (its button), then 'sent' (when and which); empty when the
    # step sends none.
    call_step = fields.Boolean(string="Asks for a phone call", compute='_compute_step_tools')
    call_pending = fields.Boolean(string="Phone call to confirm", compute='_compute_step_tools')
    family_email_state = fields.Selection(string="Email to the family", compute='_compute_step_tools', selection=[
        ('ready', 'Ready'), ('sent', 'Sent')])
    family_email_intro = fields.Char(string="Email to the family intro", compute='_compute_step_tools')
    family_email_sent = fields.Char(string="Email to the family sent", compute='_compute_step_tools')
    current_step_timing = fields.Html(string="By when", compute='_compute_current_step_texts', sanitize=False)
    # Below the contact: whether the step is late, and how to tick and accept it.
    current_step_notices = fields.Html(string="Step notices", compute='_compute_current_step_texts', sanitize=False)
    copy_text = fields.Text(string="Text to copy", compute='_compute_step_tools')
    can_print_for_inspection = fields.Boolean(string="Case file for the Inspection", compute='_compute_step_tools')
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
            withdrawal.current_step_instructions = withdrawal.current_step_timing = False
            withdrawal.current_step_notices = False
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
            withdrawal.current_step_instructions = Markup("<p><strong>{step}</strong></p><p>{what}</p>").format(
                step=codes[step.code], what=_step_instructions(withdrawal.circuit, step.code))
            withdrawal.current_step_timing = Markup("<p>{}</p>").format(frame)
            withdrawal.current_step_notices = Markup("{status}{help}").format(
                status=Markup("<p class='text-danger'>{}</p>").format(status) if status else '',
                help=Markup("<p class='text-muted'>{}</p>").format(help_line) if step.due_date <= today else '') \
                or False

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
        Check = self.env['ems.ex_officio_withdrawal.check']
        check_labels = dict(Check._fields['code']._description_selection(self.env))
        outcomes = dict(Check._fields['call_outcome']._description_selection(self.env))
        tz = str(self.env['ems.datetime_utils'].current_tz())
        for withdrawal in self:
            if not withdrawal.step_ids:
                withdrawal.history_html = False
                continue
            current = withdrawal.current_step_id
            rows = []
            for step in withdrawal.step_ids:
                checks = Markup("<br/>").join(
                    Markup("{label}{outcome}: {date}").format(
                        label=check_labels[check.code], date=format_date(self.env, check.date),
                        outcome=f" ({outcomes[check.call_outcome].lower()})" if check.call_outcome else '')
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

    @api.depends('state', 'current_step_id', 'step_ids.done_date', 'step_ids.check_ids.done',
                 'step_ids.check_ids.date')
    @api.depends_context('uid', 'lang')
    def _compute_step_tools(self):
        """The family emails, the text to copy and the case file PDF the current step offers to
        whoever may do it, from its day on."""
        for withdrawal in self:
            step = withdrawal.current_step_id
            acts = withdrawal.can_accept_step and withdrawal._ems_current_step_open()
            key = (withdrawal.circuit, step.code)
            withdrawal._ems_compute_contact(step, acts, FAMILY_TEMPLATES.get(key, ()))
            withdrawal.copy_text = withdrawal._ems_render_copy_text(COPY_TEMPLATES[key]) \
                if acts and key in COPY_TEMPLATES else False
            withdrawal.can_print_for_inspection = acts and step.code == 'direction_approval' \
                and 'inspection_email' in step.check_ids.mapped('code')

    def _ems_compute_contact(self, step, acts, xmlids):
        """The contact part of the current step's block (see call_pending and family_email_state)."""
        self.ensure_one()
        phone = step.check_ids.filtered(lambda check: check.code == 'phone')
        self.call_step = bool(phone)
        self.call_pending = acts and bool(phone) and not phone.done
        self.family_email_state = self.family_email_intro = self.family_email_sent = False
        if not acts or not xmlids:
            return
        if not phone:
            self.family_email_intro = _(
                "Send the email to the family from here: EMS writes the text, which you can review before "
                "sending it, and ticks it in the list.")
        email_check = step.check_ids.filtered(lambda check: check.code == 'family_email')
        if email_check.done:
            self.family_email_state = 'sent'
            labels = {self.env.ref(xmlid).id: label for xmlid, label in _family_email_labels().items()}
            self.family_email_sent = _("Email sent on %(date)s (%(which)s): its text is in the history.",
                                       date=format_date(self.env, email_check.date),
                                       which=labels.get(email_check.email_template_id.id, '-'))
        else:
            self.family_email_state = 'ready'

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

    def action_open_contact(self):
        """The current step's contact window: its phone call, with how it went (`call_outcome` in
        the context, one button each), and its email to the family, ready to review and send."""
        self.ensure_one()
        outcome = self.env.context.get('call_outcome')
        self._ems_check_contact_open(outcome)
        # Each button sends its own text: the first, or the second when the family was not reached.
        templates = self._ems_family_templates()
        template = templates[1 if outcome == 'not_reached' and len(templates) > 1 else 0] if templates else templates
        return {
            'type': 'ir.actions.act_window',
            'name': _("Phone call to the family") if outcome else _("Email to the family"),
            'res_model': 'ems.ex_officio_withdrawal.contact_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_withdrawal_id': self.id, 'default_template_id': template.id,
                        'default_call_outcome': outcome or False},
        }

    def _ems_check_contact_open(self, outcome):
        """The contact the current step still expects from the current user: its phone call (with
        an outcome), or else its email to the family. Checked again on the server."""
        self.ensure_one()
        if outcome:
            if not self.call_pending:
                raise UserError(_("Only the responsible of the current step can confirm its phone call, from its "
                                  "day on, and only once."))
        elif self.call_step:
            raise UserError(_("Say first how the phone call went."))
        elif not self.family_email_state:
            raise UserError(_("Only the responsible of the current step can email the family, from its day on."))
        elif self.family_email_state != 'ready':
            raise UserError(_("The email to the family of this step has already been sent."))

    def action_print_case_file(self):
        """The case file as a PDF: every step with who did it and when (what Direction sends to the
        Inspection)."""
        self.ensure_one()
        return self.env.ref(CASE_FILE_REPORT).report_action(self)

    def _ems_family_templates(self):
        """The emails to the family the current step offers."""
        self.ensure_one()
        xmlids = FAMILY_TEMPLATES.get((self.circuit, self.current_step_id.code), ())
        return self.env['mail.template'].sudo().browse([self.env.ref(xmlid).id for xmlid in xmlids])

    def _ems_render_copy_text(self, xmlid):
        """Subject and body of a text to copy, as plain text in the centre language."""
        self.ensure_one()
        template = self.env.ref(xmlid).sudo().with_context(lang=self.env.company.ems_lang)
        subject = template._render_field('subject', self.ids)[self.id]
        # One line per step done: html2plaintext would run the list items together.
        html = str(template._render_field('body_html', self.ids)[self.id]).replace('<li>', '<br/>- ')
        body = html2plaintext(html)
        return _("Subject: %(subject)s", subject=subject) + "\n\n" + body

    def _ems_done_step_lines(self):
        """One line per step done, with its day and what was done: what the texts for Social
        Services and the Inspection list (rendered in the text's language)."""
        self.ensure_one()
        codes = dict(self.env['ems.ex_officio_withdrawal.step']._fields['code']._description_selection(self.env))
        labels = dict(self.env['ems.ex_officio_withdrawal.check']._fields['code']._description_selection(self.env))
        lines = []
        for step in self.sudo().step_ids.filtered('done_date'):
            done = ", ".join(f"{labels[check.code].lower()} ({format_date(self.env, check.date)})"
                             for check in step.check_ids if check.done)
            line = f"{format_date(self.env, step.done_date.date())}: {codes[step.code]}"
            lines.append(f"{line} - {done}" if done else line)
        return lines

    @api.model
    def _ems_circuit_for_level(self, level):
        """The protocol a student of `level` follows, from its educational stage (False: none)."""
        return CIRCUIT_BY_STAGE.get(level.education_stage, False)

    def _ems_try_call_again(self, call_date):
        """The family was not reached and the responsible will phone again: the attempt stays in
        the case file, and the current step (with its task) moves to the next school day."""
        self.ensure_one()
        step = self.current_step_id
        tomorrow = self._ems_nth_school_day(self.env['ems.datetime_utils'].get_local_today(), 1)
        self.env['ems.ex_officio_withdrawal.check'].sudo().create({
            'step_id': step.id, 'code': 'phone_attempt', 'done': True, 'date': call_date, 'sequence': -1})
        step.sudo().write({'due_date': tomorrow, 'task_scheduled': False})
        self._ems_close_tasks()
        self._message_log(body=_("The family was not reached by phone on %(date)s: they will be phoned again on "
                                 "%(next)s.", date=format_date(self.env, call_date),
                                 next=format_date(self.env, tomorrow)))

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
    # The email to the family: which text was sent (the only way it gets ticked, see write()).
    email_template_id = fields.Many2one(string="Email sent", comodel_name='mail.template', readonly=True,
                                        ondelete='set null')
    # A phone call: how it went (said in the contact window).
    call_outcome = fields.Selection(string="Call outcome", selection=CALL_OUTCOMES, readonly=True)
    by_button = fields.Boolean(string="Ticked by sending", compute='_compute_by_button')

    @api.depends('code', 'call_outcome', 'by_button')
    @api.depends_context('lang')
    def _compute_label(self):
        """A call step's phone call says how it went once its window has said so; until then,
        where to say it."""
        sentences = _check_sentences()
        by_outcome = {
            'reached': _("I confirm I phoned the family (or the student, if of age) and reached them on"),
            'not_reached': _("I confirm I phoned the family (or the student, if of age) and did not reach them on"),
        }
        for check in self:
            if check.code == 'phone':
                check.label = by_outcome.get(check.call_outcome) or \
                    _("Phone call to the family: say how it went with the buttons above")
            else:
                check.label = sentences.get(check.code)

    @api.depends('code', 'step_id.code', 'withdrawal_id.circuit')
    def _compute_by_button(self):
        """A phone call is ticked by saying how it went in the contact window; the email to the
        family, by sending it."""
        for check in self:
            check.by_button = check.code in ('phone', 'phone_attempt') or (
                check.code == 'family_email' and (check.withdrawal_id.circuit, check.step_id.code) in FAMILY_TEMPLATES)

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
            if self.filtered('by_button'):
                raise UserError(_("This is ticked from the buttons of the step, not by hand."))
        return super().write(vals)


class EmsExOfficioWithdrawalContactWizard(models.TransientModel):
    """The current step's contact with the family (issue #726): its phone call, with its day and
    how it went (from the button that opens it), and its email to the student and the family, the
    template's text in their language, editable before sending. Confirming ticks them, never by
    hand, and keeps the text sent in the case file; a family not reached can be phoned again the
    next school day instead."""
    _name = 'ems.ex_officio_withdrawal.contact_wizard'
    _description = "Ex officio withdrawal contact with the family"

    withdrawal_id = fields.Many2one(string="Case file", comodel_name='ems.ex_officio_withdrawal', required=True,
                                    ondelete='cascade')
    # Set by the button that opens it, never chosen here; empty when the step sends no email.
    template_id = fields.Many2one(string="Which email", comodel_name='mail.template', readonly=True)
    call_outcome = fields.Selection(string="Outcome", selection=CALL_OUTCOMES, readonly=True)
    call_date = fields.Date(string="Phone call on", default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    recipient_ids = fields.Many2many(string="To", comodel_name='res.partner', compute='_compute_recipients')
    missing_email = fields.Char(string="Without an email address", compute='_compute_recipients')
    subject = fields.Char(string="Email subject", compute='_compute_text', store=True, readonly=False)
    body = fields.Html(string="Text", compute='_compute_text', store=True, readonly=False)

    @api.depends('withdrawal_id', 'template_id')
    def _compute_recipients(self):
        for wizard in self:
            withdrawal = wizard.withdrawal_id
            recipients = withdrawal.sudo().student_id._ems_student_and_family_recipients() \
                if withdrawal and wizard.template_id else self.env['res.partner']
            wizard.recipient_ids = recipients.filtered('email')
            wizard.missing_email = ", ".join(recipients.filtered(lambda partner: not partner.email).mapped('name'))

    @api.depends('template_id')
    def _compute_text(self):
        for wizard in self:
            if not wizard.template_id or not wizard.withdrawal_id:
                wizard.subject = wizard.body = False
                continue
            template = wizard.template_id.sudo().with_context(lang=wizard._ems_lang())
            res_id = wizard.withdrawal_id.id
            wizard.subject = template._render_field('subject', [res_id])[res_id]
            wizard.body = template._render_field('body_html', [res_id])[res_id]

    def _ems_lang(self):
        """The text is written in the language of whoever reads it (the student's when they
        differ)."""
        student = self.withdrawal_id.sudo().student_id
        return self.recipient_ids[:1].lang or student.lang or self.env.company.ems_lang

    def _ems_check_still_expected(self):
        withdrawal = self.withdrawal_id
        withdrawal._ems_check_contact_open(self.call_outcome)
        if self.template_id and self.template_id not in withdrawal._ems_family_templates():
            raise UserError(_("This text is not one the current step offers."))

    def action_confirm(self):
        """The phone call (its day and outcome) and the email, sent."""
        self.ensure_one()
        self._ems_check_still_expected()
        withdrawal = self.withdrawal_id
        step = withdrawal.current_step_id
        if self.template_id and not self.recipient_ids:
            raise UserError(_("Nobody to send it to has an email address."))
        if self.call_outcome:
            step.check_ids.filtered(lambda check: check.code == 'phone').sudo().write({
                'done': True, 'date': self.call_date, 'call_outcome': self.call_outcome})
            outcomes = dict(self._fields['call_outcome']._description_selection(self.env))
            withdrawal._message_log(body=_("Phone call to the family on %(date)s: %(outcome)s.",
                                           date=format_date(self.env, self.call_date),
                                           outcome=outcomes[self.call_outcome].lower()))
        if self.template_id:
            for recipient in self.recipient_ids:
                self.template_id.sudo().with_context(lang=self._ems_lang()).send_mail(
                    withdrawal.id, force_send=False,
                    email_values={'subject': self.subject, 'body_html': self.body, 'email_to': recipient.email})
            step.check_ids.filtered(lambda check: check.code == 'family_email').sudo().write({
                'done': True, 'date': self.env['ems.datetime_utils'].get_local_today(),
                'email_template_id': self.template_id.id})
            withdrawal._message_log(body=Markup("{intro}<br/><strong>{subject}</strong><br/>{body}").format(
                intro=_("Email sent to %s:", ", ".join(self.recipient_ids.mapped('email'))),
                subject=self.subject, body=self.body))
        return {'type': 'ir.actions.act_window_close'}

    def action_try_again(self):
        """Not reached, nothing sent: phone again the next school day."""
        self.ensure_one()
        if self.call_outcome != 'not_reached':
            raise UserError(_("Only an unanswered phone call can be tried again."))
        self._ems_check_still_expected()
        if not self.call_date or self.call_date > self.env['ems.datetime_utils'].get_local_today():
            raise UserError(_("The day it was done cannot be in the future."))
        self.withdrawal_id._ems_try_call_again(self.call_date)
        return {'type': 'ir.actions.act_window_close'}


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
