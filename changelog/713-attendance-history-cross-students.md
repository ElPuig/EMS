# Fixes

## Attendance history shows students removed from the roll-call as not required to attend:
- In the History form of a session, a student removed from the roll-call (the cross in the roll-call screen) was listed greyed out but still showing their kept status (usually "Attended"), mixed in alphabetically with the rest, so it looked as if they had attended.
- They are now listed last, greyed out and struck through, with "Not required to attend" instead of the status radio, the same way the roll-call screen shows them. The status itself is kept untouched, so restoring the student brings it back.
- Checked that these lines never count towards any absence percentage: the attendance reports, the printed report and the year record already ignore them (issue #628).
