# -*- coding: utf-8 -*-

from odoo import api, fields, models


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

    @api.depends('minute_id.type_id', 'section_id')
    def _compute_required(self):
        for value in self:
            line = value.minute_id.type_id.section_ids.filtered(lambda item: item.section_id == value.section_id)[:1]
            value.required = bool(line.required)


class EmsMinutePendingTopic(models.Model):
    _name = "ems.minute.pending.topic"
    _description = "Pending topic of a minute, carried over until somebody deals with it."
    _order = "minute_id, sequence, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Topic", required=True)
    is_done = fields.Boolean(string="Dealt with", help="Unticked topics are carried into the next minute of the same scope.")
    carried_from_minute_id = fields.Many2one(string="Carried from", comodel_name="ems.minute", ondelete='set null', readonly=True)


class EmsMinuteHarmonisationLine(models.Model):
    _name = "ems.minute.harmonisation.line"
    _description = "Harmonisation line: which groups of a subject were harmonised, and by whom."
    _order = "minute_id, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    group_ids = fields.Many2many(string="Groups", comodel_name="ems.group", relation="ems_minute_harmonisation_group_rel", column1="line_id", column2="group_id")
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
    is_harmonised = fields.Boolean(string="Harmonised")
    teacher_ids = fields.Many2many(string="Teachers", comodel_name="hr.employee.public", relation="ems_minute_harmonisation_teacher_rel", column1="line_id", column2="employee_id")
    notes = fields.Char(string="Comments")


class EmsMinuteClilLine(models.Model):
    _name = "ems.minute.clil.line"
    _description = "CLIL line: which subjects worked content in English, and in which group."
    _order = "minute_id, id"

    minute_id = fields.Many2one(string="Minute", comodel_name="ems.minute", required=True, ondelete='cascade')
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
    group_id = fields.Many2one(string="Group", comodel_name="ems.group")
    worked_in_english = fields.Boolean(string="Content worked in English")
    teacher_ids = fields.Many2many(string="Teachers", comodel_name="hr.employee.public", relation="ems_minute_clil_teacher_rel", column1="line_id", column2="employee_id")
    notes = fields.Char(string="Comments")


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
