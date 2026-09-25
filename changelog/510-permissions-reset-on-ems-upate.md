# Fixes

## Hand-granted permissions no longer wiped by EMS upgrades or role changes:
- A permission granted directly in Settings > Users on a group that EMS also manages through roles/job positions (e.g. Secretary access for a teacher who isn't the Secretary's Area Manager) was removed on every EMS upgrade: reloading data/custom/hr.department.csv rewrote each department's parent_id/is_top_level, re-ran the heads cascade, and hr.employee._sync_security_groups() reconciled the user's whole managed-group list against their roles/job, dropping anything not backed by one. It also happened on any unrelated role change (becoming a tutor, a department reassignment...).
- _sync_security_groups() now only grants what the current roles/job carry and revokes only groups a role/job stopped granting in that change (previous state captured in hr.employee.write()/ems.role.write()). A hand-granted group that a role also grants still goes with that role (documented limitation).
- hr.department.write() only re-runs the heads cascade when one of its fields actually changes value, so an upgrade's no-op CSV rewrite has no side effects.
- The three onchange calls to _sync_security_groups() were removed: they never did anything (the NewId record never matched the lookup).

## Departed teachers kept the Tutor group:
- _sync_security_groups() looked employees up with a plain search(), skipping archived ones, so a teacher whose tutorship was cleared after being archived lost role_tutor but kept the Tutor group. Archived employees are now synced too, and a post-migrate script (18.0.0.29.0) revokes, for archived employees only, any role/job-managed group their roles/job neither grant nor imply.

## Classroom names reverted to their CSV values on every EMS upgrade:
- data/custom/ems.space.csv was resynced on every upgrade (noupdate=False), so a classroom renamed or repurposed through the app went back to its file values. ems.space is now "living" data like ems.group/ems.planning: the CSV only seeds it, and res.company._ems_freeze_living_custom_data() freezes it afterwards.
- A 18.0.0.29.0 pre-migrate freezes the existing classroom xmlids before that upgrade's data reload, so the upgrade shipping this fix doesn't revert them one last time. Classrooms already reverted by earlier upgrades must be renamed again by hand.
- The audit of the remaining data/custom models (always-sync vs. freeze-after-seed) is planned in plans/data_loading_rearchitecture.md.
