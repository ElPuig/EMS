import logging

_logger = logging.getLogger(__name__)

# (model, many2many relation table, its column pointing at the model)
ATTACHMENT_RELATIONS = [
    ('ems.attendance_justification', 'ems_attendance_justification_ir_attachment_rel', 'ems_attendance_justification_id'),
    ('ems.study', 'ems_study_ir_attachment_rel', 'ems_study_id'),
]


def _link_attachments(cr):
    """Issue #553: the files attached to an attendance justification or a study were stored
    without a res_id, so Odoo only let their uploader (or a system admin) read them. Ties each
    one to its record, the same way both models' create()/write() now do; a file shared by
    several records goes to the first one."""
    for model, relation, column in ATTACHMENT_RELATIONS:
        cr.execute(f"""
            UPDATE ir_attachment attachment
               SET res_model = %s, res_id = rel.record_id
              FROM (SELECT ir_attachment_id, MIN({column}) AS record_id
                      FROM {relation}
                  GROUP BY ir_attachment_id) rel
             WHERE rel.ir_attachment_id = attachment.id
               AND COALESCE(attachment.res_id, 0) = 0
        """, [model])
        _logger.info("%s attachments linked to their record: %d.", model, cr.rowcount)


def migrate(cr, version):
    _link_attachments(cr)
