import importlib.util
import os

from odoo.tests.common import TransactionCase, tagged


def _load_migration():
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'migrations', '18.0.0.19.1', 'pre-migrate.py',
    )
    spec = importlib.util.spec_from_file_location('ems_migration_18_0_0_19_1', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestPlanningMigrationReconciliation(TransactionCase):
    """Regression test for the 2026-07-08 production deploy failure: a
    noupdate xml_id whose ems.planning row was deleted made Odoo's loader
    attempt a fresh INSERT that collided with 'ems_planning_unique_study_subject'
    because a live row for the same (study, subject) already existed under a
    different (or no) xml_id."""

    def test_orphaned_xmlid_is_relinked_to_matching_live_record(self):
        planning = self.env.ref('ems.planning_dam_0485', raise_if_not_found=False)
        if planning is None:
            self.skipTest("ems.planning_dam_0485 fixture not present in this database")
        live_id = planning.id
        cr = self.env.cr

        # Simulate the production failure: the xml_id points at a res_id that
        # no longer exists, while a live record for the same (study, subject)
        # is still there without any xml_id pointing at it.
        cr.execute(
            "UPDATE ir_model_data SET res_id = %s "
            "WHERE module = 'ems' AND name = 'planning_dam_0485'",
            (live_id + 10_000_000,),
        )

        _load_migration().migrate(cr, None)

        cr.execute(
            "SELECT res_id FROM ir_model_data "
            "WHERE module = 'ems' AND name = 'planning_dam_0485'",
        )
        self.assertEqual(cr.fetchone()[0], live_id)
