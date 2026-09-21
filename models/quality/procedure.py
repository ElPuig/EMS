# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityProcedure(models.Model):
    _name = "ems.quality.procedure"
    _description = "Quality procedure: how one part of a process is carried out (PE3.01, PE3.04...)."
    _order = "code"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another procedure already uses this code."),
    ]

    code = fields.Char(string="Code", required=True, help="As in the centre's documentation: PE3.01, PC1.02...")
    name = fields.Char(string="Name", required=True, translate=True)
    process_id = fields.Many2one(string="Process", comodel_name="ems.quality.process", required=True, ondelete='restrict')
    document_ids = fields.One2many(string="Documents", comodel_name="ems.quality.document", inverse_name="procedure_id")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for procedure in self:
            procedure.display_name = f"{procedure.code}: {procedure.name}" if procedure.code else procedure.name
