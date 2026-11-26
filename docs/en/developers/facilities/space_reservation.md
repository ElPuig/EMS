# Technical Reference: Space Reservation (`ems.space_reservation`)

## Overview

A teacher reserves a free space for a time span. A space is busy when a weekly schedule block, a
reservation or a meeting holds it. **A meeting's room is a reservation too**: `ems.minute` makes
and keeps one automatically, so a meeting and a teacher asking for the same room go through the
same check.

```mermaid
flowchart LR
    BLK["resource.calendar.attendance (space_id)<br/>classes and duties, weekly"] --> ENG
    RES["ems.space_reservation"] --> ENG["ems.space._get_space_conflicts(start, end)"]
    MIN["ems.minute (room, start, duration)"] -->|_ems_sync_space_reservation| RES
    ENG --> CON["constraint on the reservation: ValidationError naming who holds the space"]
    ENG --> AVL["available_space_ids: what the form's Space field offers"]
    ENG --> WIZ["ems.space_reservation_wizard: free spaces (by date) or what holds a space (by space)"]
```

## Why a model of its own (Odoo way)

- Odoo Community 18 has no room booking; the *Meeting Rooms* (`room`) app is Enterprise-only.
- OCA `resource_booking` books combinations of `resource.resource` against a `resource.calendar`
  and creates a `calendar.event` with invitation emails per booking. Here a space is not a
  resource and what occupies it lives in the teachers' schedule blocks
  (`resource.calendar.attendance.space_id`), so it would need a mirrored calendar per space, the
  meetings would have to create its bookings, and it brings portal and external-customer flows
  that EMS does not use.

## Data model

| Field | Notes |
|-------|-------|
| `space_id` | Required, indexed; the space must be `reservable` unless a meeting made the reservation. |
| `start_datetime` | Required, indexed, defaults to now. |
| `duration` | Hours, greater than zero. |
| `end_datetime` | Computed and stored, so the overlap search runs in SQL. |
| `reason` | Free text. |
| `user_id` | Who reserved it (defaults to the current user). |
| `minute_id` | Set when a meeting made it (`ondelete='cascade'`); the reservation follows the minute. |
| `available_space_ids` | Computed, not stored: the spaces free for the span typed so far. The form's `space_id` has `domain="[('id', 'in', available_space_ids)]"`. |

## The reservation wizard (`ems.space_reservation_wizard`)

The list's **New** button (`display="always"` header button, the list has `create="false"`) opens the
wizard instead of the form. The first field is `mode`:

- **By date** (`date`): day and type (same row), start and end time (the wizard asks for an end time; `duration` is computed from it), then the list of free spaces and, below it, the reason (full width). The free spaces are `free_space_ids`, a non-stored computed
  many2many of `ems.space` over `mode`/`date`/`start_time`/`end_time`/`space_type_id`, so the form's
  onchange recomputes them at every change (no search button): the reservable spaces (of that type)
  that `_filter_free` leaves free, none while the end is not after the start (the form then
  says so). Cost per change: the two searches of any availability check (see below).
- **By space** (`space`): choosing a space shows its week as a grid, `ems_space_week_grid`
  (`static/src/js/backend/space_week_grid_field.js`, hosted by the computed boolean `show_grid`, true
  once there is a space; there is no search button, the grid loads itself). The widget asks `get_occupation_week(space_id, monday)` for the
  seven days, what holds the space in each (from `_get_space_busy`: weekly schedule blocks and
  reservations, hours as floats in the company's timezone) and the hours the grid covers (the school
  day of the default schedule framework, widened to take in anything held outside it). It only draws:
  the server decides what is held. Dragging over a free time (or a click, for an hour) writes the
  slot into `space_day`/`space_start`/`space_end`, which can also be typed; a held time or a day
  gone by cannot be chosen. Typed by hand, a day and start that have already begun are refused on the spot
  (see below). The weekend is hidden unless ticked. A dotted red line marks the current time in today's column (the company's `serverNow()`, moved every minute); what is above it is shaded and cannot be chosen. Each mode has its own slot fields
  (`date`/`start_time`/`end_time`/`reason` by date, `space_*` by space) so each lays out its own form.
  Reserving creates the reservation (never in the past) and opens it.

The past, in both modes: the wizard opens on the next full hour of the company's day, for an hour
(`_default_slot`; tomorrow at 10:00 once it is past 22:00), so its first onchange never lands on a
time gone by. `_onchange_slot_not_past` (on `mode`, `date`/`start_time`, `space_day`/`space_start`)
refuses a day and start that have already begun: a warning dialog, and the mode's day is cleared, so
nothing is offered or drawn and *Reserve* stays disabled. Both date fields grey out the past days in
their picker (`min_date: 'today'`, a display aid only, read from the browser's clock: the server
decides, and `action_reserve` refuses the past again).

The free spaces are chosen with a radio button per row (`ems_radio_row`, `static/src/js/backend/radio_row_field.js`,
hosted by the space's `reservable` column, which only gives it a place), or by clicking anywhere on the row
(the widget listens on its row, which is highlighted). Either way it writes the space into `chosen_space_id`
of the wizard, so the footer's *Reserve* (`action_reserve`) is enabled only once a space is chosen (until
then a lookalike button with the `disabled` class is shown, since a view button has no disabled attribute).
`chosen_space_id` is a stored compute (`readonly=False`) over the same fields as the list: it keeps the
choice while that space is still free and drops it when it is not (compared by `_origin` id, since the
onchange hands it over as a new record). The list is paginated ten rows at a time (`limit="10"`, the
standard x2many pager), so the dialog does not grow with the results; the choice lives on the wizard, not on
a page. The web client appends the rows an onchange links at the end, unsorted, so the list uses
`ems_sorted_x2many` (`static/src/js/backend/sorted_x2many_field.js`, an `X2ManyField` that re-applies the
list's `default_order` whenever its rows change): a space that becomes free is shown in its place by name,
not on the last page. *Reserve* creates the reservation (never in the past) and opens it.

Not reservable: `ems.space_type.reservable` (WC...) decides it for the spaces of the type through
`ems.space.reservable`, a stored compute that can still be set on one space. A non-reservable space
is never offered, its type is not offered in the type filter, and a reservation on it is refused
(except a meeting's, which may hold any room). The catalogue (`data/main/ems.space_type.csv`)
carries `Warehouse` and `WC` (not reservable) so they translate; `migrations/18.0.0.53.0/pre-migrate.py`
gives their xmlids to the ones an installation made by hand, before the data loads, so the
catalogue does not add a second one.

Calendar view: not offered. Seven simultaneous reservations are unreadable side by side, and the two
modes answer what is asked.

## What holds a space (`ems.space._get_space_busy` / `_filter_free` / `_get_space_conflicts`)

`spaces._get_space_busy(start, end, exclude_reservations=None)` returns one dict per holder (space,
local start and end, who, whether it is a reservation). Two readings of it: `_filter_free` keeps the
spaces nothing holds (what the reservation form and the wizard offer), and `_get_space_conflicts`
gives `{space id: [texts]}` for the busy ones only, for the messages of a clash. It runs under `sudo()`: whether a room is taken
is a fact about the whole centre, not about what the acting user may read.

1. **Reservations** overlapping `[start, end)` (adjacent spans do not clash).
2. **Weekly blocks**: `resource.calendar.attendance` rows of an active calendar with that
   `space_id`, the local weekday, an overlapping hour range and `date_from`/`date_to` covering
   the day. Breaks (`non_teaching_is_break`) never hold a space. Hours are read in the company's
   timezone (see `docs/en/developers/shared/timezones.md`); a span crossing midnight takes the
   blocks of every day it touches (one search for the weekdays of the whole span, the days walked
   in memory).

Cost: two searches for any number of spaces and any length of span. Measured on this box's data (85
spaces, 1,679 blocks with a space, `odoo shell`, 2026-11-26): the wizard's free spaces for a slot
(recomputed at every change) 21 ms / 14 queries cold, 5 ms / 3 queries warm (36 spaces free); the
reservation form's available spaces 15 ms / 9 queries cold, 5 ms / 3 warm; the week of the busiest
space for the grid 27 ms / 12 queries cold, 6 ms / 4 warm (69 blocks); a meeting with a room costs
2-3 ms and 3-4 queries more to save than one without.

Weekly blocks are the single schedule source on purpose: they are what the space's own
*Schedule* tab shows. `ems.attendance_schedule` is derived from them (bottom-up sync) and is not
read here, or a class would be counted twice.

## Meetings

`ems.minute._ems_sync_space_reservation()` (called from `create` and from `write` when
`space_id`, `start_datetime`, `duration` or `modality` change) keeps exactly one reservation while
the meeting has a room, a start, a duration and is in person or hybrid, and none otherwise (no
room, online, by email). The reservation is written under `sudo()` for the minute's creator, since
whoever edits the minute later did not ask for the room. A room that is taken makes the minute's
save fail with the reservation's message. Deleting the minute deletes the reservation.

## Existing installations

`migrations/18.0.0.53.0/post-migrate.py` gives a reservation to every meeting already scheduled in a
room (in person or hybrid, starting from now), oldest first, so when two of them hold the same room
at once the earlier one keeps it. A meeting whose room is taken is left without a reservation and
logged as a warning; the migration never fails on existing data. Past meetings need none. A clean
install has no meetings, so it needs nothing in `post_init_hook`.

## Access

| Role | Read | Create | Write / delete |
|------|------|--------|----------------|
| Teacher (and every role implying it) | all | own | own, never one made by a meeting |
| Secretary | all | yes | any, but a meeting's is deleted only through its meeting |
| Administrator (`group_academic_admin`) | all | yes | any, but a meeting's is deleted only through its meeting |

`security/ir.model.access.csv` gives the CRUD rows; `security/rules/facilities.xml` narrows the
teacher's write rights to `user_id = user.id` and `minute_id = False`.

The form never offers what the rules will refuse: `can_edit` (non-stored, `depends_context('uid')`)
asks the record rules themselves (`_filtered_access('write')`, once for the whole batch) and is false
for a meeting's reservation, and the form's fields are `readonly="not can_edit"`, so someone else's
reservation opens read only. `unlink` answers with a clear message instead of the rules' generic
access error: a meeting's reservation follows its meeting (change or remove the room there; the
minute removes it under `sudo()`), and anyone else's is refused (*You can only change your own
reservations*).

## Out of scope

Weekly repetition, capacity and equipment filters, prior approval, and treating holidays or
absences as occupation.

## Tests

`tests/test_space_reservation.py` (overlaps, schedule blocks, spans over several days, timezone,
archived calendars, breaks, meetings, rules, the wizard in both modes, the migrations) and
`tests/test_space_reservation_tour.py`, logged in as a teacher: reserving by date (the list follows
what is typed, the choice kept or dropped), by space (the grid, dragging, the current-time line, a
time typed in the past) and a colleague's reservation opened read only.
