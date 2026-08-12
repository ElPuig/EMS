# -*- coding: utf-8 -*-

import re

from odoo import _, models
from odoo.exceptions import ValidationError

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ems_hex_color_mixin(models.AbstractModel):
    _name = 'ems.hex_color_mixin'
    _description = "Shared hex-color format validation for models with a free-pick color swatch (widget='color')."

    def _check_hex_color(self, fname):
        for record in self:
            value = record[fname]
            if value and not HEX_COLOR_RE.match(value):
                raise ValidationError(_("Color must be a hexadecimal code (e.g. #3A8DDE)."))
