# Fixes

## Student Google accounts store the IDALU in Employee ID:
- New student accounts are created with the IDALU in Google's Employee ID (`externalIds`, type
  `organization`), the field the centre's accounts created outside EMS already use. Until now EMS
  wrote it only to a custom `IDALU` attribute that nobody reads, so the 256 accounts EMS had created
  had no Employee ID (checked against Google's user export of 2026-10-09).
- A change of IDALU on a student with an account is queued and copied to Google, like a name
  change (suspended accounts too; a deleted or out-of-reach account leaves a chatter note).
- Existing accounts without an Employee ID are filled in once, by hand, from a production dump
  (no migration).
- The rename and the new IDALU sync share one patch helper in the Google Workspace mixin.
