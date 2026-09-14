from odoo import api, models


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    @api.model
    def _update_values(self, src_partners, dst_partner):
        """Hand the Student ID (IDALU) over to the destination contact (issue #460).

        Merging is how a duplicated student gets fixed: a returning former student registered
        again as a brand-new contact. The IDALU is unique (res.partner student_id_unique), but
        the base wizard copies the source's IDALU onto the destination while the source still
        holds it, which the database refuses. The sources are deleted right after this step,
        so their IDALU is released first (plain SQL: removing an IDALU through the ORM is
        refused on purpose) and then written onto the destination if it has none of its own.
        """
        student_id = dst_partner.student_id or next(
            (partner.student_id for partner in src_partners if partner.student_id), False)
        holders = src_partners.filtered('student_id')
        if holders:
            self.env.cr.execute(
                "UPDATE res_partner SET student_id = NULL WHERE id IN %s", [tuple(holders.ids)])
            holders.invalidate_recordset(['student_id'])
        super()._update_values(src_partners, dst_partner)
        if student_id and not dst_partner.student_id:
            dst_partner.write({'student_id': student_id})
