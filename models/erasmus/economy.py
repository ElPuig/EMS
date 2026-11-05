# -*- coding: utf-8 -*-
"""Issue #762 - the economic management of the Erasmus+ projects: the grant (amendments and SEPIE's
transfers), what each mobility commits and what has been paid of it, the project's own expenses, the
organisational support, warnings and an Excel export. Every figure is computed from the records
that already hold it (the mobilities' grants, the grant payments, the invoices, the expenses): none
is typed twice. See docs/en/developers/erasmus/economy.md."""

import io
import re
from collections import defaultdict

import xlsxwriter
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_date, formatLang

from .call import PROJECTS
from .grant import _ask_transfer, _check_transfer_fields, _transfer_wizard_action, _undo_wizard_action
from .workflow import check_workflow_create, check_workflow_write

# Who reads the economic figures: the Erasmus team, the Secretary and the Director (who only reads).
ECONOMY_READERS = 'ems.group_erasmus,ems.group_secretary,ems.group_director,ems.group_academic_admin'
# Who manages them: the Erasmus team (coordination); the administrator is above every role.
ECONOMY_MANAGERS = ('ems.group_erasmus', 'ems.group_academic_admin')
ECONOMIC_STATES = [('forecast', "Forecast"), ('committed', "Committed"), ('partial', "Partially paid"),
                   ('paid', "Paid"), ('cancelled', "Cancelled"), ('adjusted', "Cancelled with payments")]
EXPENSE_CATEGORIES = [('organisational_support', "Organisational support"), ('other', "Other project expenses")]
EXPENSE_STATES = [('to_pay', "Registered, to pay"), ('paid', "Paid"), ('cancelled', "Cancelled")]
# What changes an expense's figures: once paid, only the correction wizard changes it, with a reason.
EXPENSE_ECONOMIC_FIELDS = {'project_id', 'amount', 'category', 'concept', 'date', 'mobility_id'}
# Set only by the workflow (paying, correcting), never typed.
EXPENSE_WORKFLOW_FIELDS = ('state', 'corrected', 'transferred_amount', 'corrected_from_id')
INCOME_KINDS = [('prefinancing', "Prefinancing"), ('further', "Further prefinancing"), ('balance', "Balance"),
                ('other', "Other")]
# The kinds of mobility the funding rules give an organisational support rate to (accompanying
# teachers never generate it). The last two are only chosen by hand on the mobility.
SUPPORT_TYPES = [('student_short', "Students: short-term individual mobility"),
                 ('student_long', "Students: long-term mobility (ErasmusPro)"),
                 ('student_group', "Students: group mobility"),
                 ('staff_job', "Staff: job shadowing or teaching"),
                 ('staff_course', "Staff: courses and training"),
                 ('non_associated', "Individual activity in a third country not associated to the programme"),
                 ('other', "Skills competitions, invited experts or hosted teachers in training")]
MANUAL_SUPPORT_TYPES = ('non_associated', 'other')
# How a rate's band counts the participants: those of the same kind of mobility (KA121-VET, e.g.
# 350 € up to the 100th job shadowing, 200 € beyond) or every participant of the project (KA131-HED:
# 400 € for the first 100, students and staff together, 230 € beyond).
BAND_SCOPES = [('same', "Same kind of mobility"), ('project', "Whole project")]
# A students' stay of this many days or more is a long-term mobility (ErasmusPro).
LONG_TERM_DAYS = 90
# A group mobility before its selection is approved plans its student places; afterwards, its students.
GROUP_PLANNING_STATES = ('draft', 'enrolment', 'selection', 'validation')
GROUP_DONE_STATES = ('return', 'done')
# The call year at the start of an agreement number: 2026-1-ES01-KA121-VET-000123456.
CALL_YEAR = re.compile(r'^\s*(20\d\d)-')


def _is_manager(env):
    return any(env.user.has_group(group) for group in ECONOMY_MANAGERS)


def _check_manager(env):
    if not env.su and not _is_manager(env):
        raise AccessError(_("Only the Erasmus+ coordination changes the economic figures of a project."))


def economic_figures(planned, spent, paid, phase, recovered=0.0):
    """One mobility's economic figures, the same for an individual one and a group (issue #762).
    `planned`: its grant; `spent`: what has been requested or invoiced out of it (payments to the
    participant, services the centre pays); `paid`: what of that has been paid; `phase`: 'forecast'
    (not confirmed yet), 'committed' or 'cancelled'; `recovered`: what the participant gave back.
    A payment never adds to the commitment: paying only moves an amount from pending to paid. What
    has really gone out is never below the commitment, though (an invoice above the grant)."""
    net_paid = paid - recovered
    if phase == 'cancelled':
        committed, forecast = max(net_paid, 0.0), 0.0
        state = 'adjusted' if net_paid > 0 else 'cancelled'
    elif phase == 'forecast':
        committed, forecast = max(spent - recovered, 0.0), planned
        state = 'forecast'
    else:
        committed, forecast = max(planned, spent - recovered), 0.0
        state = 'paid' if committed and net_paid >= committed else 'partial' if net_paid > 0 else 'committed'
    if phase == 'forecast' and net_paid > 0:
        state = 'partial'
    return {'econ_state': state, 'econ_forecast': forecast, 'econ_committed': committed, 'econ_paid': net_paid,
            'econ_pending': max(committed - net_paid, 0.0)}


class EmsErasmusEconomy(models.AbstractModel):
    """What an individual mobility and a group mobility share about money: their economic state and
    figures, each computed from `_ems_economic_inputs()`. The economic state never replaces the
    mobility's own state."""
    _name = 'ems.erasmus.economy'
    _description = 'Erasmus+ economic figures of a mobility'

    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency', compute='_compute_currency_id')
    econ_state = fields.Selection(string="Economic state", selection=ECONOMIC_STATES, store=True,
                                  compute='_compute_economy', groups=ECONOMY_READERS)
    econ_forecast = fields.Monetary(string="Forecast", store=True, compute='_compute_economy',
                                    groups=ECONOMY_READERS,
                                    help="The grant of a mobility not confirmed yet: it commits no budget.")
    econ_committed = fields.Monetary(string="Committed", store=True, compute='_compute_economy',
                                     groups=ECONOMY_READERS,
                                     help="What the mobility consumes of the project's budget: its grant once "
                                          "confirmed (or what has gone out, if more); for a cancelled one, only "
                                          "what was paid and not given back.")
    econ_paid = fields.Monetary(string="Paid", store=True, compute='_compute_economy', groups=ECONOMY_READERS,
                                help="Transferred to the participant plus the services the centre paid for them, "
                                     "minus what the participant gave back.")
    econ_pending = fields.Monetary(string="Pending payment", store=True, compute='_compute_economy',
                                   groups=ECONOMY_READERS)
    recovered_amount = fields.Monetary(string="Given back by the participant", tracking=True,
                                       groups=ECONOMY_READERS,
                                       help="What the participant returned of what was paid (e.g. a cancelled or "
                                            "shortened mobility).")

    def _compute_currency_id(self):
        self.currency_id = self.env.company.currency_id

    def _ems_economic_depends(self):
        return ['recovered_amount']

    def _ems_economic_inputs(self):
        """(planned, spent, paid, phase) of this mobility: see economic_figures()."""
        raise NotImplementedError()

    @api.depends(lambda self: self._ems_economic_depends())
    def _compute_economy(self):
        for mobility in self:
            mobility.update(economic_figures(*mobility._ems_economic_inputs(), recovered=mobility.recovered_amount))

    @api.constrains('recovered_amount')
    def _check_recovered_amount(self):
        for mobility in self:
            if mobility.recovered_amount < 0:
                raise ValidationError(_("What a participant gives back cannot be negative."))


class EmsErasmusMobility(models.Model):
    """An individual mobility's grant: a forecast while its destination is being defined, committed
    once preparing, and its payments and the services the centre paid for it (provisions whose
    invoice is paid) as paid."""
    _name = 'ems.erasmus.mobility'
    _inherit = ['ems.erasmus.mobility', 'ems.erasmus.economy']

    support_type = fields.Selection(
        string="Organisational support as", selection=SUPPORT_TYPES, compute='_compute_support_type', store=True,
        readonly=False, groups=ECONOMY_READERS,
        help="The kind of mobility whose organisational support rate applies: from the participant, the dates and "
             "the staff activity. A third country not associated to the programme, or a skills competition, an "
             "invited expert or a hosted teacher, is chosen by hand.")

    @api.depends('audience', 'proposal_activity', 'date_start', 'date_end')
    def _compute_support_type(self):
        for mobility in self:
            if mobility.support_type in MANUAL_SUPPORT_TYPES:
                continue
            if mobility.audience == 'staff':
                mobility.support_type = 'staff_course' if mobility.proposal_activity == 'course' else 'staff_job'
            else:
                days = mobility.date_start and mobility.date_end and (mobility.date_end - mobility.date_start).days + 1
                mobility.support_type = 'student_long' if days and days >= LONG_TERM_DAYS else 'student_short'

    def _ems_economic_depends(self):
        return super()._ems_economic_depends() + [
            'state', 'grant_amount', 'payment_ids.amount', 'payment_ids.state', 'provision_ids.amount',
            'provision_ids.invoice_id.state']

    def _ems_economic_inputs(self):
        self.ensure_one()
        provisions = self.provision_ids
        paid_provisions = provisions.filtered(lambda provision: provision.invoice_id.state == 'paid')
        payments = self.payment_ids
        spent = sum(payments.mapped('amount')) + sum(provisions.mapped('amount'))
        paid = sum(payments.filtered(lambda payment: payment.state == 'paid').mapped('amount')) \
            + sum(paid_provisions.mapped('amount'))
        phase = 'cancelled' if self.state == 'cancelled' else 'forecast' if self.state == 'choosing' else 'committed'
        return self.grant_amount, spent, paid, phase


class EmsErasmusGroupParticipant(models.Model):
    """Each participant of a group mobility, student or accompanying teacher, has their own grant,
    as calculated in the Beneficiary Module. It is counted once, in the group mobility's figures."""
    _inherit = 'ems.erasmus.group.participant'

    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency', compute='_compute_currency_id')
    # Also read by the group's leader and accompanying teachers (issue #764).
    grant_amount = fields.Monetary(string="Grant", tracking=True,
                                   groups=f'{ECONOMY_READERS},ems.group_erasmus_group_teacher',
                                   help="The participant's grant, as calculated in the Beneficiary Module.")

    def _compute_currency_id(self):
        self.currency_id = self.env.company.currency_id


class EmsErasmusGroupMobility(models.Model):
    """A group mobility's grant: the sum of its participants' grants (students and accompanying
    teachers), each counted once, a forecast until the selection is approved and committed
    afterwards; its collective invoices are what has been paid of it."""
    _name = 'ems.erasmus.group.mobility'
    _inherit = ['ems.erasmus.group.mobility', 'ems.erasmus.economy']

    grant_amount = fields.Monetary(string="Grants of the participants", compute='_compute_grant_amount', store=True,
                                   groups=ECONOMY_READERS,
                                   help="The sum of the grants of the participants taking part, students and "
                                        "accompanying teachers.")
    grant_participant_ids = fields.One2many(
        string="Participants' grants", comodel_name='ems.erasmus.group.participant', inverse_name='group_mobility_id',
        groups=f'{ECONOMY_READERS},ems.group_erasmus_group_teacher', help="Each participant's grant, as calculated in the Beneficiary Module.")

    @api.depends('participant_ids.grant_amount', 'participant_ids.state')
    def _compute_grant_amount(self):
        for mobility in self:
            mobility.grant_amount = sum(mobility.participant_ids.filtered(
                lambda participant: participant.state == 'active').mapped('grant_amount'))

    def _ems_economic_depends(self):
        return super()._ems_economic_depends() + ['state', 'grant_amount', 'invoice_ids.amount',
                                                  'invoice_ids.state', 'participant_ids.payment_ids.amount',
                                                  'participant_ids.payment_ids.state']

    def _ems_economic_inputs(self):
        """Spent: the collective invoices and the participants' pocket money payments (issue #764)."""
        self.ensure_one()
        records = self.invoice_ids, self.sudo().participant_ids.payment_ids
        spent = sum(sum(group.mapped('amount')) for group in records)
        paid = sum(sum(group.filtered(lambda record: record.state == 'paid').mapped('amount')) for group in records)
        phase = 'cancelled' if self.state == 'cancelled' else \
            'forecast' if self.state in GROUP_PLANNING_STATES else 'committed'
        return self.grant_amount, spent, paid, phase


class EmsErasmusProject(models.Model):
    """A project's economy: the grant (initial, amendments, final) and SEPIE's transfers, what its
    mobilities and expenses commit and what has been paid, the organisational support and the
    warnings. Stored, so that the panel and the comparison by call can sum and group them."""
    _inherit = 'ems.erasmus.project'

    call_year = fields.Integer(string="Call year", compute='_compute_call_year', store=True, readonly=False,
                               aggregator=False,
                               help="The call the project belongs to, from its agreement number: its "
                                    "organisational support rates are that year's, whatever year it is now.")
    amendment_ids = fields.One2many(string="Grant amendments", comodel_name='ems.erasmus.project.amendment',
                                    inverse_name='project_id', groups=ECONOMY_READERS)
    income_ids = fields.One2many(string="SEPIE transfers", comodel_name='ems.erasmus.project.income',
                                 inverse_name='project_id', groups=ECONOMY_READERS)
    expense_ids = fields.One2many(string="Expenses", comodel_name='ems.erasmus.expense', inverse_name='project_id',
                                  groups=ECONOMY_READERS)
    economy_document_ids = fields.One2many(
        string="Grant agreement and economic documents", comodel_name='ems.erasmus.project.document',
        inverse_name='project_id', domain=[('category', '=', '03_Economia')], groups=ECONOMY_READERS,
        help="The grant agreement, its annexes and amendments, budget follow-up... They are the project's documents "
             "of category 03 Finances, also in its export.")
    final_grant = fields.Monetary(string="Final grant", tracking=True, groups=ECONOMY_READERS,
                                  help="What SEPIE finally recognised after the final report.")
    grant_current = fields.Monetary(string="Current grant", compute='_compute_economy', store=True,
                                    groups=ECONOMY_READERS, help="The grant awarded plus its amendments.")
    received_amount = fields.Monetary(string="Received", compute='_compute_economy', store=True,
                                      groups=ECONOMY_READERS, help="What SEPIE has transferred.")
    to_receive_amount = fields.Monetary(string="To receive", compute='_compute_economy', store=True,
                                        groups=ECONOMY_READERS,
                                        help="The current grant minus what SEPIE has transferred.")
    forecast_amount = fields.Monetary(string="Forecast", compute='_compute_economy', store=True,
                                      groups=ECONOMY_READERS,
                                      help="The grants of the mobilities not confirmed yet: they commit no budget.")
    committed_amount = fields.Monetary(string="Committed", compute='_compute_economy', store=True,
                                       groups=ECONOMY_READERS,
                                       help="The confirmed mobilities' grants plus the project's other expenses.")
    paid_amount = fields.Monetary(string="Paid", compute='_compute_economy', store=True, groups=ECONOMY_READERS)
    pending_amount = fields.Monetary(string="Pending payment", compute='_compute_economy', store=True,
                                     groups=ECONOMY_READERS, help="Committed and not paid yet.")
    available_amount = fields.Monetary(string="Available", compute='_compute_economy', store=True,
                                       groups=ECONOMY_READERS,
                                       help="The current grant minus what is committed. It is not the money received: "
                                            "a grant can still be pending to be transferred.")
    other_expense_amount = fields.Monetary(
        string="Other expenses", compute='_compute_economy', store=True, groups=ECONOMY_READERS,
        help="The project's expenses and the invoices of no mobility: not part of any mobility's grant.")
    support_forecast = fields.Monetary(string="Organisational support forecast", compute='_compute_support',
                                       store=True, groups=ECONOMY_READERS,
                                       help="On the planned mobilities, with that call's rates.")
    support_generated = fields.Monetary(string="Organisational support generated", compute='_compute_support',
                                        store=True, groups=ECONOMY_READERS,
                                        help="On the completed and eligible mobilities, with the real participants "
                                             "(accompanying teachers never count), plus the manual correction.")
    support_adjustment = fields.Monetary(string="Correction", tracking=True, groups=ECONOMY_READERS,
                                         help="Added to the organisational support generated (or taken off, if "
                                              "negative), for a particularity of the agreement.")
    support_adjustment_reason = fields.Text(string="Reason for the correction", tracking=True,
                                            groups=ECONOMY_READERS)
    support_expense_amount = fields.Monetary(string="Organisational support expenses", compute='_compute_economy',
                                             store=True, groups=ECONOMY_READERS)
    support_balance = fields.Monetary(
        string="Generated minus spent", compute='_compute_economy', store=True, groups=ECONOMY_READERS,
        help="An internal indicator, not a certification of funds available or recognised by SEPIE. The "
             "organisational support is part of the grant awarded: it is never added to it.")
    legacy_committed = fields.Monetary(string="Committed before EMS", groups=ECONOMY_READERS,
                                       help="Aggregated figure of a project managed before EMS, added to the totals.")
    legacy_paid = fields.Monetary(string="Paid before EMS", groups=ECONOMY_READERS)
    legacy_support_generated = fields.Monetary(string="Organisational support generated before EMS",
                                               groups=ECONOMY_READERS)
    can_manage_economy = fields.Boolean(compute='_compute_can_manage_economy')
    economy_warnings = fields.Html(string="Warnings", compute='_compute_economy_warnings', groups=ECONOMY_READERS)
    economy_warning_count = fields.Integer(string="Number of warnings", compute='_compute_economy_warnings',
                                           groups=ECONOMY_READERS)

    @api.depends_context('uid')
    def _compute_can_manage_economy(self):
        self.can_manage_economy = _is_manager(self.env)

    @api.depends('name')
    def _compute_call_year(self):
        for project in self:
            match = CALL_YEAR.match(project.name or '')
            project.call_year = project.call_year or (int(match.group(1)) if match else 0)

    @api.depends('budget', 'amendment_ids.amount', 'income_ids.amount', 'legacy_committed', 'legacy_paid',
                 'mobility_ids.econ_forecast', 'mobility_ids.econ_committed', 'mobility_ids.econ_paid',
                 'group_mobility_ids.econ_forecast', 'group_mobility_ids.econ_committed',
                 'group_mobility_ids.econ_paid', 'expense_ids.amount', 'expense_ids.state', 'expense_ids.category',
                 'expense_ids.transferred_amount',
                 'invoice_ids.amount', 'invoice_ids.state', 'invoice_ids.mobility_ids',
                 'invoice_ids.group_mobility_id', 'support_generated')
    def _compute_economy(self):
        for project in self:
            mobilities = (project.mobility_ids, project.group_mobility_ids)
            values = {expense: expense._ems_value() for expense in project.expense_ids}
            invoices = project._ems_loose_invoices()
            other = sum(committed for committed, _paid in values.values()) + sum(invoices.mapped('amount'))
            paid_other = sum(paid for _committed, paid in values.values()) \
                + sum(invoices.filtered(lambda invoice: invoice.state == 'paid').mapped('amount'))
            project.grant_current = project.budget + sum(project.amendment_ids.mapped('amount'))
            project.received_amount = sum(project.income_ids.mapped('amount'))
            project.to_receive_amount = project.grant_current - project.received_amount
            project.forecast_amount = sum(sum(records.mapped('econ_forecast')) for records in mobilities)
            project.other_expense_amount = other
            project.committed_amount = sum(sum(records.mapped('econ_committed')) for records in mobilities) + other + project.legacy_committed
            project.paid_amount = sum(sum(records.mapped('econ_paid')) for records in mobilities) + paid_other + project.legacy_paid
            project.pending_amount = project.committed_amount - project.paid_amount
            project.available_amount = project.grant_current - project.committed_amount
            project.support_expense_amount = sum(
                committed for expense, (committed, _paid) in values.items()
                if expense.category == 'organisational_support')
            project.support_balance = project.support_generated - project.support_expense_amount

    @api.depends('call_year', 'kind', 'support_adjustment', 'legacy_support_generated', 'mobility_ids.state',
                 'mobility_ids.support_type', 'mobility_ids.date_start', 'mobility_ids.date_end',
                 'group_mobility_ids.state', 'group_mobility_ids.student_places', 'group_mobility_ids.date_start',
                 'group_mobility_ids.date_end', 'group_mobility_ids.date_start_planned',
                 'group_mobility_ids.participant_ids.state', 'group_mobility_ids.participant_ids.role')
    def _compute_support(self):
        for project in self:
            lines = project._ems_support_lines()
            project.support_forecast = sum(line['forecast'] for line in lines)
            project.support_generated = sum(line['generated'] for line in lines) + project.support_adjustment \
                + project.legacy_support_generated

    @api.depends_context('uid')
    @api.depends('committed_amount', 'grant_current', 'expense_ids.attachment_ids', 'expense_ids.corrected',
                 'mobility_ids.econ_paid')
    def _compute_economy_warnings(self):
        for project in self:
            warnings = project._ems_economy_warnings()
            project.economy_warning_count = len(warnings)
            project.economy_warnings = Markup('<ul class="mb-0">%s</ul>') % Markup().join(
                Markup('<li>%s</li>') % warning for warning in warnings) if warnings else False

    @api.constrains('support_adjustment', 'support_adjustment_reason')
    def _check_support_adjustment(self):
        for project in self:
            if project.support_adjustment and not (project.support_adjustment_reason or '').strip():
                raise ValidationError(_("Say why the organisational support of %s is corrected.", project.name))

    def _ems_invoices(self):
        """Every invoice of the project: its own, its participants' and its group mobilities'."""
        self.ensure_one()
        return self.invoice_ids | self.mobility_ids.provision_ids.invoice_id | self.group_mobility_ids.invoice_ids

    def _ems_loose_invoices(self):
        """The project's invoices for no mobility (a dissemination service, the whole project's
        insurance...): those of a mobility are already part of its grant."""
        self.ensure_one()
        return self.invoice_ids.filtered(lambda invoice: not invoice.mobility_ids and not invoice.group_mobility_id)

    def _ems_support_lines(self):
        """The organisational support, participant by participant (issue #762): each eligible one with
        the rate of the project's call year for their kind of mobility and their position in the
        project (the rates' bands: e.g. up to the 100th participant one amount, beyond another). The
        forecast counts every planned mobility, a group still selecting its student places; what is
        generated, only the completed ones and the group's real students. Accompanying teachers never
        count. A line with no rate or no dates says what is missing."""
        self.ensure_one()
        project = self.sudo()
        rates = self.env['ems.erasmus.support.rate'].sudo().search(
            [('call_year', '=', project.call_year), ('kind', '=', project.kind)])
        people = []
        for mobility in project.mobility_ids.filtered(lambda mobility: mobility.state != 'cancelled'):
            people.append({'name': mobility.partner_id.name, 'type': mobility.support_type,
                           'start': mobility.date_start, 'end': mobility.date_end,
                           'done': mobility.state == 'done', 'key': (mobility._name, mobility.id)})
        for group in project.group_mobility_ids.filtered(lambda group: group.state != 'cancelled'):
            start, end = group.date_start or group.date_start_planned, group.date_end or group.date_end_planned
            if group.state in GROUP_PLANNING_STATES:
                names = [_("%(group)s, place %(place)s", group=group.name, place=place)
                         for place in range(1, group.student_places + 1)]
            else:
                names = group.participant_ids.filtered(
                    lambda participant: participant.role == 'student' and participant.state == 'active'
                ).partner_id.mapped('name')
            people += [{'name': name, 'type': 'student_group', 'start': start, 'end': end, 'group': group.name,
                        'done': group.state in GROUP_DONE_STATES, 'key': (group._name, group.id, index)}
                       for index, name in enumerate(names)]
        people.sort(key=lambda person: (person['start'] or fields.Date.to_date('9999-12-31'), person['key']))
        counters = defaultdict(int)
        for person in people:
            person['days'] = person['start'] and person['end'] and (person['end'] - person['start']).days + 1
            person['forecast'] = person['generated'] = 0.0
            for measure, counts in (('forecast', True), ('generated', person['done'])):
                if not counts:
                    continue
                # The participant's position among those of their kind and among the whole project.
                counters[(measure, person['type'])] += 1
                counters[measure] += 1
                positions = {'same': counters[(measure, person['type'])], 'project': counters[measure]}
                rate, missing = rates._ems_rate_for(person['type'], positions, person['days'])
                # The position the rate counted: among the same kind, or the whole project (KA131-HED).
                person[f'{measure}_position'] = positions[rate.band_scope or 'same']
                person['missing'] = person.get('missing') or missing
                person['rate'] = rate
                person[measure] = rate.amount if rate else 0.0
        return people

    def _ems_economy_warnings(self):
        """What may be a mistake, explained; it blocks nothing (issue #762, section I)."""
        self.ensure_one()
        project = self.sudo()
        warnings = []
        money = lambda amount: formatLang(self.env, amount, currency_obj=project.currency_id)
        if project.committed_amount > project.grant_current:
            warnings.append(_("What is committed (%(committed)s) is above the current grant (%(grant)s) by %(over)s.",
                              committed=money(project.committed_amount), grant=money(project.grant_current),
                              over=money(project.committed_amount - project.grant_current)))
        expenses = project.expense_ids.filtered(lambda expense: expense.state != 'cancelled')
        if without := expenses.filtered(lambda expense: not expense.attachment_ids):
            warnings.append(_("Expenses without an invoice or receipt: %s.",
                              ", ".join(expense.name or expense.concept for expense in without)))
        pending_payments = project.payment_ids.filtered(lambda payment: payment.state == 'to_pay')
        pending_invoices = project._ems_invoices().filtered(lambda invoice: invoice.state == 'to_pay')
        pending_expenses = expenses.filtered(lambda expense: expense.state == 'to_pay')
        if count := len(pending_payments) + len(pending_invoices) + len(pending_expenses):
            amount = sum(pending_payments.mapped('amount')) + sum(pending_invoices.mapped('amount')) \
                + sum(pending_expenses.mapped('amount'))
            warnings.append(_("%(count)s payments to make (%(amount)s): grant payments, invoices and expenses still "
                              "to transfer.", count=count, amount=money(amount)))
        if corrected := project.expense_ids.filtered('corrected'):
            warnings.append(_("Expenses changed after being paid (see their history): %s.",
                              ", ".join(corrected.mapped('name'))))
        for expense in expenses.filtered(lambda expense: expense.state == 'paid'
                                         and expense.transferred_amount > expense.amount):
            warnings.append(_("%(name)s was paid %(over)s above its corrected amount: ask for it back, then "
                              "undo the transfer and register the right one.", name=expense.name,
                              over=money(expense.transferred_amount - expense.amount)))
        for mobility in project.mobility_ids:
            if mobility.state != 'cancelled' and mobility.grant_amount and mobility.econ_paid > mobility.grant_amount:
                warnings.append(_("%(name)s has been paid %(paid)s, above their grant of %(grant)s: was the grant "
                                  "changed after paying?", name=mobility.partner_id.name,
                                  paid=money(mobility.econ_paid), grant=money(mobility.grant_amount)))
            if mobility.state == 'cancelled' and mobility.econ_paid > 0:
                warnings.append(_("The mobility of %(name)s is cancelled with %(paid)s paid: record what has to be "
                                  "given back, or keep it if it is an eligible cost.", name=mobility.partner_id.name,
                                  paid=money(mobility.econ_paid)))
        for group in project.group_mobility_ids.filtered(lambda group: group.state == 'cancelled' and group.econ_paid):
            warnings.append(_("The group mobility %(name)s is cancelled with %(paid)s paid.", name=group.name,
                              paid=money(group.econ_paid)))
        missing = [line for line in project._ems_support_lines() if line.get('missing')]
        if missing:
            warnings.append(_("Not enough information to compute the organisational support of %(count)s "
                              "participants (e.g. %(name)s: %(reason)s).", count=len(missing),
                              name=missing[0]['name'], reason=missing[0]['missing']))
        return warnings

    def action_export_economy(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': f'/ems/erasmus/project/{self.id}/economy', 'target': 'download'}

    def _ems_economy_xlsx(self):
        """The project's economy as an .xlsx (issue #762, section H): the same figures as the panel,
        forecast, committed and paid apart. Built on the fly, never stored; for whoever reads the
        economy."""
        self.ensure_one()
        if not self.env.user.has_groups(ECONOMY_READERS):
            raise AccessError(_("Only the Erasmus+ team, the Secretary and the Director export a project's economy."))
        project = self.sudo()
        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {'in_memory': True})
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        def sheet(name, headers, rows, widths=18):
            worksheet = workbook.add_worksheet(name[:31])
            worksheet.write_row(0, 0, headers, bold)
            for row, values in enumerate(rows, start=1):
                for column, value in enumerate(values):
                    if isinstance(value, float):
                        worksheet.write_number(row, column, value, money)
                    elif hasattr(value, 'year') and value:
                        worksheet.write_datetime(row, column, fields.Datetime.to_datetime(value), date_format)
                    else:
                        worksheet.write(row, column, value if value not in (None, False) else '')
            worksheet.set_column(0, len(headers) - 1, widths)
            return worksheet

        kinds = dict(self._fields['kind']._description_selection(self.env))
        states = dict(self.env['ems.erasmus.economy']._fields['econ_state']._description_selection(self.env))
        amounts = [
            (_("Grant awarded"), project.budget), (_("Amendments"), project.grant_current - project.budget),
            (_("Current grant"), project.grant_current), (_("Final grant"), project.final_grant),
            (_("Received from SEPIE"), project.received_amount), (_("To receive"), project.to_receive_amount),
            (_("Forecast"), project.forecast_amount), (_("Committed"), project.committed_amount),
            (_("Paid"), project.paid_amount), (_("Pending payment"), project.pending_amount),
            (_("Available"), project.available_amount), (_("Other expenses"), project.other_expense_amount),
            (_("Organisational support forecast"), project.support_forecast),
            (_("Organisational support generated"), project.support_generated),
            (_("Organisational support expenses"), project.support_expense_amount),
            (_("Generated minus spent"), project.support_balance),
        ]
        sheet(_("Summary"), [_("Concept"), _("Amount")],
              [(_("Project"), project.name), (_("Kind"), kinds.get(project.kind, '')),
               (_("Call year"), project.call_year)] + [(label, float(value)) for label, value in amounts], widths=36)
        mobility_rows = [(mobility.partner_id.name, _("Individual"), mobility.call_id.name,
                          states.get(mobility.econ_state, ''), float(mobility.grant_amount),
                          float(mobility.econ_forecast), float(mobility.econ_committed), float(mobility.econ_paid),
                          float(mobility.econ_pending), float(mobility.recovered_amount))
                         for mobility in project.mobility_ids]
        mobility_rows += [(group.name, _("Group"), '', states.get(group.econ_state, ''), float(group.grant_amount),
                           float(group.econ_forecast), float(group.econ_committed), float(group.econ_paid),
                           float(group.econ_pending), float(group.recovered_amount))
                          for group in project.group_mobility_ids]
        sheet(_("Grants"), [_("Mobility"), _("Kind"), _("Call"), _("Economic state"), _("Grant"), _("Forecast"),
                            _("Committed"), _("Paid"), _("Pending payment"), _("Given back")], mobility_rows)
        pay_states = dict(self.env['ems.erasmus.payment']._fields['state']._description_selection(self.env))
        pay_kinds = dict(self.env['ems.erasmus.payment']._fields['kind']._description_selection(self.env))
        invoices = project._ems_invoices()
        payment_rows = [(payment.partner_id.name, _("Pocket money") if payment.group_participant_id else
                         _("Grant payment"), pay_kinds.get(payment.kind, ''),
                         float(payment.amount), pay_states.get(payment.state, ''), payment.request_date,
                         payment.paid_date, ", ".join(payment.receipt_ids.mapped('name')))
                        for payment in project.payment_ids]
        payment_rows += [(invoice.supplier_id.name or '', _("Invoice %s", invoice.name),
                          invoice.group_mobility_id.name or ", ".join(invoice.mobility_ids.partner_id.mapped('name')),
                          float(invoice.amount), pay_states.get(invoice.state, ''), invoice.date, invoice.paid_date,
                          ", ".join((invoice.receipt_ids.mapped('name')) + ([invoice.document_filename]
                                                                            if invoice.document_filename else [])))
                         for invoice in invoices]
        sheet(_("Payments"), [_("Paid to"), _("Kind"), _("Concept"), _("Amount"), _("State"), _("Date"),
                              _("Paid on"), _("Receipts")], payment_rows)
        categories = dict(self.env['ems.erasmus.expense']._fields['category']._description_selection(self.env))
        expense_states = dict(self.env['ems.erasmus.expense']._fields['state']._description_selection(self.env))
        sheet(_("Expenses"), [_("Reference"), _("Date"), _("Concept"), _("Category"), _("Supplier"), _("Mobility"),
                              _("Amount"), _("State"), _("Paid on"), _("Invoice or receipt"), _("Changed after payment")],
              [(expense.name, expense.date, expense.concept, categories.get(expense.category, ''),
                expense.supplier_id.name or '', expense.mobility_id.partner_id.name or '', float(expense.amount),
                expense_states.get(expense.state, ''), expense.paid_date,
                ", ".join(expense.attachment_ids.mapped('name') + expense.receipt_ids.mapped('name')),
                _("Yes") if expense.corrected else '') for expense in project.expense_ids])
        types = dict(self.env['ems.erasmus.support.rate']._fields['mobility_type']._description_selection(self.env))
        sheet(_("Organisational support"), [_("Participant"), _("Kind"), _("Start"), _("Days"), _("Position"),
                                            _("Forecast"), _("Generated"), _("Missing information")],
              [(line['name'], types.get(line['type'], ''), line['start'], line['days'] or '',
                line.get('generated_position') or line.get('forecast_position') or '', float(line['forecast']),
                float(line['generated']), line.get('missing') or '') for line in project._ems_support_lines()])
        income_kinds = dict(self.env['ems.erasmus.project.income']._fields['kind']._description_selection(self.env))
        sheet(_("Grant and income"), [_("Kind"), _("Date"), _("Amount"), _("Description")],
              [(_("Grant awarded"), project.date_start, float(project.budget), '')]
              + [(_("Amendment"), amendment.date, float(amendment.amount), amendment.name or '')
                 for amendment in project.amendment_ids]
              + [(_("SEPIE transfer: %s", income_kinds.get(income.kind, '')), income.date, float(income.amount),
                  income.name or '') for income in project.income_ids])
        workbook.close()
        return stream.getvalue()


class EmsErasmusSupportRate(models.Model):
    """Issue #762 - the organisational support per participant, as each call's funding rules set
    it: per call year, Erasmus+ action and kind of mobility, optionally per band of participants
    (their position in the project) and a minimum duration. An old project keeps its year's rates."""
    _name = 'ems.erasmus.support.rate'
    _description = 'Erasmus+ organisational support rate'
    _order = 'call_year desc, kind, mobility_type, band_from'

    call_year = fields.Integer(string="Call year", required=True, aggregator=False)
    kind = fields.Selection(string="Action", selection=PROJECTS, required=True)
    mobility_type = fields.Selection(string="Mobility", selection=SUPPORT_TYPES, required=True,
                                     default='student_short')
    band_scope = fields.Selection(string="Count the participants of", selection=BAND_SCOPES, required=True,
                                  default='same',
                                  help="For the band: the participant's position among those of the same kind of "
                                       "mobility (KA121-VET), or among every participant of the project, students "
                                       "and staff together (KA131-HED).")
    band_from = fields.Integer(string="From participant", required=True, default=1,
                               help="Position of the participant, in order of start date: e.g. 101 for a lower "
                                    "amount from the 101st participant on.")
    band_to = fields.Integer(string="Up to participant", help="Empty or 0: no limit.")
    min_days = fields.Integer(string="Minimum days", help="Shorter stays generate no organisational support.")
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency',
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string="Amount per participant", required=True)
    note = fields.Char(string="Conditions", help="Other eligibility conditions of the funding rules, as a reminder.")

    @api.constrains('call_year', 'kind', 'mobility_type', 'band_from', 'band_to')
    def _check_bands(self):
        for rate in self:
            if rate.band_from < 1 or (rate.band_to and rate.band_to < rate.band_from):
                raise ValidationError(_("A band goes from participant 1 or later up to a participant after it."))
            others = self.search([('id', '!=', rate.id), ('call_year', '=', rate.call_year), ('kind', '=', rate.kind),
                                  ('mobility_type', '=', rate.mobility_type)])
            for other in others:
                if rate.band_from <= (other.band_to or float('inf')) and other.band_from <= (rate.band_to or float('inf')):
                    raise ValidationError(_(
                        "This band overlaps another rate of %(rate)s, from participant %(start)s to %(end)s. Change "
                        "one of them so that each participant falls in a single band.", rate=other.display_name,
                        start=other.band_from, end=other.band_to or _("no limit")))

    def _compute_display_name(self):
        types = dict(self._fields['mobility_type']._description_selection(self.env))
        kinds = dict(self._fields['kind']._description_selection(self.env))
        for rate in self:
            rate.display_name = f"{rate.call_year} {kinds.get(rate.kind, '')} - {types.get(rate.mobility_type, '')}"

    def _ems_rate_for(self, mobility_type, positions, days):
        """The rate among self for this participant, its position counted as each rate says
        (`positions`: {'same': ..., 'project': ...}), and why there is none."""
        rates = self.filtered(lambda rate: rate.mobility_type == mobility_type
                              and rate.band_from <= positions[rate.band_scope]
                              and (not rate.band_to or positions[rate.band_scope] <= rate.band_to))
        if not rates:
            return self.browse(), _("no organisational support rate for this call year and mobility")
        rate = rates[:1]
        if rate.min_days and not days:
            return self.browse(), _("the mobility has no dates")
        if rate.min_days and days < rate.min_days:
            return self.browse(), False
        return rate, False

    @api.model_create_multi
    def create(self, vals_list):
        rates = super().create(vals_list)
        self._ems_recompute_projects(rates.mapped('call_year'))
        return rates

    def write(self, vals):
        years = self.mapped('call_year')
        result = super().write(vals)
        self._ems_recompute_projects(years + self.mapped('call_year'))
        return result

    def unlink(self):
        years = self.mapped('call_year')
        result = super().unlink()
        self._ems_recompute_projects(years)
        return result

    @api.model
    def _ems_recompute_projects(self, years):
        """The projects of these call years compute their organisational support again: a rate is
        no field they depend on, so they are told (the dependent figures follow)."""
        projects = self.env['ems.erasmus.project'].sudo().with_context(active_test=False).search(
            [('call_year', 'in', list(set(years)))])
        projects.modified(['call_year'])


class EmsErasmusProjectLine(models.AbstractModel):
    """What the project's amendments and SEPIE's transfers share: every change stays in the
    project's history."""
    _name = 'ems.erasmus.project.line'
    _description = 'Erasmus+ project economic line'
    _inherit = ['ems.attachment_link_mixin']

    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', required=True,
                                 ondelete='cascade', index=True)
    date = fields.Date(string="Date", required=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    currency_id = fields.Many2one(string="Currency", related='project_id.currency_id')
    amount = fields.Monetary(string="Amount", required=True)
    name = fields.Char(string="Description")
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment')

    @api.model_create_multi
    def create(self, vals_list):
        _check_manager(self.env)
        lines = super().create(vals_list)
        for line in lines:
            line._ems_log(_("added"))
        return lines

    def write(self, vals):
        _check_manager(self.env)
        before = {line: line._ems_summary() for line in self}
        result = super().write(vals)
        for line in self:
            line._ems_log(_("changed (it was %s)", before[line]))
        return result

    def unlink(self):
        _check_manager(self.env)
        for line in self:
            line._ems_log(_("deleted"))
        return super().unlink()

    def _ems_summary(self):
        self.ensure_one()
        summary = f"{format_date(self.env, self.date)}, {formatLang(self.env, self.amount, currency_obj=self.currency_id)}"
        return f"{summary} ({self.name})" if self.name else summary

    def _ems_label(self):
        raise NotImplementedError()

    def _ems_log(self, what):
        self.ensure_one()
        self.project_id.sudo().message_post(
            body=Markup("%s: %s - %s") % (self._ems_label(), escape(self._ems_summary()), what),
            message_type='notification', subtype_xmlid='mail.mt_note')


class EmsErasmusProjectAmendment(models.Model):
    """Issue #762 - an amendment of the project's grant (an increase, or a reduction if negative)."""
    _name = 'ems.erasmus.project.amendment'
    _description = 'Erasmus+ grant amendment'
    _inherit = ['ems.erasmus.project.line']
    _order = 'date, id'

    attachment_ids = fields.Many2many(relation='ems_erasmus_project_amendment_attachment_rel')

    def _ems_label(self):
        return _("Grant amendment")


class EmsErasmusProjectIncome(models.Model):
    """Issue #762 - a transfer SEPIE made to the centre for the project. The balance sets the
    project's final payment date (from which its documents are kept), if not set yet."""
    _name = 'ems.erasmus.project.income'
    _description = 'Erasmus+ SEPIE transfer'
    _inherit = ['ems.erasmus.project.line']
    _order = 'date, id'

    kind = fields.Selection(string="Type", selection=INCOME_KINDS, required=True, default='prefinancing')
    attachment_ids = fields.Many2many(relation='ems_erasmus_project_income_attachment_rel')

    def _ems_label(self):
        return _("SEPIE transfer")

    @api.model_create_multi
    def create(self, vals_list):
        incomes = super().create(vals_list)
        for income in incomes.filtered(lambda income: income.kind == 'balance'):
            if not income.project_id.final_payment_date:
                income.project_id.sudo().final_payment_date = income.date
        return incomes

    @api.constrains('amount')
    def _check_amount(self):
        for income in self:
            if income.amount <= 0:
                raise ValidationError(_("A transfer from SEPIE is an amount above zero."))


class EmsErasmusExpense(models.Model):
    """Issue #762 - an expense of the project outside the participants' grants (a working meal,
    merchandising, dissemination services, language preparation...), in one of two categories:
    organisational support or other project expenses. Registered by the Erasmus team or the
    Secretary; the Secretary pays it with the same transfer wizard as the grants and invoices. Once
    paid, its figures change only through the correction wizard, which keeps the reason."""
    _name = 'ems.erasmus.expense'
    _description = 'Erasmus+ project expense'
    _inherit = ['ems.base', 'ems.attachment_link_mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", compute='_compute_name', store=True, index=True)
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', required=True, tracking=True,
                                 ondelete='restrict', index=True)
    concept = fields.Char(string="Concept", required=True, tracking=True)
    category = fields.Selection(string="Category", selection=EXPENSE_CATEGORIES, required=True, default='other',
                                tracking=True)
    date = fields.Date(string="Date", required=True, tracking=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    currency_id = fields.Many2one(string="Currency", related='project_id.currency_id')
    amount = fields.Monetary(string="Amount", required=True, tracking=True)
    supplier_id = fields.Many2one(string="Supplier", comodel_name='res.partner', tracking=True)
    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', tracking=True,
                                  domain="[('project_id', '=', project_id)]",
                                  help="Optional: the mobility it is about. It is not part of its grant.")
    attachment_ids = fields.Many2many(string="Invoice or receipt", comodel_name='ir.attachment',
                                      relation='ems_erasmus_expense_attachment_rel')
    notes = fields.Text(string="Notes")
    state = fields.Selection(string="State", selection=EXPENSE_STATES, required=True, default='to_pay',
                             readonly=True, tracking=True)
    paid_date = fields.Date(string="Paid on", readonly=True)
    paid_by_id = fields.Many2one(string="Marked paid by", comodel_name='res.users', readonly=True)
    receipt_ids = fields.Many2many(string="Transfer receipts", comodel_name='ir.attachment',
                                   relation='ems_erasmus_expense_receipt_rel', readonly=True,
                                   help="Added by the Secretary when registering the transfer.")
    corrected = fields.Boolean(string="Changed after payment", readonly=True, tracking=True)
    counted_amount = fields.Monetary(string="Counted", compute='_compute_counted_amount', store=True,
                                     help="What it consumes of the project's budget: nothing once cancelled; what "
                                          "was transferred, if more than its corrected amount.")
    transferred_amount = fields.Monetary(string="Transferred", readonly=True,
                                         help="What the Secretary transferred when registering the payment.")
    corrected_from_id = fields.Many2one(string="Difference of", comodel_name='ems.erasmus.expense', readonly=True,
                                        ondelete='restrict',
                                        help="The paid expense whose correction raised its amount: this one is "
                                             "the difference still to pay.")
    can_manage = fields.Boolean(compute='_compute_can_manage')

    @api.depends('create_date')
    def _compute_name(self):
        for expense in self:
            # _origin: in a form not saved yet (the project's Economy tab) a saved expense is a new record.
            origin = expense._origin
            year = (origin.create_date or fields.Datetime.now()).year
            expense.name = f"DESP-{year}-{origin.id:05d}" if origin.id else False

    @api.depends_context('uid')
    def _compute_can_manage(self):
        self.can_manage = _is_manager(self.env)

    @api.depends('amount', 'state', 'transferred_amount')
    def _compute_counted_amount(self):
        for expense in self:
            expense.counted_amount = expense._ems_value()[0]

    @api.constrains('amount')
    def _check_amount(self):
        for expense in self:
            if expense.amount <= 0:
                raise ValidationError(_("An expense is an amount above zero."))

    @api.constrains('project_id', 'mobility_id')
    def _check_mobility(self):
        for expense in self:
            if expense.mobility_id and expense.mobility_id.project_id != expense.project_id:
                raise ValidationError(_("An expense is only about a mobility of its own project."))

    @api.model_create_multi
    def create(self, vals_list):
        check_workflow_create(self, vals_list, extra=EXPENSE_WORKFLOW_FIELDS)
        expenses = super().create(vals_list)
        _ask_transfer(expenses)
        return expenses

    def write(self, vals):
        _check_transfer_fields(self, vals)
        check_workflow_write(self, vals, extra=EXPENSE_WORKFLOW_FIELDS)
        if not self.env.su and EXPENSE_ECONOMIC_FIELDS & set(vals) \
                and self.filtered(lambda expense: expense.state != 'to_pay'):
            raise UserError(_("A paid or cancelled expense changes only through \"Correct\", which keeps the reason."))
        result = super().write(vals)
        # What was really transferred: a later correction downwards does not change it.
        if 'state' in vals:
            for expense in self.sudo():
                transferred = expense.amount if expense.state == 'paid' else 0.0
                if expense.transferred_amount != transferred:
                    super(EmsErasmusExpense, expense).write({'transferred_amount': transferred})
        return result

    def _ems_value(self):
        """What the expense consumes of the project and what has been paid of it: its amount, or what
        was transferred if that is more (corrected downwards after paying, until it is given back)."""
        self.ensure_one()
        if self.state == 'cancelled':
            return 0.0, 0.0
        paid = self.transferred_amount if self.state == 'paid' else 0.0
        return max(self.amount, paid), paid

    def unlink(self):
        if self.filtered(lambda expense: expense.state == 'paid'):
            raise UserError(_("A paid expense cannot be deleted."))
        return super().unlink()

    def _ems_transfer_summary(self):
        self.ensure_one()
        return _("Erasmus+: pay the expense %(reference)s, %(concept)s (%(amount)s)", reference=self.name,
                 concept=self.concept, amount=formatLang(self.env, self.amount, currency_obj=self.currency_id))

    def _ems_correction_summary(self):
        self.ensure_one()
        categories = dict(self._fields['category']._description_selection(self.env))
        return f"{self.project_id.name}, {self.concept}, {categories.get(self.category)}, " \
               f"{format_date(self.env, self.date)}, {formatLang(self.env, self.amount, currency_obj=self.currency_id)}"

    def action_register_transfer(self):
        if self.filtered(lambda expense: expense.state != 'to_pay'):
            raise UserError(_("Only an expense registered and not paid is paid."))
        return _transfer_wizard_action(self)

    def action_mark_unpaid(self):
        return _undo_wizard_action(self)

    def action_cancel(self):
        """A registered expense that will not be paid; a paid one is first undone by the Secretary."""
        _check_manager(self.env)
        if self.filtered(lambda expense: expense.state != 'to_pay'):
            raise UserError(_("Only an expense not paid yet is cancelled: undo its transfer first."))
        self.sudo().write({'state': 'cancelled'})
        self.sudo().activity_ids.action_feedback()

    def action_restore(self):
        _check_manager(self.env)
        cancelled = self.filtered(lambda expense: expense.state == 'cancelled')
        cancelled.sudo().write({'state': 'to_pay'})
        _ask_transfer(cancelled)

    def action_correct(self):
        self.ensure_one()
        _check_manager(self.env)
        return {'type': 'ir.actions.act_window', 'name': _("Correct the expense"),
                'res_model': 'ems.erasmus.expense.correct.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'default_expense_id': self.id, 'default_amount': self.amount,
                            'default_concept': self.concept, 'default_category': self.category,
                            'default_project_id': self.project_id.id, 'default_date': self.date}}


class EmsErasmusExpenseCorrectWizard(models.TransientModel):
    """Issue #762 - the Erasmus coordination corrects a paid expense: its new figures and why. The
    change and the reason stay in its history, and the project warns about it."""
    _name = 'ems.erasmus.expense.correct.wizard'
    _description = 'Erasmus+ correct an expense'

    expense_id = fields.Many2one(string="Expense", comodel_name='ems.erasmus.expense', required=True)
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', required=True)
    concept = fields.Char(string="Concept", required=True)
    category = fields.Selection(string="Category", selection=EXPENSE_CATEGORIES, required=True)
    date = fields.Date(string="Date", required=True)
    currency_id = fields.Many2one(string="Currency", related='project_id.currency_id')
    amount = fields.Monetary(string="Amount", required=True)
    reason = fields.Text(string="Reason", required=True, help="Why it is corrected: it stays in its history.")

    def action_confirm(self):
        self.ensure_one()
        _check_manager(self.env)
        if not (self.reason or '').strip():
            raise UserError(_("Write the reason for the correction first."))
        expense = self.expense_id
        before = expense._ems_correction_summary()
        # adriamt, 2026-11-05: corrected upwards once paid, what was transferred stays paid and the
        # difference is a new expense the Secretary is asked to pay.
        difference = self.amount - expense.transferred_amount if expense.state == 'paid' else 0.0
        amount = expense.transferred_amount if difference > 0 else self.amount
        expense.sudo().write({'project_id': self.project_id.id, 'concept': self.concept, 'category': self.category,
                              'date': self.date, 'amount': amount,
                              'corrected': expense.corrected or expense.state != 'to_pay'})
        body = _("Corrected by %(user)s: %(reason)s. Before: %(before)s.", user=self.env.user.name,
                 reason=self.reason.strip(), before=before)
        if difference > 0:
            pending = expense.sudo().create({
                'project_id': expense.project_id.id, 'category': expense.category, 'date': expense.date,
                'supplier_id': expense.supplier_id.id, 'mobility_id': expense.mobility_id.id,
                'amount': difference, 'corrected_from_id': expense.id,
                'concept': _("%(concept)s (difference after correcting %(reference)s)", concept=self.concept,
                             reference=expense.name)})
            body = _("%(body)s The %(difference)s above what was paid is to pay in %(reference)s.", body=body,
                     difference=formatLang(self.env, difference, currency_obj=expense.currency_id),
                     reference=pending.name)
        expense.message_post(body=body, message_type='notification', subtype_xmlid='mail.mt_note')
        return {'type': 'ir.actions.act_window_close'}


class EmsErasmusTransferWizard(models.TransientModel):
    """The Secretary pays the project's expenses with the same transfer as grants and invoices."""
    _inherit = 'ems.erasmus.transfer.wizard'

    expense_ids = fields.Many2many(string="Expenses", comodel_name='ems.erasmus.expense',
                                   relation='ems_erasmus_transfer_wizard_expense_rel')


class EmsErasmusUndoTransferWizard(models.TransientModel):
    _inherit = 'ems.erasmus.undo.transfer.wizard'

    expense_ids = fields.Many2many(string="Expenses", comodel_name='ems.erasmus.expense',
                                   relation='ems_erasmus_undo_transfer_wizard_expense_rel')
