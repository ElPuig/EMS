import csv
import os

from odoo.tests.common import TransactionCase, tagged

MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Exception documented in CLAUDE.md's "Data folder conventions": these ids
# deliberately keep the hr. prefix because they override (deactivate) demo
# job records shipped by the native hr module, the same "overriding a native
# Odoo record" pattern already documented there for data/custom/.
ALLOWED_NATIVE_OVERRIDE_IDS = {
    'hr.job_ceo', 'hr.job_consultant', 'hr.job_developer', 'hr.job_marketing',
    'hr.job_cto', 'hr.job_hrm', 'hr.job_trainee',
}


@tagged('post_install', '-at_install')
class TestDataMainCatPrefix(TransactionCase):
    """CSV records under data/main/ and data/cat/ must use the ems. xmlid
    prefix, or no prefix at all (Odoo expands a bare id to ems. automatically)
    (CLAUDE.md's Data folder conventions). A foreign-module prefix there is
    only legitimate when deliberately overriding a native Odoo record."""

    def test_main_cat_csv_ids_use_ems_prefix(self):
        violations = []
        for base in ('main', 'cat'):
            base_dir = os.path.join(MODULE_ROOT, 'data', base)
            for dirpath, _dirnames, filenames in os.walk(base_dir):
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
                        if record_id.startswith('ems.') or '.' not in record_id:
                            continue
                        if record_id in ALLOWED_NATIVE_OVERRIDE_IDS:
                            continue
                        violations.append('%s: %s' % (os.path.relpath(path, MODULE_ROOT), record_id))
        self.assertFalse(
            violations,
            "data/main/ and data/cat/ CSV records must use the ems. xmlid prefix, "
            "or no prefix at all (see CLAUDE.md's Data folder conventions):\n"
            + "\n".join(violations),
        )
