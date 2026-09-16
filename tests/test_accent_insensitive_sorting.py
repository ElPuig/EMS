# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAccentInsensitiveSorting(TransactionCase):
    """Issue #454: this database's default collation ('C.UTF-8') sorts strings by raw Unicode
    code point, not alphabetically - an accented letter like 'Á' (U+00C1) has a higher code
    point than 'Z' (U+005A), so a real teacher named "Álvaro..." or a student named "Ángela..."
    sorted after every plain A-Z name instead of next to the other A's. __init__.py's
    _apply_icu_collation_to_sort_fields() (mirrored in migrations/18.0.0.26.0/pre-migrate.py)
    fixes this by giving the columns behind the app's main people/catalog list views an ICU
    ('und-x-icu') collation instead. These tests protect that fix from regressing - e.g. a
    future field/column recreation silently dropping the collation override, or a fresh install
    skipping post_init_hook.

    Every fixture below deliberately differs in its very *first* letter (accented vs plain
    'Z...') - the bug only shows up when the accented character is the one actually deciding
    sort order; an accent anywhere else in the string (e.g. a real group named "Reforç
    Programació", which sorts by its leading 'R' regardless of the 'ç' further in) proves
    nothing either way.
    """

    _ICU_COLUMNS = [
        ('ems_group', 'name'),
        ('ems_level', 'name'),
        ('ems_study', 'name'),
        ('ems_subject', 'name'),
        ('hr_employee', 'name'),
        ('res_partner', 'name'),
        ('res_partner', 'firstname'),
        ('res_partner', 'lastname'),
        ('res_partner', 'complete_name'),
    ]

    def test_sort_columns_have_icu_collation(self):
        tables = list({table for table, _column in self._ICU_COLUMNS})
        self.env.cr.execute(
            "SELECT table_name, column_name, collation_name FROM information_schema.columns "
            "WHERE table_name = ANY(%s)",
            (tables,),
        )
        found = {(table, column): collation for table, column, collation in self.env.cr.fetchall()}
        for table, column in self._ICU_COLUMNS:
            self.assertEqual(
                found.get((table, column)), 'und-x-icu',
                f"{table}.{column} should have the 'und-x-icu' collation applied (issue #454).")

    def _assert_accented_sorts_before_z(self, model, column, accented, zeta):
        records = self.env[model].search(
            [('id', 'in', [accented.id, zeta.id])], order=f'{column} asc')
        self.assertEqual(
            list(records.ids), [accented.id, zeta.id],
            f"{model}.{column}: an accented value should sort next to its base letter, "
            "not after 'Z' (issue #454).")

    def test_hr_employee_name_sorts_accented_before_z(self):
        # Mirrors the real records this bug was confirmed against (2026-09-16): a teacher
        # named "Álvaro..." belongs right after the other A's, not after every "Z"/"Y" name.
        accented = self.env['hr.employee'].create({'name': 'Álvaro Test Teacher'})
        zeta = self.env['hr.employee'].create({'name': 'Zulu Test Teacher'})
        self._assert_accented_sorts_before_z('hr.employee', 'name', accented, zeta)

    def test_res_partner_firstname_and_complete_name_sort_accented_before_z(self):
        accented = self.env['res.partner'].create(
            {'contact_type': 'family', 'firstname': 'Ángela', 'lastname': 'Test Family'})
        zeta = self.env['res.partner'].create(
            {'contact_type': 'family', 'firstname': 'Zulu', 'lastname': 'Test Family'})
        self._assert_accented_sorts_before_z('res.partner', 'firstname', accented, zeta)
        self._assert_accented_sorts_before_z('res.partner', 'complete_name', accented, zeta)

    def test_ems_level_name_sorts_accented_before_z(self):
        accented = self.env['ems.level'].create({'acronym': 'ZTST1', 'name': 'Àlvaro Test Level'})
        zeta = self.env['ems.level'].create({'acronym': 'ZTST2', 'name': 'Zulu Test Level'})
        self._assert_accented_sorts_before_z('ems.level', 'name', accented, zeta)

    def test_ems_study_name_sorts_accented_before_z(self):
        _, accented = create_level_study(self, 'ZTST3', study={'name': 'Àlvaro Test Study'})
        _, zeta = create_level_study(self, 'ZTST4', study={'name': 'Zulu Test Study'})
        self._assert_accented_sorts_before_z('ems.study', 'name', accented, zeta)

    def test_ems_subject_name_sorts_accented_before_z(self):
        accented = self.env['ems.subject'].create(
            {'code': 'ZTST-01', 'acronym': 'ZTST1', 'name': 'Àlvaro Test Subject'})
        zeta = self.env['ems.subject'].create(
            {'code': 'ZTST-02', 'acronym': 'ZTST2', 'name': 'Zulu Test Subject'})
        self._assert_accented_sorts_before_z('ems.subject', 'name', accented, zeta)

    def test_ems_group_name_sorts_accented_before_z(self):
        accented = self.env['ems.group'].create(
            {'group_type': 'reinforcement', 'acronym': 'Àlvaro Test Reinforcement'})
        zeta = self.env['ems.group'].create(
            {'group_type': 'reinforcement', 'acronym': 'Zulu Test Reinforcement'})
        self._assert_accented_sorts_before_z('ems.group', 'name', accented, zeta)
