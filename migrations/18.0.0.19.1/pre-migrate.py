# -*- coding: utf-8 -*-
import glob
import logging
import os
from xml.etree import ElementTree

_logger = logging.getLogger(__name__)

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# (model, name) pairs whose data/custom/ record id gained the __import__.
# prefix in this version (see CLAUDE.md's "Data folder conventions"). These
# xmlids already exist in production under module='ems' - repoint their
# ownership to '__import__' in place so the module upgrade never sees them
# as new/missing (no res_id changes, purely an ownership rename).
RENAMED_CUSTOM_XMLIDS = [
    ('crm.team', 'team_administration'),
    ('crm.team', 'team_after_school'),
    ('crm.team', 'team_shop'),
    ('ems.group', 'group_btx1_101ct'),
    ('ems.group', 'group_btx1_101hu'),
    ('ems.group', 'group_btx1_102ci'),
    ('ems.group', 'group_btx1_102so'),
    ('ems.group', 'group_btx2_201'),
    ('ems.group', 'group_btx2_202'),
    ('ems.group', 'group_eso1a'),
    ('ems.group', 'group_eso1b'),
    ('ems.group', 'group_eso1c'),
    ('ems.group', 'group_eso1d'),
    ('ems.group', 'group_eso1e'),
    ('ems.group', 'group_eso2a'),
    ('ems.group', 'group_eso2b'),
    ('ems.group', 'group_eso2c'),
    ('ems.group', 'group_eso2d'),
    ('ems.group', 'group_eso3a'),
    ('ems.group', 'group_eso3b'),
    ('ems.group', 'group_eso3c'),
    ('ems.group', 'group_eso3d'),
    ('ems.group', 'group_eso4a'),
    ('ems.group', 'group_eso4b'),
    ('ems.group', 'group_eso4c'),
    ('ems.group', 'group_eso4d'),
    ('ems.group', 'group_eso4e'),
]

# NOTE: the ems.planning, ems.authorization.template, ems.course,
# ir.sequence and sale.order.template.line records under data/custom/ are
# declared via XML <record> tags, not CSV. Odoo's XML loader
# (odoo/tools/convert.py::_test_xml_id) unconditionally rejects any record
# id whose module prefix isn't an actually installed Odoo module - and
# '__import__' never is - so `<record id="__import__.xxx">` always raises
# "The ID ... refers to an uninstalled module" and aborts the whole load.
# __import__ is only usable for CSV-loaded data (odoo/models.py's
# _load_records default context, used by CSV import/load()). Those XML
# records are therefore intentionally left owned by 'ems' for now; see the
# note left in CLAUDE.md's "Data folder conventions" - fixing them requires
# converting the files to CSV (straightforward for flat models, non-trivial
# for ems.planning's nested planning_outcome_ids), not a simple id rename.


def _rename_custom_xmlid_ownership(cr):
    for model, name in RENAMED_CUSTOM_XMLIDS:
        cr.execute(
            "UPDATE ir_model_data SET module = '__import__' "
            "WHERE module = 'ems' AND model = %s AND name = %s",
            (model, name),
        )
        if cr.rowcount:
            _logger.info(
                "Migration 18.0.0.19.1: rescoped xml_id 'ems.%s' (%s) -> '__import__.%s'.",
                name, model, name,
            )


def _iter_planning_records():
    """Yield (xml_id, study_ref, subject_ref) for every ems.planning record
    declared under data/custom/*/ems.planning.*.xml."""
    pattern = os.path.join(MODULE_ROOT, 'data', 'custom', '*', 'ems.planning.*.xml')
    for path in sorted(glob.glob(pattern)):
        for record in ElementTree.parse(path).getroot().iter('record'):
            if record.get('model') != 'ems.planning':
                continue
            xml_id = record.get('id')
            study_ref = subject_ref = None
            for field in record.findall('field'):
                if field.get('name') == 'study_id':
                    study_ref = field.get('ref')
                elif field.get('name') == 'subject_id':
                    subject_ref = field.get('ref')
            if xml_id and study_ref and subject_ref:
                yield xml_id, study_ref, subject_ref


def _resolve_xmlid(cr, xml_id):
    module, _, name = xml_id.rpartition('.')
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
        (module or 'ems', name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, _version):
    """Odoo's create-vs-update algorithm (ir.model.data::_lookup_xmlids) decides
    to create a fresh record whenever a noupdate xml_id's target row no longer
    exists (e.g. it was deleted through the UI). If a live ems.planning row for
    the same (study_id, subject_id) already exists without that xml_id - created
    by hand, or left behind by a previous partial load - the fresh INSERT the
    loader attempts collides with the 'ems_planning_unique_study_subject'
    constraint and aborts the whole module load. Re-link each such orphaned
    xml_id to its matching live row so the loader performs an update instead.
    """
    _rename_custom_xmlid_ownership(cr)

    for xml_id, study_ref, subject_ref in _iter_planning_records():
        planning_id = _resolve_xmlid(cr, xml_id)
        if planning_id is not None:
            cr.execute("SELECT 1 FROM ems_planning WHERE id = %s", (planning_id,))
            if cr.fetchone():
                continue  # xml_id already points at a live record, nothing to do

        study_id = _resolve_xmlid(cr, study_ref)
        subject_id = _resolve_xmlid(cr, subject_ref)
        if study_id is None or subject_id is None:
            continue  # study/subject not loaded yet, nothing to reconcile

        cr.execute(
            """
            SELECT p.id FROM ems_planning p
            WHERE p.study_id = %s AND p.subject_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM ir_model_data d
                  WHERE d.model = 'ems.planning' AND d.res_id = p.id
              )
            """,
            (study_id, subject_id),
        )
        candidates = cr.fetchall()
        if len(candidates) != 1:
            if candidates:
                _logger.warning(
                    "Migration 18.0.0.19.1: %d unlinked ems.planning candidates found "
                    "for xml_id '%s' (study_id=%s, subject_id=%s); skipping, needs manual review.",
                    len(candidates), xml_id, study_id, subject_id,
                )
            continue

        live_id = candidates[0][0]
        module, _, name = xml_id.rpartition('.')
        module = module or 'ems'
        if planning_id is None:
            cr.execute(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                VALUES (%s, %s, 'ems.planning', %s, TRUE)
                """,
                (module, name, live_id),
            )
        else:
            cr.execute(
                "UPDATE ir_model_data SET res_id = %s WHERE module = %s AND name = %s",
                (live_id, module, name),
            )
        _logger.info(
            "Migration 18.0.0.19.1: reconciled orphaned xml_id '%s.%s' -> ems_planning.id=%s.",
            module, name, live_id,
        )
