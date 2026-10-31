from odoo import SUPERUSER_ID, api

from odoo.addons.ems import _seed_declaration_codes
from odoo.addons.ems.models.employees.working_schedule import subject_block_name


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _seed_declaration_codes(env)
    _unify_class_block_names(env)


# _seed_declaration_codes: issue #723, the official schedule declaration's codes of the existing
# levels and non-teaching types (post_init_hook does it on a clean install). post-migrate: the
# columns are new in this version and it goes through the ORM.


def _unify_class_block_names(env):
    """Issue #723: the import wrote a class block's name 'MP 0485: Programació (DAM1A)' and the
    Schedule tab 'MP 0485: Programació: DAM1A'; both now write the first (subject_block_name), so
    the blocks already saved, archived ones included, are rewritten to it. Raw SQL for the write:
    'name' is only a label, and an ORM write would run the schedule sync for every block. A clean
    install only ever writes the one format, so it needs no post_init_hook counterpart."""
    blocks = env['resource.calendar.attendance'].with_context(active_test=False).search([('subject_id', '!=', False)])
    renames = [
        (name, block.id) for block in blocks
        if (name := subject_block_name(block.subject_id, block.group_ids, block.topic)) != block.name
    ]
    if renames:
        env.cr.executemany("UPDATE resource_calendar_attendance SET name = %s WHERE id = %s", renames)
        blocks.invalidate_recordset(['name'])
