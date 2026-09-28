# Fixes

## Head of Studies, Deputy, Director, TAC and Department Chiefs can save a teacher's schedule again (definitive fix):
- Saving a teacher's Schedule tab failed with an access error on "ems.teaching" whenever a subject or group was dropped from the grid (Head of Studies/Deputy/Director/TAC), and on every save for Department Chiefs (who couldn't write the teacher's own teaching list). The two earlier fixes had granted Head of Studies the one right on ems.teaching that failed at the time, but the save also deletes teaching rows, writes the employee's teaching list and can clear a group's tutor.
- Root cause fixed instead of adding rights one by one: ems.teaching is derived from the calendar, so the calendar write (done with the user's own rights) is now the only authorization check, and the derived teaching sync runs as superuser. The sync methods for teaching assignments and attendance templates became private, so they can't be called over RPC. The ACL for direct edits on the "Subject assignation" screen is unchanged.
- New regression coverage that the earlier fixes lacked: a backend test saving real schedules (add, move to another group, drop a tutorship, clear) as Department Chief, Head of Studies, Director and TAC, plus a browser tour where a Department Chief removes a class and saves (every existing schedule tour logged in as admin).

# Internal changes

## Schedule sync methods are no longer callable over RPC:
- The attendance-template sync entry points (_sync_from_schedule, _sync_from_schedule_batch, _regenerate_all_from_calendars) are now private, like the teaching one. Any user who could read attendance templates (every teacher) could previously call the centre-wide regeneration directly over JSON-RPC: it archives or deletes and rebuilds every teacher's templates and refills their student rosters. A test checks all four methods with Odoo's own remote-call guard.
