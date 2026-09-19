# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityProcedure(models.Model):
    _name = "ems.quality.procedure"
    _description = "Quality procedure: how one part of a process is carried out (PE3.01, PE3.04...)."
    _inherit = ['mail.thread']
    _order = "code"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another procedure already uses this code."),
    ]

    code = fields.Char(string="Code", required=True, tracking=True, help="As in the centre's documentation: PE3.01, PC1.02...")
    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    process_id = fields.Many2one(string="Process", comodel_name="ems.quality.process", required=True, ondelete='restrict', tracking=True)
    # The three opening blocks of the centre's own procedure sheet, kept as they are written
    # there so the two can be compared side by side during an audit.
    what = fields.Text(string="What", translate=True)
    what_for = fields.Text(string="What for", translate=True)
    for_whom = fields.Text(string="Who it applies to", translate=True)
    responsible_role_id = fields.Many2one(string="Responsible post", comodel_name="ems.role", tracking=True, help="Who drafts and maintains it.")
    phase_ids = fields.One2many(string="Phases", comodel_name="ems.quality.procedure.phase", inverse_name="procedure_id")
    document_ids = fields.One2many(string="Documents and records", comodel_name="ems.quality.document", inverse_name="procedure_id")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for procedure in self:
            procedure.display_name = f"{procedure.code}: {procedure.name}" if procedure.code else procedure.name


class EmsQualityProcedurePhase(models.Model):
    _name = "ems.quality.procedure.phase"
    _description = "Quality procedure phase: one step of a procedure, with the tools it uses."
    _order = "procedure_id, sequence, id"

    procedure_id = fields.Many2one(string="Procedure", comodel_name="ems.quality.procedure", required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Phase", required=True, translate=True)
    tools = fields.Char(string="Tools", translate=True, help="What the phase is carried out with, as the procedure sheet states it.")
