from datetime import date

from odoo.tests.common import TransactionCase


class TestLevel(TransactionCase):

    def test_display_name_computed(self):
        level = self.env['ems.level'].create({'acronym': 'TSCX', 'name': 'Test Display'})
        self.assertEqual(level.display_name, 'TSCX: Test Display')

    def test_acronym_must_be_unique(self):
        self.env['ems.level'].create({'acronym': 'UNIQ', 'name': 'First'})
        with self.assertRaises(Exception):
            self.env['ems.level'].create({'acronym': 'UNIQ', 'name': 'Second'})

    def test_study_ids_relation(self):
        level = self.env['ems.level'].create({'acronym': 'T07', 'name': 'Level With Study'})
        study = self.env['ems.study'].create({
            'code': 'TST001',
            'acronym': 'TSST',
            'name': 'Test Study for Level',
            'date': date.today(),
            'deprecated': False,
            'level_id': level.id,
        })
        self.assertIn(study, level.study_ids)

    def test_convalidation_levels_are_set_from_the_settings(self):
        """Settings > Convalidations lists the levels whose flag is set, and saving it sets and
        clears each level's flag."""
        Level = self.env['ems.level']
        allowed = Level.create({'acronym': 'TCVA', 'name': 'Allowed', 'allows_convalidation': True})
        other = Level.create({'acronym': 'TCVB', 'name': 'Not allowed yet'})
        settings = self.env['res.config.settings'].create({})
        self.assertIn(allowed, settings.convalidation_level_ids)
        self.assertNotIn(other, settings.convalidation_level_ids)
        settings.convalidation_level_ids = other
        settings.set_values()
        self.assertFalse(allowed.allows_convalidation)
        self.assertTrue(other.allows_convalidation)
        self.assertEqual(Level.search([('allows_convalidation', '=', True)]), other)

    def test_new_installation_seeds_the_vocational_cycles(self):
        Level = self.env['ems.level']
        Level.search([]).allows_convalidation = False
        Level._ems_seed_convalidation_levels()
        self.assertEqual(sorted(Level.search([('allows_convalidation', '=', True)]).mapped('acronym')),
                         ['CFGM', 'CFGS'])

    def test_educational_stage_of_the_catalog(self):
        stages = {level.acronym: level.education_stage for level in self.env['ems.level'].search(
            [('acronym', 'in', ['ESO', 'CFGB', 'CFGM', 'CFGS', 'EFPS', 'PFI', 'BTX'])])}
        self.assertEqual(stages, {'ESO': 'compulsory', 'CFGB': 'compulsory', 'CFGM': 'post_compulsory',
                                  'CFGS': 'post_compulsory', 'EFPS': 'post_compulsory', 'PFI': 'post_compulsory',
                                  'BTX': 'post_compulsory'})
