# Technical Reference: `ems.datetime_utils` (`models/shared/datetime_utils.py`)

## Overview

`EmsDatetimeUtils` (`_name = 'ems.datetime_utils'`) is a stateless `AbstractModel` of timezone
and float-hour helpers. Odoo stores `Datetime` fields as naive UTC and represents a "time of
day" (e.g. a schedule slot) as a plain `float` (`8.5` = 8:30), so every consumer needing to
convert between "a float hour in the company/user's local timezone" and "a naive UTC
datetime Odoo can store" goes through this mixin instead of re-deriving the conversion.

None of its methods read or write fields on `self` — some consumers inherit it as a mixin
(`ems.attendance_schedule`, `ems.attendance_session`, `working_schedule.py`, `employee_autocheckout.py`);
others just grab an instance directly, e.g. `models/settings/settings.py`'s
`self.env['ems.datetime_utils']`. Both are equally valid, since there's no per-record state.

---

## Methods

| Method | Purpose |
|--------|---------|
| `current_tz()` | The timezone to use: `context['tz']` if present, else the company's own `partner_id.tz`, else UTC. |
| `time_float_to_local_datetime(date, time_float)` | Combines a `date` and a float hour into an aware local `datetime`. |
| `time_float_to_utc_datetime(date, time_float)` | Same, converted to UTC. |
| `local_datetime_to_utc(dt)` / `utc_datetime_to_local(dt)` | Plain `dt.astimezone(...)` calls. |
| `datetime_to_odoo(dt)` | Strips `tzinfo` — Odoo's `Datetime` fields are naive UTC. |
| `get_local_datetime()` | `datetime.now(self.current_tz())`. |
| `time_to_float(time)` | `datetime.time` → float hour. |
| `next_occurrence_utc(time_float)` | Given a float hour, the next naive-UTC moment that time occurs — today if not yet passed, otherwise tomorrow. Used for scheduling one-off cron-like triggers at a fixed local time. |
| `ranges_overlap(start_a, end_a, start_b, end_b)` | Plain half-open interval overlap test — no timezone awareness needed, both ranges must already be in the same units. |
| `time_string_to_float(value)` | `"17:45"` → `17.75`. |

---

## Fixed in this pass (2026-07-29)

`local_datetime_to_utc`/`utc_datetime_to_local`/`datetime_to_odoo` named their parameter
`datetime`, shadowing the module-level `from datetime import datetime` import inside each
method's own body. Harmless as written — none of the three actually needed the `datetime`
*class* inside their bodies, only the parameter instance's own methods (`.astimezone()`,
`.replace()`) — but the same latent-trap pattern already flagged and fixed elsewhere in this
rollout (`LimesurveyApi.count_participants`'s `list` variable, `ems.base.persistent_hash`'s
`bytes`/`hash`). Renamed the parameter to `dt`; behavior unchanged, covered by
`tests/test_shared_mixins.py::TestEmsDatetimeUtils::test_local_utc_roundtrip_does_not_shadow_the_datetime_class`.

Class renamed `ems_datetime_utils` → `EmsDatetimeUtils`. Tabs → spaces.

## Tests

`tests/test_shared_mixins.py::TestEmsDatetimeUtils` (new, 5 tests) — all against the bare
`self.env['ems.datetime_utils']` recordset, since no method here touches instance state.
