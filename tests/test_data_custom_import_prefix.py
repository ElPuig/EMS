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


@tagged('post_install', '-at_install')
class TestDataCustomImportPrefix(TransactionCase):
    """CSV records under data/custom/ must use the __import__. xmlid prefix
    (CLAUDE.md's "Data folder conventions") so an EMS module upgrade never
    silently deletes centre data. XML <record> tags are exempted for now:
    Odoo's XML loader rejects __import__. ids outright (see CLAUDE.md's
    "Hard limitation" note) - that backlog needs converting those files to
    CSV, tracked separately."""

    def test_custom_csv_ids_use_import_prefix(self):
        violations = []
        custom_dir = os.path.join(MODULE_ROOT, 'data', 'custom')
        for dirpath, _dirnames, filenames in os.walk(custom_dir):
            for filename in filenames:
                if not filename.endswith('.csv'):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding='utf-8') as csv_file:
                    lines = csv_file.read().splitlines()
                for line in lines[1:]:
                    record_id = line.split(',', 1)[0].strip('"')
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
