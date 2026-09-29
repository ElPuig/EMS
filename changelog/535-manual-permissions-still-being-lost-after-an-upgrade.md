# Internal changes

## Security group changes are logged (hand-granted permission losses become traceable):
- Every grant or revocation of a security group now writes one line to the
server log (not the database): which user, which groups were added or
removed, who did it (uid 1 = code running as superuser) and which EMS
function asked for it. Covers changes made from the user's side (Settings >
Users, role/job sync) and from the group's side.
- Motivation (issue #535): a Secretary group granted by hand kept
disappearing. Investigation with production dumps showed the last proven loss
was the manual queue_job repair upgrade of 2026-09-26 08:13 UTC, which still
ran v18.0.0.28.0 code (the one that wiped hand-granted role/job groups, fixed
in v18.0.0.29.0); reproducing the v18.0.0.30.0 -> v18.0.0.30.1 upgrade on a
production copy did not remove it. The log settles the next occurrence.
