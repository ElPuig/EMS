# Fixes

## Roll-call used the computer's clock instead of Spanish time:
- The roll-call screen decided "today" and which slot is "current" (the one preselected) from the
  browser's own clock, so a teacher whose computer had a wrong timezone got the wrong slot and
  created the wrong session. It now uses the server's clock in the company's timezone
  (server_clock.js, synced once on load); the guard duty board's default day/shift/week too.
- create_scheduled_session() rejects a future date on the server, since the client's date can't be
  trusted.

## One timezone for the whole centre (the company's):
- ems.datetime_utils.current_tz() is always the company's timezone (read with sudo, so the public
  user of the portal and kiosks works too), no longer the acting user's or the context's.
- The web client (backend and portal) shows and reads every datetime field in the company's
  timezone instead of the browser's: the company tz is handed over in the session info (ems_tz)
  and set as luxon's default zone. The same service overwrites the browser "tz" cookie, which Odoo
  uses to give a user their timezone on first login (how users ended up in America/Lima,
  Atlantic/Canary...) and to format hr.attendance's display name.
- Every partner, employee and working schedule now keeps the company's timezone (a create/write
  mixin; only the company's own partner can change it, and everyone follows), and the tz field is
  read-only on the user, profile and employee forms. Migration 18.0.0.30.1 (and the post_init_hook
  on clean installs) aligns every existing record: users had ended up in America/Lima,
  Atlantic/Canary..., and the public user the attendance kiosk runs as had none, which is why the
  kiosk's "hasn't checked out since..." error showed UTC time.
- Every naive server-clock read in EMS (datetime.now(), date.today(), fields.Date.today(), UTC in
  Odoo) replaced with company-timezone helpers (get_local_datetime()/get_local_today()): import log
  timestamps and file names, "today" in the auto check-in, age and benefit-renewal computations,
  schedule sync default dates. LimeSurvey's survey start/expiry dates stay UTC, now explicitly,
  since that server runs in UTC.

# Internal changes

## Timezone policy documented:
- New developer doc docs/en/developers/shared/timezones.md and a CLAUDE.md rule: one timezone (the
  company's), server stays in UTC, no naive now()/today() in Python, serverNow() in JS.
