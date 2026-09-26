# Guard mode: restrict what `write_guard_session_line` can write

**Status: not started (written 2026-09-24).** Found during the role-permission audit that
followed issue #500. Re-check `models/attendance/attendance_session.py` before acting on it.

## Problem

`ems.attendance_session_header.write_guard_session_line(line_id, values)` writes with `sudo()`
on **any** `ems.attendance_session_line`, with **any** values, for any user in
`ems.group_teacher`. Guard mode legitimately needs to write lines of sessions the user doesn't
own (the teacher covering a colleague's class), which is why it uses `sudo()`, but nothing
limits it to that case:

- no check that the line's session is on the date being guarded (a past course's line works too);
- no check that the session isn't the user's own or is one `get_guard_sessions()` would return;
- no field whitelist: `student_id`, `attendance_session_id` or any other field can be changed.

This is an over-permission, not a lockout: it doesn't break anything today, but any teacher can
rewrite any attendance record in the centre through a crafted RPC call.

## Proposed fix

1. Whitelist the fields the guard view actually writes (`status_id`, `notes`, and whatever else
   `attendance_session_view.js` sends in guard mode) and raise `AccessError` on anything else.
2. Only allow lines whose session is dated today (or the date the guard view is showing, passed
   explicitly) and would be listed by `get_guard_sessions()` for this user.
3. Tests: a teacher can write status/notes on a colleague's line of today; cannot write another
   field; cannot write a line from another date.

## To decide

- Whether guard mode should be allowed on past dates at all (e.g. filling in a missed guard the
  next morning). If yes, bound it (same week? same day only?).
