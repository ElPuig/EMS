import importlib.util
from pathlib import Path

from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusStaffMobilityCase

MIGRATION = Path(__file__).parent.parent / 'migrations' / '18.0.0.48.0' / 'post-migrate.py'


@tagged('post_install', '-at_install')
class TestErasmusStaffPlacesMigration(ErasmusStaffMobilityCase):
    """Issue #772 - the upgrade of an installed centre: each staff modality's places go to a
    project and the modalities disappear. A staff call is put back in its old state (modalities,
    mobilities on them, no places per project) and the migration runs on it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        spec = importlib.util.spec_from_file_location('ems_migration_772', MIGRATION)
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)

    def _old_state(self, kind, places, project=None):
        """A staff call as it was: one modality with `places`, an accepted mobility on it, and (when
        `project` is given) that mobility already on the project, no places per project."""
        mobility = self._accepted_staff()
        call = self.staff_call.sudo()
        modality = self.env['ems.erasmus.call.modality'].create({
            'call_id': call.id, 'name': 'Old staff modality', 'places': places})
        # The kind now comes from the levels; an installed centre keeps the value the column had.
        self.env.flush_all()
        self.env.cr.execute("UPDATE ems_erasmus_call_modality SET project = %s WHERE id = %s", [kind, modality.id])
        if project:
            mobility.sudo().project_id = project
        mobility.application_id.sudo().modality_id = modality
        call.project_place_ids.unlink()
        return call, mobility, modality

    def _migrate(self):
        self.env.flush_all()
        self.migration._staff_places_per_project(self.env)
        self.env.invalidate_all()

    def test_places_go_to_the_project_the_mobilities_already_use(self):
        call, mobility, modality = self._old_state('ka121_vet', 2, project=self.staff_vet_project)
        self._migrate()
        self.assertFalse(modality.exists(), "The staff modalities are gone.")
        self.assertEqual(call.project_place_ids.project_id, self.staff_vet_project)
        self.assertEqual(call.project_place_ids.places, 2)
        self.assertEqual(call.places_total, 2)
        self.assertEqual(mobility.project_id, self.staff_vet_project)
        self.assertFalse(mobility.application_id.modality_id)

    def test_the_only_project_of_the_kind_gets_the_places_and_the_mobilities(self):
        Project = self.env['ems.erasmus.project']
        Project.search([('kind', '=', 'ka131_hed')]).write({'active': False})
        only = Project.create({'name': '2099-1-ES01-KA131-HED-000000772', 'kind': 'ka131_hed'})
        call, mobility, _modality = self._old_state('ka131_hed', 1)
        self.assertFalse(mobility.project_id)
        self._migrate()
        self.assertEqual((call.project_place_ids.project_id, call.project_place_ids.places), (only, 1))
        self.assertEqual(mobility.project_id, only, "The mobility without a project takes it.")

    def test_places_that_fit_no_single_project_are_left_for_the_team(self):
        Project = self.env['ems.erasmus.project']
        Project.create([{'name': f'209{index}-1-ES01-KA121-VET-000000772', 'kind': 'ka121_vet'}
                        for index in (7, 8)])
        call, mobility, modality = self._old_state('ka121_vet', 3)
        self._migrate()
        self.assertFalse(modality.exists())
        self.assertFalse(call.project_place_ids, "Not guessed: two projects could be paying them.")
        self.assertFalse(mobility.project_id)
        note = call.message_ids.filtered(lambda message: 'Places per projecte' in (message.body or ''))
        self.assertTrue(note, "A note on the call asks the team to add the places.")
        self.assertIn('3 places', note[:1].body)
