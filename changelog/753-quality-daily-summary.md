# What's new

## Quality reaches the staff through the daily summary (agreements and minutes):
- Each responsible person of an agreement (named, or holding its responsible post) gets a "Carry out the agreement" task due on its deadline (today without one); it moves with the deadline, is marked done when the agreement is closed and disappears for whoever stops being responsible.
- When the deadline is later than today they also get a notice in their next daily summary, so they know about the agreement before the task is due.
- Each follow-up entry added by hand is a notice for the responsible people (except its writer) with who wrote it, when, what happened, and the agreement's meeting, scope, responsible people, deadline and state. It is still kept in the agreement's history, as an internal note that emails nobody.
- Whoever is to approve a minute (the person named, or the holders of the approving post) gets an "Approve the minute" task while it waits for approval; it is done when approved and removed if the minute goes back or another approver is named.
- An agreement taken in a meeting is only announced once its minute is approved (tasks and notices); an agreement agreed and done in the same meeting arrives as a notice with nothing left to do, and the follow-up a minute writes when reviewing an agreement arrives with its final wording.

# Changes

## The people involved in an agreement are no longer notified:
- They stop following the agreement and get no notice of its progress: the minute already tells them what was agreed. They can still read it and its follow-up. The upgrade unsubscribes the ones who are only involved (not the responsible people, nor whoever created it).
- A follow-up entry no longer sends an immediate email to the agreement's followers.

# Internal changes

## Quality notifications (issue #753):
- New activity types `ems.mail_activity_quality_agreement` and `ems.mail_activity_minute_approval`, scheduled quietly (`mail_activity_quick_update`); notices through `ems.info_notice` with the new QWeb template `ems.quality_agreement_notice`.
- `ems.quality.action._ems_sync_tasks()`/`_ems_responsible_users()`/`_ems_is_announced()`, `ems.minute._ems_sync_approval_task()`/`_ems_announce_agreements()`; follow-ups written by a minute carry the `ems_quality_minute_entry` context so they wait for its approval.
- Migration `18.0.0.46.0/post-migrate.py` unsubscribes the people only involved. No task is created for agreements that existed before the upgrade until their responsible people or deadline change.
