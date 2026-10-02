# -*- coding: utf-8 -*-

from odoo import models

# NOTE: internal marker (see plans/calendar_driven_attendance_templates.md, point 3) - a template
# is only ever meant to be created/archived as a CONSEQUENCE of syncing a teacher's calendar
# (ems.attendance_template._sync_from_schedule_batch*) or a course transition
# (ems.course_transition_wizard), never directly by a user. create()/unlink() are already revoked
# in security/ir.model.access.csv for every group on ems.attendance_template, but archiving is a
# plain write() of 'active', which can't be blocked at that same coarse (create/read/write/unlink)
# granularity without also blocking every other legitimate direct field edit (color, etc.).
# ems.attendance_template.write() is the actual enforcement point (see that model); defined here,
# in the shared mixin both models already depend on, so this method's own archive+copy branch
# (used by both models) and every other legitimate internal caller can import one single constant
# without either model needing to import from the other.
EMS_BYPASS_TEMPLATE_LOCK_KEY = 'ems_bypass_template_lock'

# Bottom-up sync redesign (2026-09-08, docs/en/developers/attendance/attendance_template.md's
# "Bottom-up sync redesign" section) - resource.calendar.attendance's own create()/write()/unlink()
# now automatically re-syncs every affected teacher's schedule (hr.employee._ems_sync_schedule_
# from_calendar(), Phase 3) after a relevant change, so no caller needs to remember to do it by
# hand anymore. Default behavior (this flag ABSENT) is "sync" - the safe default, since forgetting
# to think about this at all must never silently reproduce the old, pre-redesign staleness bug.
# The ONLY reason to set this flag is a caller already doing its OWN batched sync across SEVERAL
# teachers at once in one transaction - _sync_from_schedule_batch's cross-template
# archive-before-write ordering guarantee (see that method's own docstring: avoiding a false
# room-conflict between two different teachers/templates mid-resync) only holds within ONE batched
# call, not across N separate per-row hook triggers - such a caller sets this around its own
# calendar-writing phase, then runs its own explicit batch sync afterward exactly as before. As of
# Phase 7 (2026-09-08) the only real caller left is the working-schedules import wizard's own
# per-teacher calendar write (_write_teacher_schedule) - course_transition_wizard.py no longer
# suppresses at all (letting the hook fire is the whole point of its own Phase 7 simplification,
# see docs/en/developers/settings/course_transition_wizard.md), and _regenerate_all_from_calendars()
# never needed to (it never touches resource.calendar.attendance in the first place).
EMS_SKIP_AUTO_SCHEDULE_SYNC = 'ems_skip_auto_schedule_sync'

# Issue #458 (docs/en/developers/contacts/group.md's "Reference classroom" section) - stops the two
# directions linking a group's reference classroom (ems.group.space_id) and its schedule from
# cascading into each other. While set: ems.group.write() doesn't move the group's classes to a new
# space_id (issue #405's _propagate_classroom_change), and a schedule change doesn't recompute the
# group's space_id (ems.group._sync_reference_space). Set by the automatic recompute's own write,
# by the manual-edit propagation while it moves classes, and by the working-schedules import
# wizard while it writes calendars (its blocks fall back on the group's space_id, so it mustn't
# change halfway through; the wizard recomputes once at the end).
EMS_SKIP_GROUP_CLASSROOM_CASCADE = 'ems_skip_group_classroom_cascade'


class EmsAttendanceMixin(models.AbstractModel):
    _name = 'ems.attendance_mixin'
    _description = (
        "Shared code for models about taking/scheduling student and teacher attendance "
        "(ems.attendance_template, ems.attendance_schedule, ...). Currently holds the "
        "'update in place unless real attendance history exists, else archive and recreate' "
        "rule for a model exposing its own computed 'has_sessions' boolean - backing every "
        "caller that can change one of those models' locked fields: the schedule-sync pipeline "
        "and the working-schedule import wizard's own room-reassignment resolution, one shared "
        "decision instead of each reimplementing the same "
        "check. Generic name is deliberate - a home for future shared attendance-model code "
        "too, not just this one rule."
    )

    def _write_or_new_version(self, vals):
        """Writes 'vals' onto this record if it has no real attendance history yet
        ('has_sessions' False), or archives it and creates a fresh replacement carrying 'vals'
        otherwise. Returns the record that now holds 'vals' - self if updated in place, a new
        record otherwise. The inheriting model must already declare its own 'has_sessions' field
        and rely on its own 'action_archive()'/'copy()' behavior (e.g. cascading to children) -
        this method only supplies the shared decision, not any model-specific mechanics.

        NOTE: BOTH branches run with the template-lock bypass and sudo() (see
        plans/calendar_driven_attendance_templates.md, point 3, and its 2026-08-11 refinement
        locking most of ems.attendance_template's and ems.attendance_schedule's own fields the same
        way) - required for every legitimate internal caller of this method (the schedule-sync
        pipeline, course_transition_wizard's departing-co-teacher correction, the import wizard's
        room-reassignment resolution) on either model: create()/unlink() are revoked in security/
        ir.model.access.csv, and a direct field write is separately blocked by each model's own
        write() override unless this exact flag is set. Found the hard way (2026-08-11): only the
        archive+copy branch originally carried this bypass - the plain in-place write() branch
        didn't, since it predated the schedule model's own write-lock and the template's own lock
        only covering 'active' at the time this method was first written."""
        self.ensure_one()
        bypassed = self.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).sudo()
        if not self.has_sessions:
            bypassed.write(vals)
            return self
        bypassed.action_archive()
        return bypassed.copy({'active': True, **vals})

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
