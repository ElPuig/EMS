Status: CURRENT as of 2026-10-22. Steps 1-4 and the tests for them are done and ship with issue #497
(branch `497-quality-phase-2`); step 5 is still open. Delete this file once it lands (the real
docs, `docs/en/developers/meetings/meeting_presence.md`, become the reference).

# Joining meeting attendance (#521) and the minutes (#497)

`ems.meeting.presence` (a session: who was convened, who passed the NFC tag) was built
independently of `ems.minute`, on purpose aligned with it. What is left to do once #497 is merged:

1. **One root menu.** *Done 2026-10-05, when main was merged into `497-quality-phase-2`.* Both branches add `views/minutes_agreements/menu.xml` with the root
   `menu_minutes`. Keep a single record: the root is named **Meetings** (`Reunions`), the minutes
   entries (*Minutes and records*, *Agreements*, ...) hang off it next to *Attendance*, and its
   `groups` is the union of both (#497: teacher + secretary; #521: Head of Studies, secretary,
   academic admin). Each entry keeps its own groups, so a teacher sees the minutes entries
   but not *Attendance*.
2. **Link a minute to its attendance.** *Done 2026-10-12, the other way round from what was first
   planned:* the minute is where the choice is made (`attendance_mode`: by hand or NFC tag), and
   saving it creates the session (`presence_id`) with the minute's start, duration, room and
   preloaded attendees, the writer as convener. See "Integration with the minutes" in
   `docs/en/developers/meetings/meeting_presence.md`.
3. **Derive the attendee lists.** *Done 2026-10-12:* filled when the session closes and when the
   minute is sent for approval (`ems.minute._ems_sync_attendance()`).
4. **One preloading implementation.** *Done 2026-10-22:* both call
   `ems.meeting.presence._ems_convened_employees()`, which joins both sets of rules (sub-departments,
   company, the group's teaching team plus its tutor) and adds the `group` scope to sessions. Originally:
   `ems.minute._ems_preload_attendees()` and
   `ems.meeting.presence._ems_scope_employees()` implement the same rules. Make the minute call the
   session's helper (or extract both into an abstract mixin) instead of keeping two copies.
5. **Quality roles.** `ems.group_quality_admin` is not among the managers of a session today: it
   implies neither teacher nor secretary, so it cannot read the courses, rooms, departments and
   workgroups a session points at (the failure class of issue #434). Add it (and #497's quality
   coordination group) together with the read ACL lines those four models need for it.
6. **Tests.** *Done for steps 2-3* (`tests/test_quality_minute.py`, and the minute tour chooses the
   NFC tag). Steps 4-5 still need theirs.

No migration is needed on the session side; `presence_id` is a new column, which the upgrade adds.
