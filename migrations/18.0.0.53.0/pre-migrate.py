# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Space types some installations created by hand before they became part of the catalogue
# (data/main/ems.space_type.csv): xmlid name -> English name.
CATALOGUE_TYPES = {'space_type_warehouse': 'Warehouse', 'space_type_wc': 'WC'}


def migrate(cr, version):
    _name_catalogue_space_types(cr)


def _name_catalogue_space_types(cr):
    """Issue #475: 'WC' and 'Warehouse' join the catalogue (so they translate, and a WC is not
    reservable). An installation that already has them made by hand gives them their xmlid here,
    before the data loads, or the catalogue would add a second 'WC' next to the old one. Raw SQL
    on columns that already exist, hence pre-migrate."""
    for xmlid, name in CATALOGUE_TYPES.items():
        cr.execute("SELECT 1 FROM ir_model_data WHERE module = 'ems' AND name = %s", (xmlid,))
        if cr.fetchone():
            continue
        cr.execute("SELECT id FROM ems_space_type WHERE name->>'en_US' = %s ORDER BY id LIMIT 1", (name,))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            "INSERT INTO ir_model_data (module, name, model, res_id, noupdate) VALUES ('ems', %s, 'ems.space_type', %s, FALSE)",
            (xmlid, row[0]))
        _logger.info("Space type %s is now the catalogue's %s.", name, xmlid)
