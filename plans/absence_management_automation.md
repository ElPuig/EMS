# Absence management: optional automatic mode

**Status:** not started, current as of 2026-10-07 (written right after issues #539/#571/#581
shipped the manual version, branch `539-absence-guard-management`).

## Context

The guard duty board's absences table lets the absent teacher's chain of command send guards,
propose timetable-change notices and correct what an absence that changed afterwards made
unnecessary or wrong (see "Managing absences from the board" in
`docs/en/developers/attendance/guard_duty_board.md`). Every one of those steps is manual on
purpose (developer, 2026-10-07: *"De momento vamos a hacerlo manual, en un futuro ya plantearemos
la opción de que funcione automático via settings"*).

## What an automatic mode could do (each behind its own setting, off by default)

- **Release a guard who is no longer needed** (the board's `obsolete_cover` action) as soon as the
  absence is refused, cancelled or shrunk, notifying the guard.
- **Propose the correction** of a sent timetable-change notice (the `rectification` action) by
  creating its draft automatically and notifying whoever sent the original one - never sending it
  without a person reviewing it, since it reaches families.
- Possibly, a reminder to the chain of command when an absence for tomorrow still has uncovered
  classes.

## Open questions

- Trigger: an `hr.leave`/`ems.absence_pending` state change hook, a cron, or both.
- Where the settings live (`res.config.settings`, Attendance section) and who may change them.
- Whether a released guard should also be told who released them (system vs. a person).
