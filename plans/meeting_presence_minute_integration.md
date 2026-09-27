Status: CURRENT as of 2026-09-26 - written when issue #521 (meeting attendance with the NFC tag)
was implemented, before the quality work's minutes (issue #497, branch `497-quality-phase-2`)
were merged. Re-verify against the merged code before starting: `ems.minute`'s fields and the
`views/minutes_agreements/` folder may have moved. Delete this file once the integration lands
(the real docs, `docs/en/developers/meetings/meeting_presence.md`, become the reference).

# Joining meeting attendance (#521) and the minutes (#497)

`ems.meeting.presence` (a session: who was convened, who passed the NFC tag) was built
independently of `ems.minute`, on purpose aligned with it. What is left to do once #497 is merged:

1. **One root menu.** Both branches add `views/minutes_agreements/menu.xml` with the root
   `menu_minutes`. Keep a single record: the root is named **Meetings** (`Reunions`), the minutes
   entries (*Minutes and records*, *Agreements*, ...) hang off it next to *Attendance*, and its
   `groups` is the union of both (#497: teacher + secretary; #521: Head of Studies, secretary,
   academic admin). Each entry keeps its own groups, so a teacher sees *Minutes and agreements*
   but not *Attendance*.
2. **Link a minute to its attendance.** Add `presence_id` (`Many2one → ems.meeting.presence`,
   `copy=False`) on `ems.minute`, and a form button *Attendance control* that creates the session
   from the minute: name/room from the minute, the minute's `date` + `time` as the session's start
   (`date`, with a `duration` - the session has a start and an end, and the kiosk only takes tags
   between them), and the scope mapped from the minute type's
   `scope_kind` (`department` → `department`, `workgroup` → `workgroup`, `centre` → `all_teachers`,
   `teaching_team` and `generic` → `manual`, loading `_ems_teaching_team_ids()`).
3. **Derive the attendee lists.** `attendee_ids` are the lines `present`, `absentee_ids` the lines
   `absent` and `justified` (the latter with `absence_notes`, which also delivers the "justified
   flag" the phase 2 design describes). Simplest: fill them when the minute is sent for approval, so
   a minute without a session keeps working exactly as it does.
4. **One preloading implementation.** `ems.minute._ems_preload_attendees()` and
   `ems.meeting.presence._ems_scope_employees()` implement the same rules. Make the minute call the
   session's helper (or extract both into an abstract mixin) instead of keeping two copies.
5. **Quality roles.** `ems.group_quality_admin` is not among the managers of a session today: it
   implies neither teacher nor secretary, so it cannot read the courses, rooms, departments and
   workgroups a session points at (the failure class of issue #434). Add it (and #497's quality
   coordination group) together with the read ACL lines those four models need for it.
6. **Tests.** A minute created from a session: attendees/absentees derived, a second call reusing
   the same session, and the menu merge (the secretary smoke tour covers it).

No migration is needed on the session side; `presence_id` is a new column, which the upgrade adds.
