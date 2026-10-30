# Fixes:

## Detected absences: the reviewer can write to the teacher (issue #698):

- A detected absence (`ems.absence_pending`) had no way to reach the teacher: its followers were only whoever entered it and the reviewers (through their review activity), so a "Send message" in its chatter went to nobody but them, and the teacher, with read access only, could not answer from the chatter either.
- The teacher now follows the entry as soon as they are asked to act on it (Request justification, or Create absence), in `_ems_ask_teacher()` via `_ems_follow_teacher()` (one `message_subscribe` per teacher). Never before: an entry still To review stays unknown to them (issue #707), and Correct check-in / Discard, which nobody is told about, leave them out. Once following, they stay.
- `_mail_post_access = 'read'` on the model, so the teacher can answer on the entries they can read (their own, never one To review) without gaining any write access. Reminders and review notes are notes, so followers get nothing extra.
- The upgrade subscribes the teacher of every entry already waiting for them (Justification requested / Absence prepared), `_ems_follow_asked_teachers()`.
- Tests: following only once asked, never for corrected/discarded entries, the reviewer's message reaches the teacher and the answer the reviewer, no posting on an entry still To review, the migration helper; the teacher's tour now answers from the chatter. Head of Studies and teacher manuals (ca/es/en) and the developer doc explain it.
