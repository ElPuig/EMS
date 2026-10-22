# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmsQualityDocument(models.Model):
    _name = "ems.quality.document"
    _description = "Controlled document: where it sits in the documentary structure and its link in Drive."
    _inherit = ['ems.quality.edit.mode', 'ems.quality.link']
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
    is_process_map = fields.Boolean(string="Process map", help="The document shown in Quality > Process map. Only one document can be marked.")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('procedure_id')
    def _compute_process_id(self):
        for document in self:
            if document.procedure_id:
                document.process_id = document.procedure_id.process_id

    @api.constrains('is_process_map', 'active')
    def _check_single_process_map(self):
        if self.search_count([('is_process_map', '=', True)]) > 1:
            raise ValidationError(_("Only one document can be marked as the process map."))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for document in self:
            document.display_name = f"{document.code}: {document.name}" if document.code else document.name

    @api.model
    def action_open_process_map(self):
        """Quality > Process map: the form of whichever document is marked as the process map."""
        document = self.search([('is_process_map', '=', True)], limit=1)
        if not document:
            raise UserError(_("No document is marked as the process map yet. Mark one in Quality > Configuration > Documents."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Process map"),
            'res_model': self._name,
            'res_id': document.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
