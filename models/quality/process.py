# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityProcess(models.Model):
    _name = "ems.quality.process"
    _description = "Quality process: one process of the centre's process map (PE1..PS2)."
    _inherit = ['mail.thread']
    _order = "sequence, code"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another process already uses this code."),
    ]

    code = fields.Char(string="Code", required=True, tracking=True, help="As in the centre's process map: PE1, PC2, PS1...")
    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    kind = fields.Selection(
        string="Kind",
        selection=[('strategic', "Strategic"), ('key', "Key"), ('support', "Support")],
        required=True,
        default='key',
        tracking=True,
    )
    # Responsibility is a post, not a person: the centre's own records name "Director",
    # "Secretary" or "Quality coordinator", and that survives someone changing job in September.
    responsible_role_id = fields.Many2one(string="Responsible post", comodel_name="ems.role", tracking=True)
    responsible_employee_ids = fields.Many2many(
        string="Currently held by",
        comodel_name="hr.employee.public",
        compute="_compute_responsible_employee_ids",
        help="The employees holding the responsible post right now. Not stored: it follows the post.",
    )
    is_quality_process = fields.Boolean(string="Quality process", tracking=True, help="Answers the management review's question about which processes are quality processes.")
    swot_review_date = fields.Date(string="SWOT last reviewed", tracking=True)
    procedure_ids = fields.One2many(string="Procedures", comodel_name="ems.quality.procedure", inverse_name="process_id")
    procedure_count = fields.Integer(string="Number of procedures", compute="_compute_procedure_count")
    document_ids = fields.One2many(string="Documents", comodel_name="ems.quality.document", inverse_name="process_id")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    @api.depends('responsible_role_id', 'responsible_role_id.employee_ids')
    def _compute_responsible_employee_ids(self):
        for process in self:
            process.responsible_employee_ids = process.responsible_role_id.employee_ids

    @api.depends('procedure_ids')
    def _compute_procedure_count(self):
        for process in self:
            process.procedure_count = len(process.procedure_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for process in self:
            process.display_name = f"{process.code} {process.name}" if process.code else process.name
