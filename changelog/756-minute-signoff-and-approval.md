# Changes

## Minutes: undo the approval to correct an approved minute:
- An approved minute can be corrected: **Actions → Undo the approval** (for whoever approves it, whoever answers for the scope that met and whoever wrote it, with their chain of command) takes it back to "To approve", editable again and with its draft sendable again to the participants. Approved again, its approval date says when the changes were approved and a new PDF is generated; the previous PDF stays attached to the minute.
- Re-approving brings the agreements' tasks in line with what the minute now says, and their responsible people are only told again about what changed.
- The email with the draft of the minute is worded more formally.

# Internal changes

## Undoing a minute's approval (issue #756):
- `ems.minute.action_reopen`, `can_reopen` / `_ems_user_may_reopen`; the state is written with sudo, since no record rule lets anybody write an approved minute. `ems.quality.action._ems_queue_notice(once=True)` skips a notice the user already had in the same words.
- The minute submit wizard's access for the quality administrator was removed: that role alone cannot write minutes (permission audit).
