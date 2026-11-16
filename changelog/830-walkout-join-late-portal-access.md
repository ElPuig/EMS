# Fixes

## Student walkout: students who got portal access after the proposal could not join (#830):
- A proposal records which students of the group had portal access at that moment (`has_portal`), and that snapshot limited both the group vote and the individual joining, so a student given access afterwards (or whose user was archived then) could never say whether they join, and their absence could never be justified. Reported from production on 2026-11-16.
- The group vote keeps the electorate of the proposal (its majority is counted over it, `voter_count` unchanged), but joining is now open to every student of the call: answering on the portal already means having access. The portal home banner, the call page and the minute follow it.
- The joining email goes to every student of the call with portal access when joining opens, and a student given portal access while joining is open (portal wizard, `action_grant_access`) gets it at once if they have not answered yet.
- The portal message for a student without access at the proposal now says they cannot vote but will be able to join; families' manual (ca/es/en) and developer doc updated. Tests reproduce it (failed on the previous code).
