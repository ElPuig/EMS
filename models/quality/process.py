# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityProcess(models.Model):
    _name = "ems.quality.process"
    _description = "Quality process: one process of the centre's process map (PE1..PS2)."
    _order = "sequence, code"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another process already uses this code."),
    ]

    # Only the documentary structure lives here. Everything else about a process (owner,
    # purpose, review dates) is written in its own sheet in Drive, reached through the links.
    code = fields.Char(string="Code", required=True, help="As in the centre's process map: PE1, PC2, PS1...")
    name = fields.Char(string="Name", required=True, translate=True)
    kind = fields.Selection(
        string="Kind",
        selection=[('strategic', "Strategic"), ('key', "Key"), ('support', "Support")],
        required=True,
        default='key',
    )
    procedure_ids = fields.One2many(string="Procedures", comodel_name="ems.quality.procedure", inverse_name="process_id")
    procedure_count = fields.Integer(string="Number of procedures", compute="_compute_procedure_count")
    document_ids = fields.One2many(string="Documents", comodel_name="ems.quality.document", inverse_name="process_id")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    @api.depends('procedure_ids')
    def _compute_procedure_count(self):
        for process in self:
            process.procedure_count = len(process.procedure_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for process in self:
            process.display_name = f"{process.code} {process.name}" if process.code else process.name

    @api.model
    def get_process_map_url(self):
        """The embeddable address of the process map, for the 'Process map' screen.

        Read through the model rather than straight from the company so the screen only needs the
        access every quality role already has on the processes."""
        self.check_access('read')
        return self.env.company.sudo().quality_process_map_url or False
