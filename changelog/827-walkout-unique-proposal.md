# Fixes

## Student walkout: one proposal per group and day, also when two managers propose at once:
- The check that a group has no other live proposal (not cancelled nor rejected) for the same day ran a search and then created the record, so the delegate and the sub-delegate submitting "Propose the vote" for the same day at the same moment could both pass it and create two proposals, each emailing the group and the tutor. Odoo's transactions run in REPEATABLE READ, so neither saw the other's proposal.
- A partial unique index `ems_student_walkout_one_per_group_day` on `(group_id, walkout_date) WHERE state NOT IN ('cancelled', 'rejected')`, built in the model's `init()`, now keeps it in the database; its violation is turned into the same message as the search ("Your group already has a student walkout proposal for ...").
- Migration 18.0.0.51.0 (pre): lists in the log any group and day that already has more than one live proposal, instead of failing the upgrade; `init()` skips the index while they exist (with a warning) and builds it on the first upgrade after they are cancelled.

# Changes

## Student walkout: a cancelled proposal stays visible to both managers:
- When the sub-delegate cancelled the delegate's proposal (or the other way round), only whoever opened it kept seeing it. Now the opener and the group's delegate and sub-delegate (the same people who may manage it) keep seeing it as cancelled; the rest of the group still no longer does.
