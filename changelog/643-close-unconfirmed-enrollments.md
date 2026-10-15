# What's new

## Close unconfirmed enrollments (one action per person, with preview):
- New assistant, from the Enrollments and Pre-inscription lists, that closes every draft or sent enrollment nobody confirmed. It resolves one action per person and shows it before applying anything.
- The preview starts with a summary (people, enrollments, and how many people get each action and what it means); applying locks the screen with a message while it runs, and ends with the result and a CSV log of what happened to each person, downloaded automatically.
- Applicants who were never students are deleted with everything that only existed for them (portal user, enrollments, authorizations, documents); if they already have a corporate account or a convalidation they are archived instead, and a deletion that something still references falls back to archiving.
- Applicants who had studied at the centre (turned into applicants when their new offer was sent) go back to alumni if they graduated, or withdrawal otherwise, with their exit data restored from the academic history, the Google grace period and the portal revoked.
- Students without a group are withdrawn with the withdrawal assistant's own steps (now shared through `res.partner._ems_register_exit()`); students with a group, with a confirmed enrollment for the running course or a later one, alumni, withdrawals and expelled only lose the pending enrollment.
- Enrollments with a payment transaction or an invoice are left untouched and listed for review.
- Pre-inscription gets a "Without enrollment" filter (searchable `ems_has_enrollment`), to find the GEDAC applicants who never got an offer.

# Changes

## "Actions" dropdown on lists:
- The lists with several header buttons (Enrollments, Pre-inscription, Enrollment proposals, Contact data requests) now group them in one "Actions" dropdown, like the forms already do, instead of a row of loose buttons. Opt-in per list (`o_ems_header_actions` class) or per action context (`ems_header_actions`), so native lists are untouched.
