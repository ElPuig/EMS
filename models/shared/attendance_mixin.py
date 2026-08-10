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

    def find_schedule_lines_for_teaching(self, teacher, subject, groups, weekday, start_time, end_time):
        """Given a teacher + subject + a set of groups + weekday + start_time/end_time, finds
        every currently active 'ems.attendance_schedule' line for that exact teaching slot -
        subject match, ANY group overlap (not exact set equality, mirroring the same "same
        teaching assignment" convention 'ems.working_schedules_import_wizard._classify_conflict_
        kind' already uses), and weekday/time overlap. Deliberately NOT scoped by room
        (2026-08-10, developer feedback, after finding real stray un-archived sessions caused by
        exactly this - "lo que manda es el calendario... el aula no es normal que cambie, [pero]
        no deberíamos usarla para las búsquedas"): a teacher can freely change the room while
        taking attendance for a session (e.g. an unplanned workshop), so a calendar block's own
        room can legitimately drift from the schedule line's authoritative one over time -
        matching on it, as this lookup originally did, silently breaks the very link it exists to
        find, the moment that drift happens. If more than one line matches (e.g. a stale one left
        behind by an earlier edit alongside a newer one), every match is returned - the caller
        decides what to do with each, not this lookup. Extracted as a shared, standalone lookup
        rather than yet another narrowly-scoped inline copy: a full audit (see
        plans/course_transition_teacher_schedule_archival.md) found every existing occurrence too
        tied to its own caller to reuse directly. Meant to be called on the model itself
        (self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(...)) rather than a
        specific record - there is no natural 'self' for a lookup like this. Used by the
        course-transition wizard to find which schedule line(s) back a given
        'resource.calendar.attendance' row, since the two models have no direct FK between them -
        only this same teaching-assignment matching convention links them."""
        candidates = self.env['ems.attendance_schedule'].search([
            ('weekday', '=', weekday),
            ('attendance_template_id.teacher_ids', 'in', teacher.id),
            ('attendance_template_id.subject_id', '=', subject.id),
            ('attendance_template_id.group_ids', 'in', groups.ids),
        ])
        return candidates.filtered(
            lambda candidate: candidate.ranges_overlap(candidate.start_time, candidate.end_time, start_time, end_time)
        )
