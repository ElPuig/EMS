# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityDocument(models.Model):
    _name = "ems.quality.document"
    _description = "Controlled document: where it sits in the documentary structure and its link in Drive."
    _order = "code, name"
    _sql_constraints = [
        # Nullable on purpose: some documents of the centre have no code yet. Postgres treats
        # NULLs as distinct, so several uncoded documents coexist without tripping the constraint.
        ('unique_code', 'unique (code)', "Another document already uses this code."),
    ]

    # Deliberately no version, state or dates: the document itself, in Drive, is the only place
    # those are kept, so nobody has to update them twice.
    code = fields.Char(string="Code", help="As in the centre's documentation: PE3.01.15. Empty while the document has no code.")
    name = fields.Char(string="Name", required=True, translate=True)
    procedure_id = fields.Many2one(string="Procedure", comodel_name="ems.quality.procedure", ondelete='set null')
    process_id = fields.Many2one(
        string="Process",
        comodel_name="ems.quality.process",
        compute="_compute_process_id",
        store=True,
        readonly=False,
        ondelete='set null',
        help="Taken from the procedure when there is one, and editable for documents that hang straight off a process.",
    )
    # Not a data/custom/ CSV column on purpose: the links point into the centre's Drive, which
    # this public repository does not publish. Filled in from the app, or loaded in one go with
    # the code,url wizard.
    url = fields.Char(string="Link", help="Where the document lives, normally in the centre's Drive.")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('procedure_id')
    def _compute_process_id(self):
        for document in self:
            if document.procedure_id:
                document.process_id = document.procedure_id.process_id

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for document in self:
            document.display_name = f"{document.code}: {document.name}" if document.code else document.name
