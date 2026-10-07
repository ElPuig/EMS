# Guard room display: the absences table on a TV

**Status:** not started, current as of 2026-10-07. Tracked in issue #591. Written right after the guard duty board's
absence management (issues #539, #571, #581, branch `539-absence-guard-management`) and builds on
it: re-check the board's payload (`ems.course.get_guard_duty_board_data`) before starting, in case
it changed since.

## Goal

A TV in the guard room permanently shows the **current** absences table: who is missing, which
classes need covering, which guard has been sent where, and what the families were told - with no
one touching it. It refreshes on its own (about every 30 seconds) and a band at the bottom shows
what changed recently. Visual only: no sound. Nobody can hover or click on a TV, so everything the
interactive board hides behind a tooltip or a popover has to be visible as it is.

## What already exists to reuse

- **The data:** `ems.course.get_guard_duty_board_data(weekday, shift, level_ids, day)` already
  returns every row (absence, group, subject, room, guard sent and its colour, struck-out reason,
  timetable change communicated) and the guard column. The display only reads; it never needs the
  management parts (`can_manage`, actions, candidates).
- **A kiosk without a login:** the meeting presence kiosk (`/ems/presence/<access_token>`, see
  `docs/en/developers/meetings/meeting_presence.md`) is a public frontend page whose only credential
  is a token in its URL, with its own language setting. The same pattern fits a screen nobody logs
  into: a company-level token and a stable link (`/ems/guard-room/<token>`), regenerable by an
  administrator if it leaks.
- **"Now" in the company's timezone:** `ems.datetime_utils` server-side (never the TV's clock, see
  `docs/en/developers/shared/timezones.md`). The board's own default day/shift logic
  (`getDefaultDayAndShift`, 15:00 shift change) applies, but driven by the server.

## Proposed design

1. **Route and access.** `GET /ems/guard-room/<token>` (auth `public`), checked against a new
   `res.company.guard_room_token` (+ a "Regenerate" button and the copyable link in Settings, admin
   only). The page calls a JSON route with the same token that returns the payload for **today and
   the current shift**, resolved on the server - the TV never chooses a date. Reads with `sudo()`
   limited to exactly what the board already exposes (the fact of an absence, never its type or
   reason - same confidentiality rule as the board).
2. **Layout for a TV.** Full screen, no Odoo chrome, large fonts readable from across the room,
   high contrast, landscape. Title with the date, shift and the time of the last refresh (so a
   frozen screen is obvious). The absences table as the main block; the guard column with each
   guard's colour; struck-out lines keep their colour and show their reason **as text on the line**
   ("Coberta per X", "Entren a les 10:00", "Co-docència"), not behind an icon.
3. **Refresh.** Poll every 30 s (a plain `setInterval` on the JSON route; the bus is not needed for
   this rate). Switch shift/day by itself as time passes. If a refresh fails (network, server
   restart), keep the last data and show a visible "no connection since HH:MM" badge instead of a
   blank screen. Keep the screen awake with the Screen Wake Lock API where available.
4. **Changes band ("what's new").** Each refresh is compared with the previous payload and every
   difference becomes a short line at the bottom, with its time: a new absence, a guard sent or
   released, a timetable change communicated. Lines stay for a while (e.g. 15-30 minutes) and the
   newest is highlighted for a few seconds; nothing blinks permanently. Kept client-side (no new
   model) unless the developer wants it to survive a TV restart, in which case it can be rebuilt
   from the records' `create_date`/`write_date`.
5. **Language.** A setting like the presence kiosk's (`kiosk_lang`), Catalan by default.

## Open questions (ask the developer before implementing)

- One screen for the whole centre, or one per level/building (the board's level filter as a URL
  parameter)?
- Morning and afternoon on the same screen at shift change, or strictly the current shift?
- Should the band also show what is **about to** need covering (next period still uncovered), as
  a reminder for whoever is on guard?
- How long should a change stay in the band, and is the order newest-first?
- Should the guard column show who is free right now (on guard and not yet sent anywhere)?

## Testing

- Backend: the JSON route refuses a wrong token, returns today's current shift only, and exposes
  nothing beyond the board's payload.
- Tour: open the display URL, check the table and the band render, simulate a change between two
  refreshes (a guard assigned by another user) and check it appears in the band.
- A real check on the guard room TV (resolution, distance) before closing.
