# Fixes

## Roll-call: a replaced schedule slot no longer shows up again as planned (no duplicate sessions):

- When a schedule line that already had sessions changed its classroom, the sync archived it and created a copy with the same template, weekday and hours, valid from the start of the course. On days already taken with the original line, the pass-list selector offered the copy again as "Planned (no session)", so the same class appeared twice, and picking it created a second session of the same class that day (the `UNIQUE(date, schedule)` constraint can't tell the copy from the original). That would count the class twice in every student's attendance and absence rate, and could duplicate family notifications.
- The planned slots (normal and guard mode, shared `_read_planned`) now leave out any line whose class already has a session that day: same template, overlapping hours, on any line, archived or not (`_taken_time_slots` + `_is_slot_taken`, one search per day).
- New `@api.constrains` on `ems.attendance_session_header` rejects, on every creation path (not only `create_scheduled_session`), a session overlapping another one of the same template and date, reusing the existing "session already exists" message. Consecutive hours of the same template (continuations) are still allowed.
- Planned slots are now labelled with the line's `display_name`, so the weekday is translated like the sessions' (it showed "Thursday" next to "Dijous", which looked like a language problem).
- No data fix needed: there are no duplicate sessions in the database. Measured cold on the dev DB's busiest day (135 sessions): guard mode 15 → 36 ms, normal mode 27 → 34 ms.
