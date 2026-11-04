# Changes

## Minutes: sign-off by whoever answers for them, approval in the next meeting:
- A meeting's minute now goes through two steps. Whoever answers for it (the person in "Signed off by", or anybody above them in the chain of command) gives it the sign-off: the minute closes, its PDF is filed marked "Signed off, pending approval in the next meeting", and its agreements reach their responsible people (tasks and notices in the daily summary).
- The next meeting of the same type and scope approves it in its existing "Approval of the previous minute" block, which takes effect when that next minute is signed off: "Approved" or "Approved with changes" approves the previous minute (its final PDF says in which meeting and on which date); "Not approved" sends it back to the meeting to be corrected and signed off again, and whoever writes it is told in their daily summary with what the meeting said. A minute cannot be signed off while the previous one is waiting for that decision.
- An approval given while the previous minute was still being written applies as soon as that minute gets its sign-off.
- Each minute type says whether it is approved in the next meeting or with the sign-off; evidence records, and meetings with no next one, are approved with the sign-off, as before.
- Renamed across the screens, PDF, task and manuals: "Send for sign-off", "Give the sign-off", "Awaiting my sign-off", states "Awaiting sign-off" and "Signed off"; new filter "Signed off, to be approved".

# Internal changes

## Minute sign-off (issue #756):
- New `ems.minute` state `signed_off` (between `to_approve` and `approved`) and fields `signoff_date`, `approved_in_minute_id`; `ems.minute.type.approval_mode` (stored compute from `kind`, editable). `action_sign_off` (with `action_approve` kept as its alias), `_ems_decide_previous`, `_ems_approve_in`, `_ems_reject_in`; `CLOSED_STATES` drives the write rules, the form's read-only fields, the sign-off task and the moment agreements are announced.
- The minute submit wizard's access for the quality administrator was removed: that role alone cannot write minutes (permission audit).
