# Fixes

## Duplicated strikes sent a few seconds apart (double click on Send):
- The roll-call view's strike dialog had no guard while its Send request was in flight, and creating a strike takes a few seconds because every notification email is sent right away, so a second click issued the same strike twice (and emailed the student, family and tutor twice). Send is now disabled and ignores clicks until the request finishes. Existing duplicates are deliberately left as they are.
- New possible-duplicate warning: when the same teacher already issued a strike to the same student within a configurable number of minutes, both the roll-call dialog and the New strike dialog warn (with the previous strike's time and reason) and ask for confirmation before sending another one. In the roll-call, declining goes back to the strike dialog with everything typed still there.
- New setting under Settings > Strikes Settings: "Possible duplicate warning" (minutes, 1 by default, 0 disables it).
- Covered by backend tests and by the strike tours (a double click now issues one strike; a second strike for the same student asks for confirmation, in both dialogs). Teacher, admin and developer manuals updated.
