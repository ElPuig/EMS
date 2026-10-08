# Fixes

## Guard duty board no longer proposes timetable changes whose time has passed:
- On the board's own day, a late entry, early leave, longer break or "no classes" option is only offered while its time is still to come (e.g. "Could start at 09:00" disappears at 09:00; a later option such as 10:00 stays). The dashed row tag and the proposals box follow the same rule, and a side with nothing left shows no proposal.
- A notice already sent whose change has already started is considered settled: no correction is proposed for it, since it would reach the families too late. A correction back to the usual timetable is only offered before the group's first lesson.
- The server re-checks it: proposing an option that went past while the board stayed open is refused, asking to reload. Future days are unaffected.
