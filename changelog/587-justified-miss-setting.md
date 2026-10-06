# What's new:

## Setting to allow or forbid marking a Justified Miss in the roll-call (issue #587):
- New company setting "Justify absences when taking the roll-call" (Settings, EMS Management,
  "Student's Attendance Settings" block), off by default on every installation, upgrades
  included: only the student's tutor justifies an absence, by registering a justification.
- With it off, the roll-call keeps the Justified Miss column visible (same look for justified
  and non-justified rows) but its buttons are disabled, with a tooltip explaining that only the
  tutor can justify an absence; the server rejects the status when it is picked by hand
  (ValidationError on ems.attendance_session_line, Guard mode included), while justifications
  and previsions keep setting it as before.
- Lines already marked by hand keep their status when the setting is turned off.
- New computed field ems.attendance_status.roll_call_selectable carries the decision to the
  roll-call widget. Manuals updated for admins (attendance statuses), teachers (roll-call) and
  tutors (justifications), plus the developer docs.
