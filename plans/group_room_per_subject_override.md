Status: not started - design/confirmation only, no implementation yet.

# Problem

`ems.group` has a single fixed `space_id` (the group's classroom). Every place the
working-schedule importer derives a room for a schedule entry uses this same group-level field —
never anything per-subject:

- `ems.attendance_template._write_schedule_sync` / `_plan_schedule_sync`: `first_group.space_id.id`
- `ems.attendance_template.find_external_conflicts`: `self.env['ems.group'].browse(entry['group_ids'][0]).space_id.id`

The external planner XML that `ems.working_schedules_import_wizard` parses never carries a room at
all — only `<Students name="...">` (the group) and `<Subject>`/`<NonTeaching>` (the activity). So
EMS has no way to know, from the file alone, when a group's session for one particular subject
actually happens in a *different* physical room than that group's usual/default one.

Reported 2026-08-01 by the developer: some groups (e.g. two groups that normally share one
classroom) sometimes go to a different room for a specific subject. Confirmed real by reading the
code above — this is a genuine architectural gap, not a misunderstanding of existing behavior.

# Consequences (not yet confirmed which actually bit in the reported incident)

- **False conflict**: two genuinely different-room sessions for the same group get assumed into
  the same room and can raise a spurious overlap `ValidationError`, blocking a legitimate import.
- **Silent incorrect room recorded**: the `ems.attendance_schedule` row ends up pointing at the
  group's default room even when the real session happens elsewhere — wrong for anyone reading the
  schedule afterward (printed report, "Schedule" tab, room-booking overlap checks against other
  data), not just an import-time nuisance.

# Not yet done

- Confirm (empirically, via a real reimport or a reproduction test) whether this specific gap is
  what caused the 2026-08-01 incident, or whether that incident was a different root cause.
- Decide the actual fix shape once confirmed relevant - e.g., an optional per-subject room
  override on `ems.teaching`/`ems.attendance_template`, or extending the planner XML format (if the
  external tool can be made to emit a room), or a manual override on the resulting
  `ems.attendance_schedule` row that survives resync. Needs a decision with the developer given the
  tradeoffs (extra field vs. changing the external planner's export vs. accepting some manual
  correction after every import) — not something to default into silently.

Explicitly deferred by the developer ("no lo arregles aún") - do not implement until asked.
