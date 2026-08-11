# -*- coding: utf-8 -*-
import csv
import glob
import logging
import os

_logger = logging.getLogger(__name__)

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

DEFAULT_COLOR = "#3A8DDE"

# Odoo's own fixed color_picker palette (web/static/src/scss/secondary_variables.scss
# $o-colors), index 0-11 - used to remap ems_attendance_template's pre-existing integer
# values (which came from that same palette, via the kanban_color_picker/color_picker
# widgets) to their closest hex equivalent, so distinct existing rows stay distinct
# instead of all collapsing to one flat default color.
ODOO_PALETTE = [
    '#A2A2A2', '#EE2D2D', '#DC8534', '#E8BB1D', '#5794DD', '#9F628F',
    '#DB8865', '#41A9A2', '#304BE0', '#EE2F8A', '#61C36E', '#9872E6',
]


def _column_is_integer(cr, table, column):
    cr.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    row = cr.fetchone()
    return bool(row) and row[0] == 'integer'


def _migrate_role_color(cr):
    # ems.role.color moves from a fixed-palette Integer index to a free-pick hex Char.
    # Any existing value is not a valid hex code, so it can't carry meaning across the
    # type change - reset every row to a neutral default here; data/cat/ems.role.csv
    # (noupdate=False) reloads right after and gives the built-in roles their real,
    # distinct colors back. Centre-defined custom roles simply keep the default until
    # an admin repicks them with the new color widget.
    if not _column_is_integer(cr, 'ems_role', 'color'):
        return

    cr.execute(
        "ALTER TABLE ems_role ALTER COLUMN color TYPE varchar USING %s",
        (DEFAULT_COLOR,),
    )
    _logger.info("Migration 18.0.0.22.0: converted ems_role.color from integer to hex varchar.")


def _migrate_attendance_template_color(cr):
    # ems.attendance_template.color moves the same way, but these rows are live,
    # permanently-created user data (no fixture file reloads them afterwards, unlike
    # ems.role) - remap each existing integer through Odoo's own former palette (mod 12,
    # matching how the color_picker/kanban widgets already interpreted it) instead of
    # collapsing every row to one flat color.
    if not _column_is_integer(cr, 'ems_attendance_template', 'color'):
        return

    case_sql = " ".join(
        f"WHEN {index} THEN '{hex_color}'" for index, hex_color in enumerate(ODOO_PALETTE)
    )
    cr.execute(f"""
        ALTER TABLE ems_attendance_template ALTER COLUMN color TYPE varchar
        USING (CASE COALESCE(color, 0) % {len(ODOO_PALETTE)} {case_sql} END)
    """)
    _logger.info("Migration 18.0.0.22.0: converted ems_attendance_template.color from integer to hex varchar.")


def _rename_old_status_columns(cr):
    """ems_attendance_session_line.status / ems_attendance_issue_status.attendance_status
    (both Selection) become Many2one status_id/attendance_status_id in this version - see
    docs/en/developers/attendance/attendance_status.md. The post-migrate backfill needs to
    read the old string values, but confirmed empirically on a dev box: as soon as this
    module's schema sync runs (right after pre-migrate), Odoo's own ir.model.fields
    cleanup for the now-removed field drops the physical column outright - there is no
    window where the old column and the new one coexist unless the old one is moved out
    of the way first. Renaming here (before schema sync ever runs) sidesteps that: Odoo's
    cleanup only knows to drop a column literally named "status"/"attendance_status" (via
    the stale ir.model.fields record for that exact name), so the renamed copies are never
    a target and survive through to post-migrate, which reads them and drops them itself
    once the backfill is done.
    """
    if _column_exists(cr, 'ems_attendance_session_line', 'status'):
        cr.execute("ALTER TABLE ems_attendance_session_line RENAME COLUMN status TO status_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_attendance_session_line.status as status_old for the post-migrate backfill.")

    if _column_exists(cr, 'ems_attendance_issue_status', 'attendance_status'):
        cr.execute("ALTER TABLE ems_attendance_issue_status RENAME COLUMN attendance_status TO attendance_status_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_attendance_issue_status.attendance_status as attendance_status_old for the post-migrate backfill.")


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _rename_old_special_columns(cr):
    """ems_limesurvey_block.special_wpi_enrolled/special_subject_enrolled (both Boolean)
    become a single special_type Selection in this version - see
    plans/limesurvey_block_special_mutual_exclusion_asymmetry.md (now resolved). Same
    rename-before-schema-sync gotcha as _rename_old_status_columns above: renaming here
    (before the fields are removed from the model) keeps the old values reachable for the
    post-migrate backfill, since Odoo's own field-removal cleanup would otherwise drop the
    columns outright.
    """
    if _column_exists(cr, 'ems_limesurvey_block', 'special_wpi_enrolled'):
        cr.execute("ALTER TABLE ems_limesurvey_block RENAME COLUMN special_wpi_enrolled TO special_wpi_enrolled_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_limesurvey_block.special_wpi_enrolled as special_wpi_enrolled_old for the post-migrate backfill.")

    if _column_exists(cr, 'ems_limesurvey_block', 'special_subject_enrolled'):
        cr.execute("ALTER TABLE ems_limesurvey_block RENAME COLUMN special_subject_enrolled TO special_subject_enrolled_old")
        _logger.info("Migration 18.0.0.22.0: preserved ems_limesurvey_block.special_subject_enrolled as special_subject_enrolled_old for the post-migrate backfill.")


def _dedupe_ems_enrollment(cr):
    """ems.enrollment gets a new UNIQUE(student_id, group_id, subject_id) constraint in
    this version (see plans/enrollment_junction_duplicate_constraint.md) - the schema sync
    right after pre-migrate would fail to create it while duplicate rows still exist. All
    42 duplicate rows found in production (21 triples) were confirmed field-identical
    within their pair (only id/timestamps differ), so keeping the lowest id per triple and
    dropping the rest loses no information. Deleted directly via SQL, not ORM unlink() -
    unlink()'s _ems_sync_grade_session_remove has no still-enrolled guard (unlike its
    sibling _ems_sync_attendance_template_remove - see
    plans/grade_session_remove_missing_still_enrolled_guard.md), so going through the ORM
    here would risk wiping the surviving student's grade lines for an open session.
    """
    cr.execute("""
        DELETE FROM ems_enrollment a
        USING ems_enrollment b
        WHERE a.student_id = b.student_id
          AND a.group_id = b.group_id
          AND a.subject_id = b.subject_id
          AND a.id > b.id
    """)
    if cr.rowcount:
        _logger.info(
            "Migration 18.0.0.22.0: removed %d duplicate ems_enrollment row(s) "
            "(student_id, group_id, subject_id) ahead of the new unique constraint.",
            cr.rowcount)


# (model, name) pairs whose data/custom/ record gained the __import__. prefix in this
# version by converting from XML to CSV (see CLAUDE.md's "Data folder conventions" - the
# ems.planning, ems.authorization.template, ems.course and ir.sequence files that were the
# last data/custom/ holdouts still declared via XML <record> tags). These xmlids already
# exist in production under module='ems' - repoint their ownership to '__import__' in
# place, same as 18.0.0.19.1 did for ems.group/crm.team (no res_id changes).
FLAT_RENAMED_XMLIDS = [
    ('ems.course', 'ems_course_25_26'),
    ('ems.course', 'ems_course_26_27'),
    ('ems.course', 'ems_course_27_28'),
    ('ems.course', 'ems_course_28_29'),
    ('ir.sequence', 'seq_ems_enrollment_number'),
    ('ems.authorization.template', 'auth_template_image_and_sound'),
    ('ems.authorization.template', 'auth_template_carta_compromis'),
    ('ems.authorization.template', 'auth_template_data_protection'),
    ('ems.authorization.template', 'auth_template_excursions'),
    ('ems.authorization.template', 'auth_template_comunicacio_families'),
]


def _read_custom_csv(filename):
    path = os.path.join(MODULE_ROOT, 'data', 'custom', 'ccff', filename)
    with open(path, encoding='utf-8', newline='') as csv_file:
        return list(csv.DictReader(csv_file))


def _split_xmlid(xmlid):
    module, _, name = xmlid.rpartition('.')
    return module or 'ems', name


def _rename_data_custom_xmlid_ownership(cr):
    """Also clears the stored ir_model_data.noupdate flag, not just the module - confirmed
    empirically (2026-07-30, changing ir.sequence-enrollment_number.csv's padding and running
    a plain ./upgrade.sh) that odoo/models.py::_load_records decides whether to update an
    EXISTING record by checking `d_noupdate` read from the ir_model_data row itself
    (`if not (update and d_noupdate): to_update.append(data)`), not the noupdate context the
    calling file's load() was invoked with. These xmlids were all originally created under the
    old <data noupdate="1"> XML files, so their stored flag is True; renaming only the module
    (as 18.0.0.19.1 did for ems.group/crm.team, which were always noupdate=False CSV and never
    had this problem) would silently leave every one of these records frozen forever, exactly
    the noupdate=1 XML behavior data/custom/ is deliberately moving away from (see CLAUDE.md's
    Data folder conventions) - the new CSV files would load without error but never actually
    resync a changed value into an already-existing row.
    """
    renamed = list(FLAT_RENAMED_XMLIDS)
    for path in sorted(glob.glob(os.path.join(MODULE_ROOT, 'data', 'custom', 'ccff', 'ems.planning-*.csv'))):
        for row in csv.DictReader(open(path, encoding='utf-8', newline='')):
            renamed.append(('ems.planning', _split_xmlid(row['id'])[1]))

    for model, name in renamed:
        cr.execute(
            "UPDATE ir_model_data SET module = '__import__', noupdate = FALSE "
            "WHERE module = 'ems' AND model = %s AND name = %s",
            (model, name),
        )
        if cr.rowcount:
            _logger.info(
                "Migration 18.0.0.22.0: rescoped xml_id 'ems.%s' (%s) -> '__import__.%s' "
                "and cleared its noupdate flag.",
                name, model, name,
            )


def _resolve_xmlid(cr, xmlid):
    module, name = _split_xmlid(xmlid)
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
        (module, name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _reconcile_planning_outcome_xmlids(cr):
    """ems.planning_outcome children were created inline (eval="[(0, 0, {...})]") in the old
    XML, so production has live rows with no xml_id of their own at all - only their parent
    ems.planning row had one. The new data/custom/ccff/ems.planning_outcome.*.csv files mint
    a real per-child __import__. id for each one, matched here to its existing live row by
    (planning_id, outcome_id) - the same reconcile-before-reload approach 18.0.0.19.1 used for
    orphaned ems.planning xml_ids. Must run after _rename_data_custom_xmlid_ownership (needs
    the ems.planning ids already resolvable) so this file's migrate() calls it second.
    """
    for path in sorted(glob.glob(os.path.join(MODULE_ROOT, 'data', 'custom', 'ccff', 'ems.planning_outcome-*.csv'))):
        for row in csv.DictReader(open(path, encoding='utf-8', newline='')):
            new_module, new_name = _split_xmlid(row['id'])
            planning_id = _resolve_xmlid(cr, row['planning_id/id'])
            outcome_id = _resolve_xmlid(cr, row['outcome_id/id'])
            if planning_id is None or outcome_id is None:
                _logger.warning(
                    "Migration 18.0.0.22.0: could not resolve planning_id/outcome_id for "
                    "'%s' (planning=%s, outcome=%s); skipping.",
                    row['id'], row['planning_id/id'], row['outcome_id/id'],
                )
                continue

            cr.execute(
                "SELECT id FROM ems_planning_outcome WHERE planning_id = %s AND outcome_id = %s",
                (planning_id, outcome_id),
            )
            candidates = cr.fetchall()
            if len(candidates) != 1:
                if candidates:
                    _logger.warning(
                        "Migration 18.0.0.22.0: %d ems_planning_outcome candidates found for "
                        "'%s' (planning_id=%s, outcome_id=%s); skipping, needs manual review.",
                        len(candidates), row['id'], planning_id, outcome_id,
                    )
                continue

            live_id = candidates[0][0]
            cr.execute(
                "SELECT 1 FROM ir_model_data WHERE model = 'ems.planning_outcome' AND res_id = %s",
                (live_id,),
            )
            if cr.fetchone():
                continue  # already linked to an xml_id, nothing to do

            cr.execute(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                VALUES (%s, %s, 'ems.planning_outcome', %s, FALSE)
                """,
                (new_module, new_name, live_id),
            )
            _logger.info(
                "Migration 18.0.0.22.0: linked new xml_id '%s.%s' -> ems_planning_outcome.id=%s.",
                new_module, new_name, live_id,
            )


# (model, name) pairs converted from noupdate="1" XML to noupdate=False CSV in this version -
# see docs/en/developers/shared/data_loading.md's "Deciding noupdate=True vs False" for why
# (EMS owns its own cosmetic/business-label data by default; noupdate=1 is reserved for
# genuine "EMS can't know this" gaps, which neither of these had). Both stay module='ems' -
# no ownership rename needed, only the stored noupdate flag changes.
NOUPDATE_CLEARED_XMLIDS = [
    ('mail.activity.type', 'mail_activity_enrollment_comment'),
    ('mail.activity.type', 'mail_activity_student_document_review'),
    ('mail.activity.type', 'mail_activity_attendance_correction'),
    ('res.partner.category', 'partner_category_student'),
    ('res.partner.category', 'partner_category_family'),
    ('res.partner.category', 'partner_category_provider'),
    ('res.partner.category', 'partner_category_applicant'),
    ('res.partner.category', 'partner_category_alumni'),
    ('res.partner.category', 'partner_category_withdrawal'),
]


def _clear_noupdate_for_ems_owned_xmlids(cr):
    for model, name in NOUPDATE_CLEARED_XMLIDS:
        cr.execute(
            "UPDATE ir_model_data SET noupdate = FALSE "
            "WHERE module = 'ems' AND model = %s AND name = %s AND noupdate = TRUE",
            (model, name),
        )
        if cr.rowcount:
            _logger.info(
                "Migration 18.0.0.22.0: cleared noupdate for xml_id 'ems.%s' (%s), "
                "now tracking the CSV file.",
                name, model,
            )


# hr.departure.reason records are owned by the native 'hr' module (hr/data/hr_data.xml,
# <data noupdate="1">), not 'ems' - a different case from NOUPDATE_CLEARED_XMLIDS above (which
# only ever targets EMS's own module='ems' records). data/main/hr.departure.reason.csv adds a
# 'color' field to these three EXISTING reasons (see models/employees/departure_reason.py); left
# untouched, their stored noupdate=True (confirmed empirically 2026-08-01: color stayed NULL
# after a plain ./upgrade.sh with the CSV in place) would silently swallow that CSV's color
# values forever, same underlying mechanism as _rename_data_custom_xmlid_ownership above - only
# the owning module differs, so module is NOT rewritten here (these stay hr's own records).
HR_OWNED_NOUPDATE_CLEARED_XMLIDS = [
    ('hr.departure.reason', 'departure_fired'),
    ('hr.departure.reason', 'departure_resigned'),
    ('hr.departure.reason', 'departure_retired'),
]


def _clear_noupdate_for_hr_owned_xmlids(cr):
    for model, name in HR_OWNED_NOUPDATE_CLEARED_XMLIDS:
        cr.execute(
            "UPDATE ir_model_data SET noupdate = FALSE "
            "WHERE module = 'hr' AND model = %s AND name = %s AND noupdate = TRUE",
            (model, name),
        )
        if cr.rowcount:
            _logger.info(
                "Migration 18.0.0.22.0: cleared noupdate for xml_id 'hr.%s' (%s), "
                "so data/main/hr.departure.reason.csv's color can now reach it.",
                name, model,
            )


def _rename_old_attendance_template_study_column(cr):
    """ems_attendance_template.study_id (Many2one) becomes study_ids (Many2many) in this
    version, and level_id is dropped outright - see
    plans/attendance_template_multi_study.md. Same rename-before-schema-sync gotcha as
    _rename_old_status_columns above: renaming study_id here (before the field is removed
    from the model) keeps its value reachable for the post-migrate backfill, since Odoo's
    own field-removal cleanup would otherwise drop the column outright as soon as schema
    sync runs. level_id needs no such preservation - confirmed (see the plan) it carries
    no information not already derivable from group_ids/study_ids, and has zero downstream
    readers once removed, so there's nothing worth keeping.
    """
    if _column_exists(cr, 'ems_attendance_template', 'study_id'):
        cr.execute("ALTER TABLE ems_attendance_template RENAME COLUMN study_id TO study_id_old")
        _logger.info(
            "Migration 18.0.0.22.0: preserved ems_attendance_template.study_id as "
            "study_id_old for the post-migrate study_ids backfill.")


def _backup_attendance_template_student_rel(cr):
    """ems.attendance_template.student_ids moves to ems.attendance_schedule.student_ids in this
    version - see plans/calendar_driven_attendance_templates.md, point 1. Its relation table
    (ems_attendance_template_res_partner_rel) is dropped outright by Odoo's own schema sync the
    moment the field disappears from the model - same "preserve before schema sync" gotcha as
    '_rename_old_attendance_template_study_column' above, but a Many2many's relation table can't
    be renamed in place the same way a plain column can (the NEW field's own relation table,
    ems_attendance_schedule_res_partner_rel, doesn't exist yet at this point either - it's created
    by the same schema sync that drops this one). Copied into a plain, Odoo-untracked backup table
    instead - post-migrate reads it back once ems_attendance_schedule's own relation table exists,
    then drops it."""
    cr.execute("""
        CREATE TABLE IF NOT EXISTS _ems_migration_template_student_backup AS
        SELECT ems_attendance_template_id AS template_id, res_partner_id AS student_id
        FROM ems_attendance_template_res_partner_rel
    """)
    cr.execute("SELECT count(*) FROM _ems_migration_template_student_backup")
    _logger.info(
        "Migration 18.0.0.22.0: backed up %d ems.attendance_template.student_ids row(s) "
        "before the field moves to ems.attendance_schedule.", cr.fetchone()[0])


def migrate(cr, _version):
    _migrate_role_color(cr)
    _migrate_attendance_template_color(cr)
    _rename_old_status_columns(cr)
    _rename_old_special_columns(cr)
    _rename_old_attendance_template_study_column(cr)
    _dedupe_ems_enrollment(cr)
    _rename_data_custom_xmlid_ownership(cr)
    _reconcile_planning_outcome_xmlids(cr)
    _clear_noupdate_for_ems_owned_xmlids(cr)
    _clear_noupdate_for_hr_owned_xmlids(cr)
    _backup_attendance_template_student_rel(cr)
