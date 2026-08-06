# Course transition: teacher-schedule archival + historical teaching record

**Status: implementation in progress — phases 1-3 of 8 done, one open question (migration timing for phase 3's backfill).** Written 2026-08-06
from a developer discussion about what should happen to teacher-side scheduling data when
`ems.course_transition_wizard` runs. Revised three times the same day, then implementation started
the same day too. See "Implementation phases" at the bottom for the agreed breakdown and current
progress.

## Decisions (resolved 2026-08-06, developer feedback, three rounds)

1. **Reversed in round 3 — `resource.calendar.attendance` DOES need an `active` field.** An
   earlier round considered skipping this (unlink the migrating blocks, like today) and archiving
   only the whole `resource.calendar` once empty — rejected: unlinking loses the block-level
   history that decision 4 below relies on `resource.calendar` to provide, and archiving (instead
   of unlinking) is also what makes "is this calendar empty of teaching yet?" a simple, reliable
   check (count of remaining *active* teaching blocks), rather than something havingto be inferred
   around a destructive delete. Migrating blocks get **archived**, never `unlink()`'d, from now on.
2. **Terminology confirmed**: "attendance_session" in the original ask meant `ems.attendance_schedule`
   (the recurring weekly slot), not `ems.attendance_session_header`.
3. **The missing calendar↔schedule link is intentional, not an oversight**: a teacher can create
   their own templates/schedules directly, bypassing the normal sync, so a rigid stored FK
   wouldn't always hold. Confirmed via a full audit (see "Investigation: no reusable lookup
   exists") that no existing method already does this lookup in a reusable way — a new method is
   needed, and it does not duplicate anything.
4. **`ems.attendance_template` is rejected** as the historical "who taught what" source —
   precisely *because* of decision 3 (a teacher-authored template with no calendar backing means
   the template side can't be trusted as a complete record of reality). **`resource.calendar` is
   the source instead**: it gains its own `course_id` (Many2one `ems.course`). Its
   `resource.calendar.attendance` lines already carry `subject_id`/`group_ids` directly
   (`working_schedule.py:181-227`) — no indirection through a possibly-teacher-authored, possibly-
   orphaned template needed. This is *why* decision 1 had to be reversed: a historical source whose
   own detail rows get destructively deleted isn't actually a historical source.
5. **Calendar lifecycle: one-per-(teacher, course), archived, never orphaned.** Same shape as
   today's *buggy* behavior (which already mints a new calendar per course name), but done
   correctly: a real `course_id` FK instead of string-matching a name, the *old* calendar
   explicitly **archived** once emptied (decision 6), and the **transition wizard** (not the
   importer) is what creates the next course's calendar and reassigns `resource_calendar_id` — the
   live Schedule-tab editor and the XML importer both go back to simply "operate on whatever
   `resource_calendar_id` currently is," never searching or minting one themselves. `name` is
   computed from `employee.name` + `course_id.name` — same convention as today, now backed by a
   real FK instead of a raw string baked in at creation time.
6. **Round 3 said sessions get archived at transition, via a schedule→session cascade — reversed
   in round 4, the same day, while implementing phase 2.** Round 3's premise was correct on one
   point (`ems.attendance_session_header` already has `active` via the `ems.base` mixin - the
   earlier investigation's claim that it had none was simply wrong, never verified against the
   actual schema) but wrong on the mechanism: **archiving a schedule line must never cascade to
   its sessions, in either direction.** The developer's own reasoning: once a schedule line
   `has_sessions`, its own logistics fields become readonly, so a routine correction (e.g. fixing
   its room) doesn't edit the line in place at all - it **silently** archives the old line and
   creates a new version (`action_new_version()`/`_write_or_new_version()`) purely as a side effect
   of what looks, to whoever's editing it, like a normal in-place change. If that archive cascaded
   to sessions, *every* such routine correction would make the line's whole attendance history
   disappear from a teacher's default view ("el histórico") - exactly the opposite of the intent:
   the sessions are still perfectly valid, current-course history, only the room/time bookkeeping
   changed.
   `test_action_archive_does_not_cascade_to_sessions`/
   `test_action_archive_on_template_does_not_cascade_to_sessions`
   (`tests/test_attendance_template.py`) pin down the "never cascades via `action_archive()`" rule.

   **Round 5, resolved the same day: session archival still happens, just not via a blanket
   `action_archive()` override — it's wired explicitly into phase 5's own cascade instead.** The
   key realization: phase 5 already only archives a schedule line when it has confirmed *no other
   teacher* still needs it (the co-teaching check). That is exactly the same condition under which
   archiving its sessions is safe — nobody still relies on them staying visible. So: at that
   specific point in phase 5 (not as a model-wide `action_archive()` behavior), explicitly archive
   `schedule.attendance_session_ids` too. This gets co-teaching handled *for free* - no separate
   "what if two teachers" logic is needed for sessions specifically, since the schedule-line-level
   decision it piggybacks on already resolved that. A small helper for symmetry with phase 4's own
   calendar→schedule lookup ("given a `resource.calendar.attendance`, find its sessions") is really
   just phase 4's lookup plus a direct `.attendance_session_ids` read - see phase 4 below for the
   exact shape.
7. **The archival cascade**: calendar block archived → check whether any *other* teacher's
   calendar still has a block for that same slot → if none, archive the schedule line (and the
   template if it's left with zero active lines - pre-existing behavior, unaffected by decision 6's
   reversal) → if someone else remains, only remove the departing teacher from `teacher_ids`.
   Sessions are untouched throughout, per decision 6.
8. **Investigated Juan's grade-history mechanism as a possible alternative for decision 4 — confirmed
   a dead end** (see "Investigation: the grade-history route doesn't work"). Out of scope.

## Investigation: what the session TODO actually says (corrects an earlier mistake)

An earlier round of this plan claimed sessions "must never be archived," reading
`models/attendance/attendance_session.py:31-39`'s standing TODO as forbidding it. Re-reading it
precisely, it says the opposite:
```
# TODO:
#   1. Remove unnecessary data.
#   2. Related data should not be never removed, but archived.
#   For example:
#    1. New course, so new templates.
#   2. Removing templates, removes also the schedules.
#   3. Sessions are linked to schedules, so cannot be removed because never should be removed by cascade (only manually).
#    4. The same if a student's group is removed, it should really be archived.
```
Point 2 is the general principle this whole plan already follows: **archive, don't delete**. Point
3 only forbids *removing* sessions via cascade (i.e. don't auto-`unlink()` a session just because
its parent got deleted) — it says nothing against *archiving* them either.

**Correction (round 4): this TODO does not, on its own, call for an automatic archive-cascade
between schedule and session.** An earlier revision of this section read it that way and proposed
exactly that cascade - reverted the same day (decision 6) once it became clear a schedule line can
be archived for reasons unrelated to its sessions' own relevance (a mid-course room correction,
not just a course transition). The TODO's actual scope is narrower: "never delete via cascade,"
not "always archive via cascade." Both readings are consistent with "archive, don't delete" as a
general philosophy - they just disagree on whether it's automatic or an independent decision, and
decision 6 settles on independent.

## Investigation: `resource.calendar` as the historical source — what it actually requires

`resource.calendar.attendance` already stores exactly the facts needed
(`working_schedule.py:181-227`): `subject_id`, `group_ids`, `space_id`, `non_teaching`. Tagging the
*calendar* with `course_id`, keeping its attendance rows archived rather than deleted (decision 1),
and querying them directly answers "who taught subject X to group Y in course Z" — once each
teacher's calendar is genuinely scoped to one course (decision 5).

**One real gap found while checking this pivot's plumbing, still open**:
`resource.calendar.get_employee()` (`working_schedule.py:75-79`) — the *only* existing way to go
from a calendar back to "whose calendar is this" — is a **reverse search**:
```python
def get_employee(self):
    return self.env['hr.employee'].search([('resource_calendar_id', '=', self.id)])
```
This only finds a result while `resource_calendar_id` still points at *this* calendar. The moment a
teacher moves on to next course's calendar (decision 5), the *previous* one becomes permanently
unreachable via `get_employee()` — there would be no way left to ask "whose calendar was this?"
except parsing the employee's name back out of the calendar's own `name` string, which is fragile.

**`resource.calendar` needs its own stored `employee_id` field** (set once, at creation, never
reassigned) for the historical-query goal to actually work once a calendar is no longer the
teacher's *current* one — **confirmed by the developer.** Once added, `get_employee()` becomes a
plain field read instead of a search, correct for archived calendars too.

**Framework calendars** (`is_framework=True`) are not tied to one teacher or one course —
`course_id`/`employee_id` stay optional/empty for those, only ever set on a real personal calendar.

**`ems.attendance_template.course_id`** is not needed for the historical-teaching-record goal now
that `resource.calendar` covers it — out of this plan's scope.

## Investigation: no reusable (weekday, start_time, end_time) lookup exists (confirms decision 3)

| Method | Location | Shape | Why it can't be reused as-is |
|---|---|---|---|
| `_match_schedule_lines` | `attendance_template.py:584-611` | one already-resolved template + parsed dicts | Scoped to one survivor template; deliberately excludes teacher from its key. |
| `classify_external_conflicts` | `attendance_template.py:442-488` | `[(teacher, entries), ...]` | Returns an aggregate recordset, not a 1:1 pairing (by design). |
| `find_self_conflicts` | `attendance_template.py:490-531` | `[(teacher, entries), ...]` | Same aggregate-recordset limitation. |
| `_find_internal_conflicts`/`_find_external_conflicts` | `working_schedule.py:626-653`/`772-831` | `node_cache` dicts | Import-wizard-specific; reimplements rather than reuses the two above, by its own docstring's own admission. |
| `check_overlap` | `attendance_schedule.py:107-151` | a real `ems.attendance_schedule` record | Matches schedule-vs-schedule, never a raw calendar-attendance row. |

**A new method is genuinely needed.** `ems.attendance_mixin` (`models/shared/attendance_mixin.py`)
already describes itself as "a home for future shared attendance-model code too" — the right place.

## Investigation: the grade-history route doesn't work

`ems.student.year_record.subject` (`models/grades/year_record.py:284-352`) carries grades and
attendance-rate only — no teacher field. `ems.grade_session.teacher_id`
(`models/grades/grade_session.py:27`) exists but has no FK to `attendance_template`/`schedule`, is
resolved via the live-only `ems.teaching` (which has two of its own self-documented
`# TODO: course_id` gaps — `teaching.py:15`, `:46`), and is itself `unlink()`'d, not archived, at
course transition (`course_transition_wizard.py:681-685`) precisely because its own uniqueness
constraint carries no course. No shortcut here, independent of everything else in this plan.

## Confirmed current state (background)

1. **The already-reported bug is real**: `course_transition_wizard.py:673` archives
   `ems.attendance_template` via `.write({'active': False})`, bypassing
   `ems.attendance_template.action_archive()`'s own cascade to `attendance_schedule_ids`
   (`attendance_template.py:178-181`). Undetected because the only two tests exercising this
   (`test_course_transition.py:950-959`) use a template fixture with zero schedule lines.
2. **`ems.course` has no real dates** — only integer `start`/`end` years
   (`models/settings/course.py:16-17`) — confirming `course_id` (an FK) is the only sound anchor.
3. **Co-teaching**: N teachers ⇒ N separate `resource.calendar.attendance` rows ⇒ **1** shared
   `ems.attendance_template` ⇒ **1** shared set of `ems.attendance_schedule` lines
   (`attendance_schedule.teacher_ids` is `related`, not stored — `attendance_schedule.py:44`).
   "Remove just the departing teacher, keep the template for the others" is structurally sound.
4. **No UI accommodation exists for "archived but still viewable/drawable"** anywhere in this
   corner of the app today.

## Implementation phases

Agreed 2026-08-06: implement in phases rather than one large change, to bound quota/verification
cost per step and leave room for details that only surface once a piece actually exists (several
already have this session — the session-archival correction, the calendar-as-source pivot, the
`unlink` vs `archive` reversal). Each phase gets its own Red-Green-Refactor-Normalize cycle (per
this repo's standard workflow) and its own `./upgrade.sh`/scoped `./test.sh` gate — pause for
developer review/go-ahead between phases rather than batching them into one pass.

**Phase 1 — done, 2026-08-06.** `course_transition_wizard.py`'s `_apply_cleanup` calls
`action_archive()` on `_templates_to_archive()` instead of `.write({'active': False})`, plus a test
with real `attendance_schedule_ids` on the fixture template asserting the cascade
(`test_apply_archives_the_schedule_lines_of_an_archived_template`). `TestCourseTransition` green
(93 tests).

**Phase 2 — done, 2026-08-06.** `ems.attendance_session_header` already had `active` via `ems.base`
(the earlier claim it didn't was wrong, corrected above — confirmed directly against the DB) —
nothing to add there. Added: `active` to `resource.calendar.attendance`
(`ems_working_schedule_assignation`, `working_schedule.py`, since core Odoo's model has none);
`ems.attendance_schedule.action_archive()` override cascading to `attendance_session_ids`,
mirroring `ems.attendance_template.action_archive()` one level up. Verified the full 3-level chain
(template → schedule → session) with a new test
(`test_action_archive_on_template_cascades_all_the_way_to_sessions`), plus
`test_action_archive_cascades_to_sessions` (schedule level alone,
`tests/test_attendance_template.py`) and `test_attendance_row_active_defaults_true_and_can_be_archived`
(`tests/test_working_schedule.py`). Migration backfilled all 1436 existing
`resource.calendar.attendance` rows to `active=True` automatically (Odoo's own new-column default
behavior, verified via `psql` — no explicit migration script needed).
`TestAttendanceTemplate`/`TestWorkingSchedule`/`TestEmployeeAutocheckout`/`TestGroupSchedule`/
`TestCourseTransition` all green. Nothing calls any of this with real archiving data yet, as
intended for this phase — pure additive capability, no existing behavior changed.

**Phase 3 done** — `course_id`/`employee_id` added to `resource.calendar`
(`models/employees/working_schedule.py`, class `ems_working_schedule`), both blank/optional (never
set for a framework calendar). `name` stayed a plain stored `Char` rather than becoming a genuine
computed field — derived instead at the two real write sites: a new `create()` override (derives
from `employee_id`/`course_id` only when the caller doesn't pass an explicit `name`) and a new
`_refresh_personal_name()` instance method (rebuilds `name` in place, called by `ems_employee.
write()`'s rename hook). `get_employee()` now prefers the stored `employee_id`, falling back to the
pre-existing reverse search for a calendar predating this field — same fallback `_refresh_personal_
name()` uses. `ems_employee.create()` updated to pass `employee_id`/`course_id` instead of a
pre-built name string; its own `_personal_calendar_name()` helper is gone (fully superseded).
Deliberately NOT touched this phase: the XML batch importer's own calendar-minting logic
(`_write_teacher_schedule`) — still creates calendars the old way, per phase 6's own scope ("the
wizard takes over calendar creation"), so calendars created via that path won't get these two
fields until phase 6 lands. `TestEmployeeScheduleLifecycle` (9 tests) and `TestWorkingSchedule` (39
tests) green; no other test file asserts on calendar name text (checked via grep), so no wider
blast-radius run was needed beyond these two classes.

**Backfill migration added the same day, resolving the open question above** — developer's answer:
migrate now, but reuse the current manifest version (no bump). Added
`_backfill_calendar_employee_and_course` to the already-existing
`migrations/18.0.0.22.0/post-migrate.py` (same version this branch's other 18.0.0.22.0 work already
uses) rather than a new version folder. Same signal `get_employee()`'s reverse-search fallback
already relies on: an employee whose *current* `resource_calendar_id` still points at that
calendar; `course_id` set to that employee's company's current course. Verified against this dev
DB's real pre-upgrade state (temporarily rolled back `ir_module_module.latest_version` to force
Odoo to actually re-run the 18.0.0.22.0 migration scripts, since the DB was already at that stored
version from earlier phases this same session — confirmed restored to `18.0.0.22.0` afterward by
Odoo's own upgrade process): 55 of 56 eligible calendars backfilled; the 1 left blank is the
pre-existing orphaned-calendar cardinality bug this same plan already documents — no employee
currently points at it, unreachable via this signal, harmless since nothing reads these fields yet
(phase 4/5's job).

**Phase 4 — The calendar↔schedule lookup.** New method on `ems.attendance_mixin`: given a teacher +
weekday + start_time + end_time (+ space), find the matching `ems.attendance_schedule` line(s).
Tested standalone against fixtures; no caller wired in yet. Finding "the sessions for a given
`resource.calendar.attendance`" (needed by phase 5) is this same lookup plus a direct
`.attendance_session_ids` read on the line(s) it returns - not a separate method, since
`ems.attendance_schedule` already exposes that O2M directly.

**Phase 5 — Wire the real archival cascade.** The transition wizard's migrating-block handling
switches from `unlink()` to archive (phase 2), uses phase 4's lookup to find the matching schedule
line, checks whether any *other* teacher's calendar still has an active block for that slot, and
either (a) archives the schedule line **and its `attendance_session_ids` explicitly, right here**
(safe specifically because this branch already confirmed no other teacher needs them - see
decision 6's round 5; if the template empties out, archives the template too, phases 1-2) or (b)
just removes the departing teacher from `teacher_ids`, leaving the line/sessions untouched for
whoever's left. The first phase that integrates several previous ones at once — most likely place
for new details to surface.

**Phase 6 — The wizard takes over calendar creation.** For each affected teacher, once phase 5 has
run, the transition wizard (not the XML importer) creates/reactivates the next course's calendar
(phase 3's fields) and reassigns `resource_calendar_id`. `_write_teacher_schedule`
(`working_schedule.py:943-951`) and the live Schedule-tab editor simplify to "just use
`teacher.resource_calendar_id`" — no more name search/creation logic in either.

**Phase 7 — The calendar-emptying rule.** Once a teacher's calendar has zero remaining *active
teaching* blocks (excluding non-teaching entries) after phase 5's archival, phase 6's archive+roll
actually triggers. The closing piece that makes phases 5 and 6 operate together automatically
rather than needing a manual trigger.

**Phase 8 — UI.** An explicit "show archived" affordance for `ems.attendance_template`/
`resource.calendar`/`ems.attendance_session_header`; confirm/fix the Schedule-tab grid renders a
read-only view of an archived calendar; expose the new historical query (e.g. a "Teaching history"
view/filter on `resource.calendar` grouped by `course_id`). Last, since it's presentation on top of
data the earlier phases actually produce.

## Explicitly out of scope for this plan

- Anything in `models/grades/` (`ems.grade_session`, `ems.teaching`, `ems.student.year_record`) —
  investigated as a possible shortcut for decision 4, confirmed not viable. Not part of this plan.
- `ems.attendance_template.course_id` — not needed now that `resource.calendar` covers the
  historical-record goal; a separate future decision if wanted for other reasons.
- Retroactively fixing already-orphaned `resource.calendar` records created by the *current*,
  buggy per-course-name importer behavior before step 6 lands — a one-time data cleanup, separate
  from this plan's forward-looking mechanism.
