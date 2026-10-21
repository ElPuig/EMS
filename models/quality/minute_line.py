# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


class EmsMinuteAgenda(models.Model):
    _name = "ems.minute.agenda"
    _description = "Agenda item of a minute."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Item", required=True)
    notes = fields.Html(string="What was said", help="What the meeting actually discussed on this item.")


class EmsMinuteSectionValue(models.Model):
    _name = "ems.minute.section.value"
    _description = "Section of a minute, with whatever was written in it."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    section_id = fields.Many2one(string="Section", comodel_name="ems.minute.section", required=True, ondelete='restrict')
    sequence = fields.Integer(string="Sequence", default=10)
    kind = fields.Selection(string="Kind", related="section_id.kind", store=True)
    name = fields.Char(string="Name", related="section_id.name")
    content = fields.Html(string="Content")
    required = fields.Boolean(string="Required", compute="_compute_required", store=True)
    is_written = fields.Boolean(
        string="Written during the meeting",
        compute="_compute_is_written",
        help="The section is a text of its own, written in the meeting. The development of the session is, "
             "unless the minute has items to discuss: then it is put together from what was said on each.",
    )

    @api.depends('kind', 'minute_id.type_id')
    def _compute_is_written(self):
        for value in self:
            has_items = 'agenda' in value.minute_id.type_id.section_ids.mapped('section_id.kind')
            value.is_written = value.kind == 'text' or (value.kind == 'development' and not has_items)

    @api.depends('minute_id.type_id', 'section_id')
    def _compute_required(self):
        for value in self:
            line = value.minute_id.type_id.section_ids.filtered(lambda item: item.section_id == value.section_id)[:1]
            value.required = bool(line.required)


class EmsMinuteGuest(models.Model):
    """Somebody from outside EMS at the meeting (a student's family, a teacher from another school,
    a speaker): no employee record, so the minute keeps their name, surname and email itself."""

    _name = "ems.minute.guest"
    _description = "Person from outside EMS at a meeting."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="First name", required=True)
    surname = fields.Char(string="Surname", required=True)
    email = fields.Char(string="Email")
    organisation = fields.Char(string="Organisation or relationship", help="Who they are for the meeting: a student's mother, another school, a company...")
    attended = fields.Boolean(string="Present", default=True, help="Untick it for somebody who was invited but did not come.")
    send_call = fields.Boolean(
        string="Send them the call",
        help="They get the call by email, in a message of their own: never together with the staff's, so nobody "
             "sees anybody else's address.")

    @api.depends('name', 'surname', 'organisation')
    def _compute_display_name(self):
        for guest in self:
            full_name = f"{guest.name or ''} {guest.surname or ''}".strip()
            guest.display_name = f"{full_name} ({guest.organisation})" if guest.organisation else full_name

    @api.constrains('email')
    def _check_email(self):
        for guest in self:
            if guest.email and not email_normalize(guest.email):
                raise ValidationError(_("%(email)s is not a valid email address.", email=guest.email))

    @api.constrains('send_call', 'email')
    def _check_send_call_email(self):
        for guest in self:
            if guest.send_call and not guest.email:
                raise ValidationError(_("%(name)s has no email to send the call to.", name=guest.display_name))


class EmsMinutePendingTopic(models.Model):
    _name = "ems.minute.pending.topic"
    _description = "Pending topic of a minute, carried over until somebody deals with it."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Topic", required=True)
    is_done = fields.Boolean(string="Dealt with", help="Unticked topics are carried into the next minute of the same scope.")
    carried_from_minute_id = fields.Many2one(string="Carried from", comodel_name="ems.minute", ondelete='set null', readonly=True)


class EmsMinuteAgreementReview(models.Model):
    """One agreement still open, as this meeting reviews it. What is written here becomes an
    entry in the agreement's own follow-up, so its history stays in one place and the next
    meeting finds it up to date."""

    _name = "ems.minute.agreement.review"
    _description = "Review of an open agreement in a minute: what was said, a new deadline, whether it is closed."
    _order = "minute_id, action_id"
    _sql_constraints = [
        ('unique_action', 'unique (minute_id, action_id)', "This agreement is already reviewed in this minute."),
    ]

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    action_id = fields.Many2one(string="Agreement", comodel_name="ems.quality.action", required=True, ondelete='cascade')
    code = fields.Char(string="Code", related="action_id.code")
    name = fields.Char(string="What was agreed", related="action_id.name")
    responsible_employee_ids = fields.Many2many(string="Responsible people", related="action_id.responsible_employee_ids")
    deadline_date = fields.Date(string="Deadline", related="action_id.deadline_date")
    new_deadline_date = fields.Date(string="New deadline", help="Set it to move the agreement's deadline.")
    note = fields.Text(string="Follow-up", help="What the meeting said about the agreement. It is added to the agreement's own follow-up.")
    is_closed = fields.Boolean(string="Done", help="The meeting considers the agreement done.")
    followup_id = fields.Many2one(string="Follow-up entry", comodel_name="ems.quality.followup", ondelete='set null', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        reviews = super().create(vals_list)
        reviews._ems_push_to_agreement()
        return reviews

    def write(self, vals):
        result = super().write(vals)
        if {'note', 'is_closed', 'new_deadline_date'} & set(vals):
            self._ems_push_to_agreement()
        return result

    def _ems_push_to_agreement(self):
        """Carry the review over to the agreement: one follow-up entry per minute, kept in step
        with what the minute says, and the new deadline when one was set. With sudo: whoever
        writes the minute reviews the agreements it follows, whoever they belong to."""
        for review in self.sudo():
            if review.new_deadline_date and review.new_deadline_date != review.action_id.deadline_date:
                review.action_id.deadline_date = review.new_deadline_date
            if not (review.note or review.is_closed):
                review.followup_id.unlink()
                continue
            vals = {
                'action_id': review.action_id.id,
                'date': review.minute_id.date,
                'state': 'closed' if review.is_closed else 'in_progress',
                'description': review.note or _("Reviewed in the meeting %s.", review.minute_id.code or review.minute_id.name),
                'author_employee_id': review.minute_id.redactor_employee_id.id,
            }
            if review.followup_id:
                review.followup_id.write(vals)
            else:
                review.followup_id = self.env['ems.quality.followup'].sudo().create(vals)


class EmsMinuteMemberLine(models.Model):
    _name = "ems.minute.member.line"
    _description = "Member of a team being constituted, with the post held inside it."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    employee_id = fields.Many2one(string="Member", comodel_name="hr.employee.public", required=True)
    team_role = fields.Selection(
        string="Post in the team",
        selection=[('facilitator', "Facilitator"), ('secretary', "Secretary"), ('member', "Member")],
        required=True,
        default='member',
    )
    speciality = fields.Char(string="Teaching speciality")
    identification = fields.Char(
        string="Identification number",
        compute="_compute_identification",
        help="Read from the employee record. Printed only by the minute types that need it, because it is required to claim the innovation credit.",
    )

    @api.depends('employee_id')
    def _compute_identification(self):
        """Read with sudo() on purpose and nowhere else.

        hr.employee.identification_id carries groups="hr.group_hr_user", which neither the teaching
        staff nor the quality coordination nor the secretariat imply: without this, the field would
        render blank or raise for exactly the people who generate the document (the failure class of
        issue #434). Same narrow pattern already used for the Google credentials (#478)."""
        for line in self:
            employee = line.employee_id
            line.identification = employee.sudo().employee_id.identification_id if employee.sudo().employee_id else False


class EmsMinuteObjectiveLine(models.Model):
    _name = "ems.minute.objective.line"
    _description = "Objective and its indicator, as stated when a team is constituted."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Objective", required=True)
    indicator = fields.Text(string="Indicator", help="What is measured, as a single objective fact.")
    acceptance_value = fields.Char(string="Acceptance", help="The minimum value that counts as achieved.")
    target_value = fields.Char(string="Target", help="The value aimed for in future iterations.")
