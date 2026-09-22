# Fixes

## Absence refusal confirmation claimed reopening was impossible when it actually wasn't (#501):

Refusing an absence request showed a confirmation dialog stating the request could never be
reopened, but a "Reset" button was actually reachable for the one account still entitled to use
it (`base.user_admin`, deliberately kept as a genuine Time Off Administrator). The dialogs now
say precisely that: reopening isn't available to the approver or the employee, only to a Time
Off Administrator, so in practice the employee should expect to file a new request.

## Resetting a Direction-refused absence left its Direction status stranded on "Refused" (#501):

When that Reset button was used on a request Direction (not the Head) had refused, the overall
status came back to "Pending" but Direction's own column kept showing "Refused", with nothing on
screen explaining why the request still couldn't move forward. Resetting a refused absence request
now also clears Direction's own review, so the request genuinely returns to a clean pending state.
