# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _copy_student_to_student_list(cr)
    move_notes_to_details(cr)
    merge_batch_justifications(cr)
    _set_reason_other(cr)


def _copy_student_to_student_list(cr):
    """Issue #795: a justification covers a list of students (student_ids) instead of one
    (student_id). The old column is still there in post-migrate: Odoo drops it at the end of the
    upgrade."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'ems_attendance_justification' AND column_name = 'student_id'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        INSERT INTO ems_attendance_justification_student_rel (justification_id, student_id)
        SELECT id, student_id FROM ems_attendance_justification WHERE student_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    _logger.info("Migration #795: %d justification(s) moved to the student list.", cr.rowcount)


def move_notes_to_details(cr):
    """Issue #795: every existing justification becomes 'Other reasons' (_set_reason_other), whose
    text is its details: the notes move there, and the notes field stays, empty."""
    cr.execute("""
        UPDATE ems_attendance_justification SET details = notes, notes = NULL
         WHERE COALESCE(notes, '') <> ''
    """)
    _logger.info("Migration #795: %d justification(s) moved their notes to the details.", cr.rowcount)


def merge_batch_justifications(cr):
    """Issue #795: the 'Justify absences' assistant (issues #656, #763) created one justification
    per student, with the same comment and a copy of every file. Each batch becomes one
    justification with all its students.

    A batch is recognized by everything the assistant copied (its notes, in the details by now) plus
    the moment it was created: it created them all in a single create() (same create_uid and
    create_date, the transaction's time), which justifications created one by one never share. The
    oldest one is kept."""
    cr.execute("""
        SELECT MIN(id), ARRAY_AGG(id ORDER BY id)
          FROM ems_attendance_justification
         GROUP BY teacher_id, start_date, end_date, COALESCE(details, ''), create_uid, create_date
        HAVING COUNT(*) > 1
    """)
    batches = cr.fetchall()
    for kept, ids in batches:
        merged = tuple(ids[1:])
        params = {'kept': kept, 'merged': merged}
        cr.execute("""
            INSERT INTO ems_attendance_justification_student_rel (justification_id, student_id)
            SELECT %(kept)s, student_id FROM ems_attendance_justification_student_rel
             WHERE justification_id IN %(merged)s
            ON CONFLICT DO NOTHING
        """, params)
        cr.execute("""
            UPDATE ems_attendance_session_line SET attendance_justification_id = %(kept)s
             WHERE attendance_justification_id IN %(merged)s
        """, params)
        cr.execute("""
            UPDATE ems_attendance_session_line SET attendance_prevision_id = %(kept)s
             WHERE attendance_prevision_id IN %(merged)s
        """, params)
        cr.execute("""
            INSERT INTO ems_attendance_justification_ems_attendance_session_line_rel
                   (ems_attendance_justification_id, ems_attendance_session_line_id)
            SELECT %(kept)s, ems_attendance_session_line_id
              FROM ems_attendance_justification_ems_attendance_session_line_rel
             WHERE ems_attendance_justification_id IN %(merged)s
            ON CONFLICT DO NOTHING
        """, params)
        cr.execute("""
            INSERT INTO ems_attendance_justification_hr_employee_rel
                   (ems_attendance_justification_id, hr_employee_id)
            SELECT %(kept)s, hr_employee_id FROM ems_attendance_justification_hr_employee_rel
             WHERE ems_attendance_justification_id IN %(merged)s
            ON CONFLICT DO NOTHING
        """, params)
        _merge_attachments(cr, kept, merged)
        # Plain SQL, not unlink(): unlink() would take the justification off the session lines.
        cr.execute("DELETE FROM ems_attendance_justification WHERE id IN %(merged)s", params)
    if batches:
        _logger.info("Migration #795: %d batch(es) of justifications merged into one each.", len(batches))


def _set_reason_other(cr):
    """Issue #795: every justification from before the reasons existed becomes 'Other', with its old
    notes as details (move_notes_to_details()). Before Odoo adds the NOT NULL on reason_id (at the
    end of the upgrade). The reasons are loaded by now."""
    cr.execute("""
        SELECT res_id FROM ir_model_data
         WHERE module = 'ems' AND name = 'attendance_justification_reason_other'
    """)
    row = cr.fetchone()
    if not row:
        return
    cr.execute("UPDATE ems_attendance_justification SET reason_id = %s WHERE reason_id IS NULL", row)
    _logger.info("Migration #795: %d justification(s) set to the reason 'Other'.", cr.rowcount)


def _merge_attachments(cr, kept, merged):
    """The copies of the kept justification's files (same name and content) are deleted; any other
    file moves to it. The filestore keeps the content once either way."""
    cr.execute("""
        SELECT a.id, a.name, a.checksum FROM ir_attachment a
          JOIN ems_attendance_justification_ir_attachment_rel r ON r.ir_attachment_id = a.id
         WHERE r.ems_attendance_justification_id IN %s
         ORDER BY a.id
    """, (merged,))
    for attachment_id, name, checksum in cr.fetchall():
        # Checked file by file: a file moved just before counts as the kept one's from then on.
        cr.execute("""
            SELECT 1 FROM ir_attachment k
              JOIN ems_attendance_justification_ir_attachment_rel kr ON kr.ir_attachment_id = k.id
             WHERE kr.ems_attendance_justification_id = %s
               AND k.name = %s AND k.checksum IS NOT DISTINCT FROM %s
        """, (kept, name, checksum))
        if cr.fetchone():
            cr.execute("DELETE FROM ir_attachment WHERE id = %s", (attachment_id,))
            continue
        cr.execute("""
            UPDATE ems_attendance_justification_ir_attachment_rel
               SET ems_attendance_justification_id = %s
             WHERE ir_attachment_id = %s
        """, (kept, attachment_id))
        cr.execute("UPDATE ir_attachment SET res_id = %s WHERE id = %s", (kept, attachment_id))
