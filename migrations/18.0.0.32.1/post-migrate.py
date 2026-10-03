import logging

_logger = logging.getLogger(__name__)


def _link_justification_attachments(cr):
    """Issue #553: the files attached to an attendance justification were stored without a
    res_id, so Odoo only let their uploader (or a system admin) read them. Ties each one to its
    justification, the same way ems.attendance_justification's create()/write() now do."""
    cr.execute("""
        UPDATE ir_attachment attachment
           SET res_model = 'ems.attendance_justification',
               res_id = rel.ems_attendance_justification_id
          FROM ems_attendance_justification_ir_attachment_rel rel
         WHERE rel.ir_attachment_id = attachment.id
           AND COALESCE(attachment.res_id, 0) = 0
    """)
    _logger.info("Attendance justification attachments linked to their justification: %d.", cr.rowcount)


def migrate(cr, version):
    _link_justification_attachments(cr)
