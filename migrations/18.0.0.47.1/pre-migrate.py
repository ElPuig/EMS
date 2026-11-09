def migrate(cr, version):
    _freeze_quality_committee(cr)


def _freeze_quality_committee(cr):
    """The quality committee workgroup (ems.quality) was re-applied from the catalogue on every
    upgrade, putting back 'Quality Comission' over the name the centre had given it (issue #804).
    Its data file is noupdate now, but that only reaches new installations: an existing record
    keeps the flag it was created with, so set it here. A record still carrying the original name
    gets the Catalan one a new installation starts with."""
    cr.execute("""
        UPDATE ir_model_data SET noupdate = TRUE
         WHERE module = 'ems' AND name = 'quality' AND model = 'ems.workgroup'
     RETURNING res_id
    """)
    row = cr.fetchone()
    if row:
        cr.execute(
            "UPDATE ems_workgroup SET name = 'Comissió de Qualitat' WHERE id = %s AND name = 'Quality Comission'",
            (row[0],),
        )
