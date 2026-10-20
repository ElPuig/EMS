# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval

from .common import QUALITY_STATE_CLOSED, QUALITY_STATES, scope_code


# What the responsible people may write on an agreement whose content they do not manage: the
# description, which explains how to carry it out. Its progress goes in follow-up entries.
PROGRESS_FIELDS = {'description'}


class EmsQualityAction(models.Model):
    _name = "ems.quality.action"
    _description = "Quality action: a meeting agreement or an improvement action, which are the same thing."
    _inherit = ['ems.quality.can.edit', 'mail.thread', 'mail.activity.mixin']
    _order = "deadline_date, id desc"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another action already uses this code."),
    ]

    code = fields.Char(string="Code", readonly=True, copy=False, index=True)
    name = fields.Char(string="Content", required=True, tracking=True)
    description = fields.Html(string="Description")
    # One model for both because they are the same concept - owner, deadline, follow-up, closure -
    # and unifying them is what makes a single "what do I owe and by when" screen possible.
    type = fields.Selection(
        string="Type",
        selection=[
            ('agreement', "Agreement"),
            ('immediate', "Immediate action"),
            ('repair', "Repair action"),
            ('corrective', "Corrective action"),
            ('preventive', "Preventive action"),
            ('improvement', "Improvement action"),
            ('change', "Change plan"),
        ],
        required=True,
        default='agreement',
        tracking=True,
    )
    responsible_role_id = fields.Many2one(string="Responsible post", comodel_name="ems.role", tracking=True)
    # The centre's own records hold values like "<name> + volunteers" or "management team and
    # department heads", so several people must be expressible alongside the post.
    responsible_employee_ids = fields.Many2many(
        string="Responsible people",
        comodel_name="hr.employee.public",
        relation="ems_quality_action_employee_rel",
        column1="action_id",
        column2="employee_id",
    )
    # Whoever has to do something about it (a whole department updating its syllabuses) without
    # managing it: they read it and its follow-up, and hear of its progress as followers.
    involved_employee_ids = fields.Many2many(
        string="People involved",
        comodel_name="hr.employee.public",
        relation="ems_quality_action_involved_employee_rel",
        column1="action_id",
        column2="employee_id",
        help="They read the agreement and its follow-up and are told of its progress, but do not manage it.",
    )
    # The responsible people and everybody above them in the chain of command (their Department
    # or Seminar Chief, Head or Deputy Head of Studies, the Director): what the record rules match.
    # compute_sudo: Odoo checks record rules in memory (filtered_domain), which computes this very
    # field; computed as the user, its own read of the record would hit that check half-computed.
    responsible_scope_user_ids = fields.Many2many(
        string="Responsible chain of command", comodel_name="res.users",
        compute="_compute_responsible_scope_user_ids", search="_search_responsible_scope_user_ids", compute_sudo=True)
    deadline_date = fields.Date(string="Deadline", tracking=True)
    # Real deadlines are often prose ("by the final meeting of the year"), so both are kept: the
    # date is what the overdue filter uses, the text is what the minute actually said.
    deadline_text = fields.Char(string="Deadline (as agreed)", help="When the deadline was agreed as a description rather than a date.")
    resources = fields.Char(string="Resources")
    completion_criteria = fields.Text(string="When will it be finished")
    efficacy_criteria = fields.Text(string="How will efficacy be measured")
    minute_id = fields.Many2one(
        string="Minute",
        comodel_name="ems.minute",
        ondelete='cascade',
        index=True,
        help="The minute this agreement was taken in. Later phases add the other origins.",
    )
    course_id = fields.Many2one(
        string="Course",
        comodel_name="ems.course",
        required=True,
        default=lambda self: self.env['ems.course'].search([('is_current', '=', True)], limit=1),
        tracking=True,
    )
    # Scope: drives the code sequence, the search facets and the record rules.
    department_id = fields.Many2one(string="Department", comodel_name="hr.department", tracking=True)
    workgroup_id = fields.Many2one(string="Workgroup", comodel_name="ems.workgroup", tracking=True)
    group_id = fields.Many2one(string="Group", comodel_name="ems.group", tracking=True)
    is_centre = fields.Boolean(string="Centre-wide", tracking=True, help="For agreements of a staff meeting or of the management review, which hang off no department.")
    scope_name = fields.Char(string="Scope", compute="_compute_scope_name", store=True)
    followup_ids = fields.One2many(string="Follow-up", comodel_name="ems.quality.followup", inverse_name="action_id")
    state = fields.Selection(
        string="State",
        selection=QUALITY_STATES,
        compute="_compute_state",
        store=True,
        tracking=True,
        help="Derived from the latest follow-up entry: to move it forward, add one.",
    )
    is_late = fields.Boolean(string="Overdue", compute="_compute_is_late", store=True)
    can_manage_content = fields.Boolean(
        string="Can manage the content", compute="_compute_can_manage_content",
        help="Whether the current user may change what was agreed, and not only its description and follow-up.")
    is_responsible = fields.Boolean(
        string="Is responsible", compute="_compute_is_responsible",
        help="Whether the current user answers for the agreement: one of its responsible people, a holder of the "
             "responsible post, somebody above them in the chain of command, or the administrator.")
    can_follow_up = fields.Boolean(string="Can follow it up", compute="_compute_can_follow_up", help="Whether the current user may add follow-up entries.")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('department_id', 'workgroup_id', 'group_id', 'is_centre')
    def _compute_scope_name(self):
        for action in self:
            action.scope_name = action._scope_label()

    @api.depends('followup_ids', 'followup_ids.state', 'followup_ids.date', 'responsible_role_id', 'responsible_employee_ids', 'deadline_date', 'deadline_text')
    def _compute_state(self):
        """The rule the centre's own spreadsheets implement, kept deliberately.

        There is no editable state field: moving an action forward means adding a follow-up
        entry, which is what keeps the reason on the record."""
        for action in self:
            latest = action._latest_followup()
            if latest:
                action.state = latest.state
            elif action.responsible_role_id or action.responsible_employee_ids or action.deadline_date or action.deadline_text:
                action.state = 'analysed'
            else:
                action.state = 'new'

    @api.depends('responsible_employee_ids')
    def _compute_responsible_scope_user_ids(self):
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        for action in self:
            action.responsible_scope_user_ids = Employee.browse(action.responsible_employee_ids.ids).tutor_scope_user_ids

    def _search_responsible_scope_user_ids(self, operator, value):
        if operator not in ('=', 'in'):
            raise NotImplementedError(_("Unsupported search on responsible_scope_user_ids"))
        responsibles = self.env['hr.employee'].sudo().with_context(active_test=False).search([('tutor_scope_user_ids', operator, value)])
        return [('responsible_employee_ids', 'in', responsibles.ids)]

    @api.depends_context('uid')
    def _compute_can_manage_content(self):
        managed = self._ems_content_managed()
        for action in self:
            action.can_manage_content = not action.id or action in managed

    @api.depends('responsible_employee_ids', 'responsible_role_id')
    @api.depends_context('uid')
    def _compute_is_responsible(self):
        """The agreement's form keeps its description for them; the minute's writers edit it from
        the minute instead."""
        user = self.env.user
        is_admin = user.has_group('ems.group_academic_admin')
        for action in self:
            action.is_responsible = (is_admin or user in action.responsible_scope_user_ids
                                     or user in action.responsible_role_id.sudo().employee_ids.user_id)

    @api.depends('responsible_employee_ids', 'responsible_role_id')
    @api.depends_context('uid')
    def _compute_can_follow_up(self):
        """Whoever manages the content and whoever answers for the agreement: the same split as
        the follow-up's record rules."""
        for action in self:
            action.can_follow_up = action.can_edit or action.is_responsible

    @api.depends('deadline_date', 'state')
    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for action in self:
            action.is_late = bool(action.deadline_date) and action.state != QUALITY_STATE_CLOSED and action.deadline_date < today

    @api.model
    def _ems_department_chiefs(self, department):
        """Who answers for what a department agrees when nobody in particular was named: its
        Department Chief and its Seminar Chief, when it has one."""
        department = self.env['hr.department'].sudo().browse(department.id if department else False)
        return self.env['hr.employee.public'].browse((department.manager_id | department.seminar_chief_id).ids)

    @api.onchange('is_centre')
    def _onchange_is_centre(self):
        """One scope at a time: a centre-wide agreement belongs to no department, group or workgroup."""
        if self.is_centre:
            self.department_id = self.workgroup_id = self.group_id = False

    @api.onchange('department_id', 'workgroup_id', 'group_id')
    def _onchange_scope_unit(self):
        if self.department_id or self.workgroup_id or self.group_id:
            self.is_centre = False

    @api.model
    def default_get(self, fields_list):
        """An agreement added from a department's minute comes with its chiefs as responsible."""
        defaults = super().default_get(fields_list)
        if ('responsible_employee_ids' in fields_list and not defaults.get('responsible_employee_ids')
                and defaults.get('type', 'agreement') == 'agreement' and defaults.get('department_id')):
            chiefs = self._ems_department_chiefs(self.env['hr.department'].browse(defaults['department_id']))
            if chiefs:
                defaults['responsible_employee_ids'] = [(6, 0, chiefs.ids)]
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # An agreement taken in a minute belongs to that minute's scope and course. Taken from
            # the minute itself, not from the form's defaults: the web client only sends back the
            # fields the agreement's card shows, and the scope is not one of them.
            minute = self.env['ems.minute'].browse(vals.get('minute_id'))
            if minute and not any(vals.get(name) for name in ('department_id', 'workgroup_id', 'group_id', 'is_centre')):
                vals.update({
                    'department_id': minute.department_id.id, 'workgroup_id': minute.workgroup_id.id,
                    'group_id': minute.group_id.id, 'is_centre': minute.is_centre, 'course_id': minute.course_id.id,
                })
            # Same default for an agreement created by code (an import, the minute's own lines):
            # only when nobody was named, neither a post nor a person.
            if (vals.get('type', 'agreement') == 'agreement' and vals.get('department_id')
                    and 'responsible_employee_ids' not in vals and not vals.get('responsible_role_id')):
                chiefs = self._ems_department_chiefs(self.env['hr.department'].browse(vals['department_id']))
                if chiefs:
                    vals['responsible_employee_ids'] = [(6, 0, chiefs.ids)]
            if not vals.get('code'):
                vals['code'] = self.new(vals)._next_code()
        actions = super().create(vals_list)
        actions._ems_subscribe_people()
        return actions

    def write(self, vals):
        if not self.env.su and set(vals) - PROGRESS_FIELDS and self - self._ems_content_managed():
            raise AccessError(_("Only whoever manages this agreement may change what was agreed: its responsible people "
                                "edit its description and report its progress in the follow-up."))
        result = super().write(vals)
        if {'responsible_employee_ids', 'involved_employee_ids'} & set(vals):
            self._ems_subscribe_people()
        return result

    def _ems_content_managed(self):
        """The agreements in self whose content the current user may change. The responsible people
        get write access through a rule of their own (rule_quality_action_progress_write), for the
        description only; the content goes by rule_quality_action_teacher_write, evaluated here
        rather than repeated, and by the groups that oversee them all."""
        user = self.env.user
        if self.env.su or not self:
            return self
        content_rule = self.env.ref('ems.rule_quality_action_teacher_write').sudo()
        oversight = self.env.ref('ems.rule_quality_action_oversight').sudo().groups
        if user.groups_id & oversight or not user.groups_id & content_rule.groups:
            # Overseers manage them all; a user in none of the rules' groups is not narrowed by them.
            return self
        domain = safe_eval(content_rule.domain_force, content_rule._eval_context())
        # Only saved agreements: one being created is checked by the create rule itself.
        saved = self.filtered('id')
        return self.sudo().search([('id', 'in', saved.ids)] + domain).with_env(self.env)

    def _ems_subscribe_people(self):
        """The responsible people and the people involved follow the agreement, so its progress
        reaches them. With sudo: subscribing somebody else is not what the record rules decide."""
        for action in self.sudo():
            partners = (action.responsible_employee_ids | action.involved_employee_ids).user_id.partner_id
            if partners:
                action.message_subscribe(partner_ids=partners.ids)

    def action_add_followup(self):
        """A follow-up entry in a dialog: the responsible people report progress from here, on an
        agreement whose content they may only read."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Add follow-up"),
            'res_model': 'ems.quality.followup',
            'view_mode': 'form',
            'views': [(self.env.ref('ems.view_quality_followup_form').id, 'form')],
            'target': 'new',
            'context': {'default_action_id': self.id},
        }

    def _latest_followup(self):
        """The most recent follow-up entry, by date and then by creation order.

        Two entries can share a date (a meeting that reviews several agreements at once), so id
        breaks the tie rather than leaving the state dependent on insertion order."""
        self.ensure_one()
        return self.followup_ids.sorted(key=lambda line: (line.date or fields.Date.today(), line.id))[-1:]

    def _scope_label(self):
        """Short label of the scope this action belongs to, used in codes and lists."""
        self.ensure_one()
        if self.department_id:
            return self.department_id.name
        if self.workgroup_id:
            return self.workgroup_id.name
        if self.group_id:
            return self.group_id.name
        return "Centre" if self.is_centre else ""

    def _scope_code(self):
        """The scope's short code, for the sequence prefix (see common.scope_code)."""
        self.ensure_one()
        if self.group_id:
            return self.group_id.name.upper().replace(' ', '')
        record = self.department_id or self.workgroup_id
        return (scope_code(record) if record else "") or "CEN"

    def _next_code(self):
        """One sequence per (scope, action type family, course), created on demand.

        An ir.sequence rather than a computed max+1: two people approving records at the same
        time must not get the same number, and only the sequence guarantees that."""
        self.ensure_one()
        course = self.course_id or self.env['ems.course'].search([('is_current', '=', True)], limit=1)
        scope_code = self._scope_code() or "CEN"
        short_code = course.short_code or (course.name or '').replace(' ', '')
        prefix = f"ACORD-{scope_code}-{short_code}-"
        sequence_code = f"ems.quality.action.{scope_code}.{short_code}"
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', sequence_code)], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f"Quality actions {scope_code} {short_code}",
                'code': sequence_code,
                'prefix': prefix,
                'padding': 3,
                'implementation': 'no_gap',
            })
        return sequence.next_by_id()

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for action in self:
            action.display_name = f"{action.code} {action.name}" if action.code else action.name
