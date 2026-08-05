# -*- coding: utf-8 -*-

from odoo import models


class EmsAttendanceMixin(models.AbstractModel):
    _name = 'ems.attendance_mixin'
    _description = (
        "Shared code for models about taking/scheduling student and teacher attendance "
        "(ems.attendance_template, ems.attendance_schedule, ...). Currently holds the "
        "'update in place unless real attendance history exists, else archive and recreate' "
        "rule for a model exposing its own computed 'has_sessions' boolean - backing every "
        "caller that can change one of those models' locked fields: the manual 'Edit' button "
        "(action_new_version), the schedule-sync pipeline, and the working-schedule import "
        "wizard, one shared decision instead of each reimplementing the same has_sessions "
        "check. Generic name is deliberate - a home for future shared attendance-model code "
        "too, not just this one rule."
    )

    def _write_or_new_version(self, vals):
        """Writes 'vals' onto this record if it has no real attendance history yet
        ('has_sessions' False), or archives it and creates a fresh replacement carrying 'vals'
        otherwise. Returns the record that now holds 'vals' - self if updated in place, a new
        record otherwise. The inheriting model must already declare its own 'has_sessions' field
        and rely on its own 'action_archive()'/'copy()' behavior (e.g. cascading to children) -
        this method only supplies the shared decision, not any model-specific mechanics."""
        self.ensure_one()
        if not self.has_sessions:
            self.write(vals)
            return self
        self.action_archive()
        return self.copy({'active': True, **vals})
