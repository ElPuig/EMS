# Technical Reference: `res.config.settings` (EMS extension)

## Overview

`models/settings/settings.py` extends Odoo's `res.config.settings` transient wizard with a `related=..., readonly=False` field for every EMS-added `res.company` field (see [res.company](company.md) for what each one does) — this is what makes them editable from the Settings screen at all. It is a thin proxy: reading/writing any of these fields just reads/writes the underlying `res.company` field through the relation.

**Module file:** `models/settings/settings.py`

The only behaviour that isn't a plain passthrough is `set_values()`, plus the read-only `ems_version` field.

---

## `set_values()` — EMS auto-checkout cron activation

```mermaid
flowchart TD
    A([Admin saves Settings]) --> B[super.set_values writes every related field to res.company]
    B --> C{auto_checkout_mode == 'ems'?}
    C -- No --> D[Nothing else happens]
    C -- Yes --> E{hr_attendance_check_out_cron exists?}
    E -- No --> D
    E -- Yes --> F[Activate the cron: active=True, every 1 hour]
    F --> G[nextcall = next occurrence of auto_checkout_time,<br/>computed via ems.datetime_utils.next_occurrence_utc]
```

Switching `auto_checkout_mode` back to `native` does **not** deactivate the cron — `set_values()` only acts when the mode is `'ems'`; the native mode relies on Odoo/`hr_attendance`'s own built-in auto-checkout instead, which this cron has nothing to do with. Toggling away from `'ems'` currently leaves a previously-activated cron running; if that turns out to matter operationally, it's a one-line follow-up (deactivate the cron in the `else` branch) — not addressed in this DTON pass since it wasn't flagged as broken.

---

## `ems_version` — installed EMS version

Read-only field shown in the **About** block at the bottom of the EMS Management tab. It reads `ir.module.module.latest_version` for `ems` (with `sudo()`), i.e. the version the database was last installed/upgraded to, which is the one actually running, rather than the manifest on disk (code that has been pulled but not yet upgraded would show the new number too early). It is a `default`, not a compute: the settings form takes its initial values from `onchange()`, which never computes a field with no dependencies.

---

## Access Control

Same as any `res.config.settings`: reaching the screen at all requires Settings access (standard Odoo `base.group_system`-gated navigation), not an EMS-specific rule.

---

## Views

| View | File | Notes |
|------|------|-------|
| Settings form | `views/settings/form.xml` | See [res.company](company.md)'s Views section — same page, already covered by the `ems_course_settings` tour; the `ems_settings_edit` tour also checks the About block's version |
