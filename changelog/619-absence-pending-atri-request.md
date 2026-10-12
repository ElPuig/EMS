# What's new:

## Absences: an ATRI absence waits for the employee to confirm it is requested in ATRI (issue #619):
- Once the Head has validated an ATRI absence, it no longer goes straight to Direction: it always
  stops at a new status, "Pending ATRI confirmation", until the employee confirms from the
  request ("I confirm it is requested in ATRI") that they have filed it on the Generalitat's
  portal. Nothing at filing time lets them skip it; whoever already requested it confirms
  straight away.
- The Head validates first on purpose, since ATRI is often picked for what is not and the other
  way round. The status and the notice on the request are worded as a confirmation: they do not
  say the absence is missing in ATRI.
- While unconfirmed, the employee has an activity and a notice with the link to the portal, and
  gets the same reminders as for a missing supporting document: daily once the absence is over,
  with a single report to their Head a few days later (same two settings).
- Direction can send an ATRI absence it is reviewing back to that status with "Not in ATRI",
  giving the reason, which the employee receives and sees on the request.
- Undo covers the new step with the existing rules. New filter "My pending ATRI confirmations".
- No migration: ATRI requests already validated by their Head stay where they are.

# Fixes:

## Absences: the "Reason for the refusal" label of the request form was not translated:
- The label of the red notice added with the refusal reason had no Catalan or Spanish entry.
