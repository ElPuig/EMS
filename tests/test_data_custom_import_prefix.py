import csv
import os

from odoo.tests.common import TransactionCase, tagged

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Exceptions documented in CLAUDE.md's "Data folder conventions": ids in
# data/custom/ that intentionally keep a non-__import__ prefix.
ALLOWED_NON_IMPORT_IDS = {
    'hr.dep_administration',  # overrides a native Odoo hr module record
} | {
    'ems.study_%s' % code for code in (
        'cfgm_ic10_smx_2024', 'cfgs_icb0_dam_2024', 'cfgs_icc0_daw_2024',
        'cfgs_ica0_asix_2024', 'efps_ic02_dev_2024', 'cfgm_ag10_ga_2024',
        'cfgs_agb0_aif_2024', 'cfgs_aga0_ad_2024', 'cfpb_ag10_sa_2024',
        'pfi_ag10_ao_2024', 'btx_171_2022', 'eso_175_2022',
    )
}  # extend the shared data/cat/ems.study.csv record with centre subjects

# The one file allowed to stay XML under data/custom/ - see CLAUDE.md's "Confirmed real,
# remaining CSV-incompatible case" note. Its product_id is resolved via a <field search="...">
# domain lookup (no external id of its own to reference), which CSV's load() has no
# equivalent for - every other data/custom/ file has been converted to CSV.
ALLOWED_XML_FILES = {'data/custom/ccff/ems_enrollment_template_opt.xml'}


@tagged('post_install', '-at_install')
class TestDataCustomImportPrefix(TransactionCase):
    """CSV records under data/custom/ must use the __import__. xmlid prefix
    (CLAUDE.md's "Data folder conventions") so an EMS module upgrade never
    silently deletes centre data. Every data/custom/ file is CSV except the
    one documented, confirmed exception in ALLOWED_XML_FILES above (a CSV
    hard limitation, not a backlog item)."""

    def test_custom_has_no_undocumented_xml_files(self):
        violations = []
        custom_dir = os.path.join(MODULE_ROOT, 'data', 'custom')
        for dirpath, _dirnames, filenames in os.walk(custom_dir):
            for filename in filenames:
                if not filename.endswith('.xml'):
                    continue
                rel_path = os.path.relpath(os.path.join(dirpath, filename), MODULE_ROOT).replace(os.sep, '/')
                if rel_path not in ALLOWED_XML_FILES:
                    violations.append(rel_path)
        self.assertFalse(
            violations,
            "data/custom/ must be CSV, not XML, so its records can use the __import__. "
            "xmlid prefix (see CLAUDE.md's Data folder conventions) - undocumented XML "
            "file(s) found:\n" + "\n".join(violations),
        )

    def test_custom_csv_ids_use_import_prefix(self):
        violations = []
        custom_dir = os.path.join(MODULE_ROOT, 'data', 'custom')
        for dirpath, _dirnames, filenames in os.walk(custom_dir):
            for filename in filenames:
                if not filename.endswith('.csv'):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding='utf-8', newline='') as csv_file:
                    rows = list(csv.reader(csv_file))
                for row in rows[1:]:
                    record_id = row[0] if row else ''
                    if not record_id:
                        continue
                    if record_id.startswith(('__import__.', 'base.')):
                        continue
                    if record_id in ALLOWED_NON_IMPORT_IDS:
                        continue
                    violations.append('%s: %s' % (os.path.relpath(path, MODULE_ROOT), record_id))
        self.assertFalse(
            violations,
            "data/custom/ CSV records must use the __import__. xmlid prefix "
            "(see CLAUDE.md's Data folder conventions) so an EMS upgrade never "
            "silently deletes centre data:\n" + "\n".join(violations),
        )
