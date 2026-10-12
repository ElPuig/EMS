import csv
import os

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import convert_file

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Exception documented in CLAUDE.md's "Data folder conventions": an id in data/custom/ that
# intentionally keeps a non-__import__ prefix.
ALLOWED_NON_IMPORT_IDS = {
    'hr.dep_administration',  # overrides a native Odoo hr module record
}

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

    def _custom_csv_import_ids(self):
        """{xmlid name: 'data/custom/...csv'} of every '__import__.' row under data/custom/."""
        names = {}
        custom_dir = os.path.join(MODULE_ROOT, 'data', 'custom')
        for dirpath, _dirnames, filenames in os.walk(custom_dir):
            for filename in filenames:
                if not filename.endswith('.csv'):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding='utf-8', newline='') as csv_file:
                    for row in list(csv.reader(csv_file))[1:]:
                        if row and row[0].startswith('__import__.'):
                            names[row[0].split('.', 1)[1]] = os.path.relpath(path, MODULE_ROOT)
        return names

    def test_custom_data_is_frozen_against_future_upgrades(self):
        # data/custom/ seeds its records only once: what the centre then changes through the app
        # (renaming a group or a classroom, rebalancing a planning's weights, editing a subject)
        # must not be pushed back by the CSV on every upgrade (see CLAUDE.md's "Data folder
        # conventions"). '_ems_freeze_living_custom_data' (models/settings/company.py) already ran
        # during this test run's own module (re)load, via '_register_hook()'.
        csv_ids = self._custom_csv_import_ids()
        self.assertTrue(csv_ids, "no __import__ row found under data/custom/ - fixture assumption broken")
        custom_data = self.env['ir.model.data'].sudo().search([
            ('module', '=', '__import__'), ('name', 'in', list(csv_ids)),
        ])
        self.assertTrue(custom_data, "no data/custom/ record loaded - fixture assumption broken")
        not_frozen = custom_data.filtered(lambda data: not data.noupdate)
        self.assertFalse(
            not_frozen,
            "data/custom/ records not frozen:\n" + "\n".join(
                f"{csv_ids[data.name]}: {data.name}" for data in not_frozen),
        )

    def _reload_data_file(self, path):
        """Loads a data file the way a module upgrade does."""
        convert_file(self.env, 'ems', path, {}, mode='update', noupdate=False, kind='data')

    def test_upgrade_keeps_centre_subjects_and_restores_official_links(self):
        # What 'odoo -u ems' does to the curriculum: reload the catalog and the centre's files.
        eso = self.env.ref('ems.study_eso_175_2022')
        dam = self.env.ref('ems.study_cfgs_icb0_dam_2024')
        handmade = self.env['ems.subject'].create({
            'code': 'T573_HAND', 'acronym': 'T573H', 'name': 'Handmade optative',
            'study_ids': [(6, 0, (eso | dam).ids)],
        })
        custom = self.env.ref('__import__.subject_175_2022_CAT1')
        custom.name = 'Renamed through the app'
        official = self.env.ref('ems.subject_0373')
        official_studies = official.study_ids
        self.assertGreater(len(official_studies), 1, "fixture assumption broken")
        official.study_ids = [(3, dam.id)]

        for path in ('data/cat/ems.study.csv', 'data/cat/ems.subject.csv',
                     'data/custom/eso/ems.subject.csv', 'data/custom/btx/ems.subject.csv',
                     'data/custom/ccff/ems.subject.csv'):
            self._reload_data_file(path)
        self.env.invalidate_all()

        self.assertEqual(handmade.study_ids, eso | dam, "a subject created by hand lost its studies")
        self.assertIn(handmade, eso.subject_ids)
        self.assertEqual(custom.name, 'Renamed through the app', "a centre subject was reverted to its CSV")
        self.assertIn(eso, custom.study_ids)
        self.assertEqual(official.study_ids, official_studies, "the catalog did not restore an official subject's studies")
