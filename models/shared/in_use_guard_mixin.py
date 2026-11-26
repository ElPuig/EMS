# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError


class EmsInUseGuardMixin(models.AbstractModel):
    """Refuses to delete a record that another record still points at (issue #868, part of #52).

    The catalog models (levels, studies, subjects, plannings, spaces, roles...) are archived, never
    deleted, once they are in use: deleting a subject would cascade to its enrolments and teaching
    assignments, deleting a level would empty the level of every student, group and session. Only
    the administrators keep the delete permission (ir.model.access), and this guard makes sure they
    can only delete a record nobody uses yet, e.g. one created by mistake. Code that runs as
    superuser is checked too: a delete is only safe when nothing refers to the record.

    Odoo has no "in use" check of its own: an ondelete='restrict' foreign key only covers the fields
    declared that way, and most references here are 'set null' or 'cascade', which would silently
    empty or delete the referencing records. So every stored many2one/many2many pointing at the
    model is looked up, archived referencing records included."""
    _name = 'ems.in_use_guard.mixin'
    _description = 'Refuses to delete records still in use'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_in_use(self):
        users = self._ems_referencing_models()
        if users:
            raise UserError(_(
                "%(records)s cannot be deleted because it is in use (%(where)s). Archive it instead.",
                records=", ".join(self.mapped('display_name')), where=", ".join(users)))

    def _ems_referencing_models(self):
        """Names of the models with a record pointing at any of `self`: one query for the
        referencing fields, then one indexed lookup (limit 1) per field, stopping at none."""
        if not self:
            return []
        fields_data = self.env['ir.model.fields'].sudo().search_read([
            ('relation', '=', self._name), ('store', '=', True),
            ('ttype', 'in', ('many2one', 'many2many'))], ['model', 'name'])
        found = {}
        for field_data in fields_data:
            model_name = field_data['model']
            if model_name in found or model_name not in self.env:
                continue
            model = self.env[model_name]
            if model._transient or model._abstract or field_data['name'] not in model._fields:
                continue
            if model.sudo().with_context(active_test=False).search(
                    [(field_data['name'], 'in', self.ids)], limit=1):
                # EMS descriptions read "Name: explanation"; the name is enough here.
                found[model_name] = self.env['ir.model']._get(model_name).name.split(':')[0]
        return sorted(found.values())
