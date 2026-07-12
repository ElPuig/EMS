# -*- coding: utf-8 -*-

from . import controllers
from . import models


def post_init_hook(env):
    """'resource.calendar' auto-fills 'attendance_ids' from the company's own calendar whenever a new
    calendar is created without attendance lines in the same create() call (resource_calendar.py's
    '_compute_attendance_ids', @api.depends('company_id')) — this silently injects extra lines into
    any schedule framework whose own attendance lines are created as separate child records/rows
    (CSV parent+child files, e.g. data/custom/resource.calendar[.attendance].csv). Every legitimate
    framework attendance line ships with a real xmlid; the auto-filled ones never get one, so purge
    any attendance line on a framework calendar that isn't backed by one."""
    env.cr.execute("""
        DELETE FROM resource_calendar_attendance rca
        USING resource_calendar rc
        WHERE rca.calendar_id = rc.id
          AND rc.is_framework = true
          AND NOT EXISTS (
              SELECT 1 FROM ir_model_data d
              WHERE d.model = 'resource.calendar.attendance' AND d.res_id = rca.id
          )
    """)