# Technical Reference: `hr.attendance` auto-checkout (EMS extension)

## Overview

`models/employees/employee_autocheckout.py` extends `hr.attendance` with two related behaviours: closing a **stale** open attendance the moment a new one is checked in (so Odoo's own "already checked in" block never fires for a forgotten previous day), and an EMS-specific nightly cron mode that closes any still-open attendance using the employee's **actual working schedule** for that day, instead of Odoo's native fixed-hours logic.

**Module file:** `models/employees/employee_autocheckout.py`

Both paths are gated by `res.company.auto_check_out` (native `hr_attendance` field) and only ever touch employees whose `resource_calendar_id.flexible_hours` is `False` — an employee on a flexible schedule is deliberately left to native Odoo behaviour.

---

## `create()` — closing a stale attendance before opening a new one

```mermaid
flowchart TD
    A[New hr.attendance being created, no check_out] --> B{Employee already has\nan OPEN attendance?}
    B -- No --> E[Proceed to create]
    B -- Yes --> C{auto_check_out enabled AND\nnot flexible_hours?}
    C -- No --> D[Leave the old one open —\nOdoo's native validation will\nreject the new check-in]
    C -- Yes --> F[_close_stale_attendance_safely\non the stale one]
    F --> E
```

This is the **check-in-triggered backup** for the nightly cron below: if the cron missed a
run (a bug, a server restart mid-window, a misconfigured retry window), the very next time
that same employee checks in for real, the stale attendance gets a chance to close right
then — visibly, since a failure here surfaces through the *same* check-in request instead of
silently at 3am with nobody watching. It does **not** replace the cron: an employee who
doesn't come back soon (leave, absence, departure) still needs the cron as the only
mechanism that eventually corrects the data regardless of employee action.

## `_get_stale_attendance_domain()` / `_close_stale_attendance_safely()` — shared by both paths

`create()`'s per-employee lookup and the cron's company-wide one both build their search
from `_get_stale_attendance_domain()` (`create()` adds `('employee_id', '=', employee_id)`
on top; the cron uses it as-is) — the three eligibility conditions
(`check_out = False`, `company.auto_check_out = True`, `not resource_calendar_id.flexible_hours`)
are written in exactly one place.

Once a stale attendance is found, both paths hand it to `_close_stale_attendance_safely()`
rather than calling `_auto_close_attendance()` directly:

```mermaid
flowchart TD
    A[_close_stale_attendance_safely] --> B[cr.savepoint\naround _auto_close_attendance]
    B -- succeeds --> C[done]
    B -- raises --> D[log the failure]
    D --> E[_notify_close_failure]
    E -- raises too --> F[log that too, still don't propagate]
```

The `cr.savepoint()` is what actually isolates one bad record from whatever else is going
on in the same transaction: a bare `try/except` alone does **not** undo Postgres's own
"transaction aborted" state once a genuine DB-level error occurs — every subsequent
statement in that same run would fail too without it (this is exactly the blast radius the
microsecond bug below used to have, every single night).

## `_auto_close_attendance()` — the shared close logic

```mermaid
flowchart TD
    A[_auto_close_attendance] --> B[_get_closing_hour for check_in's date]
    B --> C{Working hours expected that day?}
    C -- Yes --> E{Closing hour already passed?}
    C -- No --> K{Framework has a period that weekday?}
    K -- No --> D[Log a warning, return False - left open]
    K -- Yes --> E
    E -- No --> F[Return False - too early, leave open]
    E -- Yes --> G{Closing hour is before check_in itself?}
    G -- Yes --> H[Fallback: check_out = check_in + 1h,<br/>notify the employee + their manager to review]
    G -- No --> I[check_out = closing hour,<br/>chatter note only - naming the framework<br/>when it came from it]
    H --> J[(write check_out, out_mode='auto_check_out')]
    I --> J
```

`_get_closing_hour(employee, work_date)` (and `_get_last_working_hour()`, which returns just its hour) gives the naive UTC hour to close at: the end of the last stretch the employee was actually **expected** to work that day or, when nothing was expected of them that day, the end of that day in their framework (see below). `None` only when neither exists.

**It asks the calendar what was expected; it does not read the raw weekly timetable** (changed 2026-09-08, when `hr_holidays` first made absences visible to Odoo — see [Staff absences](absence.md)). An approved absence becomes a `resource.calendar.leaves` row on the employee's own calendar, and Odoo's `hr.employee._get_expected_attendances()` already subtracts those (it calls `_work_intervals_batch` with `compute_leaves=True`). The earlier version filtered `resource_calendar_id.attendance_ids` by weekday and took the latest `hour_to`, which knew nothing about leave: a teacher who left at 14:00 with the afternoon approved off and forgot to check out had their attendance closed at 18:00, crediting four hours they had permission to miss. Only an **approved** absence counts — a request still awaiting its approver never becomes a resource leave, so it correctly changes nothing.

**Nothing expected that day: the framework's end of day.** The purpose of the auto check-out is to close a forgotten attendance, so the next check-in isn't taken as its check-out. When the employee's own timetable expects nothing of them that day but they checked in anyway (a personal schedule with no slots yet, e.g. a new course's schedule created by the course transition's rollover and not filled in yet, since `seed_from_framework()` only records `source_framework_id` and never writes rows; a weekday they don't work; an absence covering the whole day), `_get_closing_framework()` returns the schedule's `source_framework_id` (or the company's `default_schedule_framework_id` for a schedule predating that reference), and the attendance closes at the end of that weekday's last framework period. No absence is subtracted there: the fallback only applies to a day nothing was expected anyway. So a morning-only teacher on the ESO framework closes at 14:40; the admin chooses the right framework per teacher. The chatter note names the framework used. Auto check-in (`_is_within_working_hours()`) deliberately keeps reading only the real timetable, so nobody is checked in automatically on a day nothing was expected of them.

`None` (no expected hours and no framework period that weekday, e.g. a weekend, or no schedule at all) leaves the attendance open, with a `WARNING` in the log, for a human to correct. Covered by `TestEmployeeAutocheckout`.

## `_cron_auto_check_out()` — the nightly EMS mode

Delegates straight to Odoo's native `_cron_auto_check_out()` unless `res.company.auto_checkout_mode == 'ems'` (see [res.company](../settings/company.md)). When EMS mode is active:

1. Only runs inside the configured retry window (`auto_checkout_time` → `auto_checkout_retry_until`, wrapping past midnight if `start > end`) — a cron that runs more often than once a night would otherwise keep re-evaluating "not yet passed" attendances pointlessly.
2. Finds every open attendance across every employee (not just one) via `_get_stale_attendance_domain()`.
3. Hands each one to `_close_stale_attendance_safely()` — see above.

## `_notify_close_failure()` — telling someone, not just the log

Schedules a `mail.mail_activity_data_todo` activity for every user in `ems.group_academic_admin`.
Scheduled on `employee_id`, not on the attendance itself: `hr.attendance` only inherits
`mail.thread` (no `mail.activity.mixin`), while `hr.employee` already does.

**Known, accepted gap (2026-09, verified empirically, not chased further):** when this runs
*nested* inside the very `create()` call that goes on to raise its own native "already
checked in" validation right after — i.e. the failure is discovered during the *employee's
own* check-in attempt, which Odoo's own validation then blocks anyway — the scheduled
activity is not reliably kept; something in that specific combination (schedule an activity,
then have the *same* top-level ORM call fail right after) discards it. Calling this from the
cron's own loop (one call per record, never followed by a same-call failure) is unaffected.
Low impact either way: the underlying safety guarantee (the transaction never gets corrupted,
the stale attendance is never wrongly half-closed, the new check-in stays correctly blocked)
holds regardless — the same stuck attendance gets picked up by the next cron run or the
employee's next real check-in either way, just without that one immediate notification.

### The microsecond bug (issue #422, fixed 2026-09)

Odoo core's `hr.attendance._get_day_start_and_day()` computes a "day start" instant via `dt.replace(hour=0, minute=0, second=0)` — it never resets **microseconds**. A `check_in` stamped with `datetime.now()` (has microseconds, typical of any real kiosk/systray punch) and a `check_out` set to a "clean" value (no microseconds — typed by hand in the form, or computed by `_auto_close_attendance()`) on the **same calendar day** therefore produce two distinct day-start instants for the exact same date. `hr.attendance._update_overtime()` treats those as two different days to recompute, and both independently decide to `create()` a new `hr.attendance.overtime` row for the same `(employee_id, date)` — a self-collision against that table's own `UNIQUE(employee_id, date) WHERE NOT adjustment` index (`psycopg2.errors.UniqueViolation`).

This model's own override of `_get_day_start_and_day()` fixes it at the single source every write path (`create()`, `write()`, both crons, the native absence-detection cron) goes through: `day_start.replace(microsecond=0)`.

**Blast radius before the fix:** because the nightly cron processed every open attendance in one shared transaction without a savepoint, the first record to hit this bug poisoned the transaction for every attendance processed afterward in that same run — silently, every night, for as long as at least one stale open attendance's `check_in` happened to carry microseconds and land on the same calendar day as its computed `check_out`. See `migrations/18.0.0.24.0/post-migrate.py`'s `_close_stale_attendances_same_day` for the one-off repair of the production data this left behind (stuck-open attendances, and attendances closed days late via a different-day kiosk badge-in, producing nonsensical multi-day `worked_hours`).

---

## Access Control

No EMS-specific `ir.model.access.csv` rows — inherits `hr_attendance`'s own access rules unchanged.

---

## Data/Config

| Field | Model | Purpose |
|-------|-------|---------|
| `auto_check_out` | `res.company` (native) | Master switch for both behaviours above |
| `auto_checkout_mode` | `res.company` (EMS) | `'native'` (default) or `'ems'` — selects which `_cron_auto_check_out()` logic runs |
| `auto_checkout_time` / `auto_checkout_retry_until` | `res.company` (EMS) | The nightly retry window |

See [res.company](../settings/company.md) and [res.config.settings](../settings/settings.md) for how these are exposed/activated (the `res.config.settings.set_values()` cron-activation logic documented there is the other half of this feature).
