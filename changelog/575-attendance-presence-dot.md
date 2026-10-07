# Fixes:

## Presence dot: grey on the employee's form while green on the Teachers kanban:
- For a teacher or a tutor, a colleague who had checked in showed as present (green) on the
  Teachers kanban but as "Out of working hours" (grey) on their form. The presence state reads the
  last check-in, a field restricted to HR and attendance officers, and it was computed with the
  viewer's rights, so it came back empty depending on how the screen loaded it.
- The presence state and icon are now computed as superuser: the dot is the same on the card and
  on the form, for everyone. Nothing new is exposed (present / absent / on leave / out of working
  hours was already shown).
- Tests check every colour (present, absent, out of working hours, on leave): the state must be
  identical read as the system, a teacher and a tutor, and a tour as a plain teacher checks the
  kanban and the form show the identical icon for one colleague per colour (both fail without the
  fix).
