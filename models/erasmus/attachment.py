# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

# What makes a file another file, or someone else's: its content and the record it belongs to.
CONTENT_FIELDS = {'datas', 'raw', 'db_datas', 'store_fname', 'url', 'type', 'res_model', 'res_id', 'res_field'}


class IrAttachment(models.Model):
    """Audit 2026-10-25 (R-01): the file of a valid document, of a closed mobility or the receipt of a
    paid transfer is evidence. The line already refuses to drop it (EmsErasmusApplicationDocument.write),
    but the file itself could be deleted, overwritten or moved to another record directly."""
    _inherit = 'ir.attachment'

    def write(self, vals):
        if CONTENT_FIELDS & set(vals):
            self._ems_erasmus_check_kept()
        return super().write(vals)

    def unlink(self):
        self._ems_erasmus_check_kept()
        return super().unlink()

    def _ems_erasmus_check_kept(self):
        if not self or self.env.context.get(MODULE_UNINSTALL_FLAG):
            return
        kept = self.env['ems.erasmus.application.document'].sudo().search([
            '|', ('attachment_ids', 'in', self.ids), ('prepared_attachment_ids', 'in', self.ids),
        ])._ems_kept_attachments()
        for model in ('ems.erasmus.payment', 'ems.erasmus.invoice'):
            kept |= self.env[model].sudo().with_context(active_test=False).search([
                ('receipt_ids', 'in', self.ids), ('state', '=', 'paid')]).receipt_ids
        if kept := self.filtered(lambda attachment: attachment.id in kept.ids):
            raise UserError(_("These files are kept as evidence of an Erasmus+ record and cannot be changed, moved or "
                              "deleted (upload a new version instead): %s", ", ".join(kept.sudo().mapped('name'))))
