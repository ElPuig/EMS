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

    def find_schedule_lines_for_slot(self, teacher, weekday, start_time, end_time, space=None):
        """Given a teacher + weekday + start_time/end_time (+ optional space), finds every
        currently active 'ems.attendance_schedule' line for that teacher overlapping that slot -
        the reverse of the (weekday, start_time, end_time) matching this module already does at
        sync time (see e.g. 'ems.attendance_template.classify_external_conflicts'/
        'find_self_conflicts'). Extracted as a shared, standalone lookup rather than yet another
        narrowly-scoped inline copy: a full audit (see
        plans/course_transition_teacher_schedule_archival.md) found every existing occurrence too
        tied to its own caller to reuse directly. Meant to be called on the model itself
        (self.env['ems.attendance_schedule'].find_schedule_lines_for_slot(...)) rather than a
        specific record - there is no natural 'self' for a lookup like this. Used by the
        course-transition wizard to find which schedule line(s) back a given
        'resource.calendar.attendance' row, since the two models have no direct FK between them -
        only this same slot-matching convention links them."""
        domain = [
            ('weekday', '=', weekday),
            ('attendance_template_id.teacher_ids', 'in', teacher.id),
        ]
        if space:
            domain.append(('space_id', '=', space.id))
        candidates = self.env['ems.attendance_schedule'].search(domain)
        return candidates.filtered(
            lambda candidate: candidate.ranges_overlap(candidate.start_time, candidate.end_time, start_time, end_time)
        )
