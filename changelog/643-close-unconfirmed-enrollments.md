# What's new

## Close unconfirmed enrollments (one action per person, with preview):
- New assistant, from the ⚙ Action menu of the Enrollments list and from the Pre-inscription list header, that closes every draft or sent enrollment nobody confirmed. It resolves one action per person and shows it before applying anything.
- Applicants who were never students are deleted with everything that only existed for them (portal user, enrollments, authorizations, documents); if they already have a corporate account or a convalidation they are archived instead, and a deletion that something still references falls back to archiving.
- Applicants who had studied at the centre (turned into applicants when their new offer was sent) go back to alumni if they graduated, or withdrawal otherwise, with their exit data restored from the academic history, the Google grace period and the portal revoked.
- Students without a group are withdrawn with the withdrawal assistant's own steps (now shared through `res.partner._ems_register_exit()`); students with a group, with a confirmed enrollment for the running course or a later one, alumni, withdrawals and expelled only lose the pending enrollment.
- Enrollments with a payment transaction or an invoice are left untouched and listed for review.
- Pre-inscription gets a "Without enrollment" filter (searchable `ems_has_enrollment`), to find the GEDAC applicants who never got an offer.

# Changes

## Enrollments list without loose header buttons:
- "Send Enrollment" moved from the list header into the ⚙ Action menu, next to "Close unconfirmed enrollments".
