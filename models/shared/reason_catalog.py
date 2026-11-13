# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsReasonCatalog(models.AbstractModel):
    """The shape every catalog of reasons shares (the convalidation refusal and documentation
    request reasons, the strike, justification, student walkout rejection and detected absence
    discard reasons): a translated name, a sequence and an active flag, archived rather than
    deleted. Each model inherits it and keeps its own list: reasons are never shared between
    models, only the code is. A catalog that needs more adds its own fields (e.g. requires_details)."""
    _name = 'ems.reason.catalog'
    _description = "Catalog of reasons"
    _order = 'sequence, name'

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    @api.model
    def default_reason(self):
        """The first active reason by its own order: the most usual one, which the dialogs that
        pick a reason offer by default."""
        return self.search([], limit=1)
