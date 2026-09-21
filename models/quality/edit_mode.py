# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsQualityEditMode(models.AbstractModel):
    """Read-only by default: a form of the quality structure opens as a record to consult, and its
    fields only become editable after pressing 'Edit' in the header, even for users who may write.

    'edit_mode' is never stored: it starts False on every load, so saving or leaving the record
    always brings the form back to read-only. The views mark every field readonly="not edit_mode"."""

    _name = "ems.quality.edit.mode"
    _description = "Quality edit mode: forms that open read-only until 'Edit' is pressed."

    edit_mode = fields.Boolean(string="Editing", compute="_compute_edit_mode", readonly=False, store=False)
    can_edit = fields.Boolean(string="Can edit", compute="_compute_can_edit", help="Whether the current user may write this record.")

    def _compute_edit_mode(self):
        for record in self:
            # A record being created is already in edit mode: there is nothing to consult yet.
            record.edit_mode = not record.id

    @api.depends_context('uid')
    def _compute_can_edit(self):
        for record in self:
            record.can_edit = record.has_access('write') if record.id else self.has_access('create')
