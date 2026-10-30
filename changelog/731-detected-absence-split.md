# Fixes

## Detected absences no longer discarded by an attendance outside their hours (issue #731):
- An attendance recorded afterwards (guard duty board, Head of Studies, accepted correction) used to re-run the detection with the day's first check-in only: any check-in during the first period discarded the whole detected absence, even when the reviewer had already narrowed it to the hours really missed and asked the teacher for it (real case: absence 14:00-16:06 narrowed to 15:00-16:06 and prepared for the teacher, then the 14:00-15:00 attendance was recorded and the absence was discarded).
- Now only the detected absences the attendance overlaps are reviewed, and they keep exactly what no attendance covers: shortened at either end, split in two when the attendance falls in the middle, discarded only when nothing is left. The detection's rule is kept: being at the centre for part of a period counts as being there (a gap without a whole period of the teacher's schedule is no absence). A check-out change also triggers the review now.
- A split part keeps the stage of the review (state, absence type, reminders), its followers and a chatter note saying where it comes from; only a part still to review gets its own review task.
- Migration 18.0.0.42.1 reopens the detected absences discarded that way (still active, unlike a reviewer's discard), back at the stage they had reached, with the teacher's reminders counting from the migration day. In production this reopens one entry.

# What's new

## Correct the check-in of part of a detected absence (issue #731):
- "Correct check-in" on the detected absence's form now opens a dialog with From/To, prefilled with the whole absence. Narrowing it records the attendance of those hours only, and the rest stays as a detected absence to review (split in two if the corrected hours fall in the middle), so the reviewer can then ask the teacher to justify the rest. The list's bulk action still corrects whole entries.
- Head of Studies manual (ca/es/en, with a screenshot of the new dialog) and developer doc updated.

# Internal changes

## Detected absence dialogs share their closing logic (issue #731):
- The "Create absence" and "Correct check-in" dialogs close through one shared helper (reload plus the notice of what was skipped), and the schedule periods read by the detection and by the new review come from one shared method.
