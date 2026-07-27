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
    C -- Yes --> F[_auto_close_attendance on the stale one]
    F --> E
```

## `_auto_close_attendance()` — the shared close logic

```mermaid
flowchart TD
    A[_auto_close_attendance] --> B[_get_last_working_hour for check_in's date]
    B --> C{Schedule found for that day?}
    C -- No --> D[Log a warning, return False — left open]
    C -- Yes --> E{Scheduled hour already passed?}
    E -- No --> F[Return False — too early, leave open]
    E -- Yes --> G{Scheduled hour is before check_in itself?}
    G -- Yes --> H[Fallback: check_out = check_in + 1h,<br/>notify the employee + their manager to review]
    G -- No --> I[check_out = scheduled hour,<br/>chatter note only]
    H --> J[(write check_out, out_mode='auto_check_out')]
    I --> J
```

`_get_last_working_hour(employee, work_date)` returns the latest `hour_to` among that weekday's `resource_calendar_id.attendance_ids`, converted to a naive UTC datetime via `ems.datetime_utils` — `None` if the employee has no calendar or no slot that day.

## `_cron_auto_check_out()` — the nightly EMS mode

Delegates straight to Odoo's native `_cron_auto_check_out()` unless `res.company.auto_checkout_mode == 'ems'` (see [res.company](../settings/company.md)). When EMS mode is active:

1. Only runs inside the configured retry window (`auto_checkout_time` → `auto_checkout_retry_until`, wrapping past midnight if `start > end`) — a cron that runs more often than once a night would otherwise keep re-evaluating "not yet passed" attendances pointlessly.
2. Finds every open attendance across every employee (not just one), gated the same way as `create()`.
3. Calls `_auto_close_attendance()` per record inside a `try/except`, logging and skipping on error rather than letting one bad record abort the whole batch.

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
