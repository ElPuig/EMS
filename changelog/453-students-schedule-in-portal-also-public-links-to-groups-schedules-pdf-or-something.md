# What's new

## Public, persistent link to each group's schedule PDF:

- Every active group now has a public link (`<web.base.url>/ems/schedule/<group-name-slug>.pdf`,
  e.g. `/ems/schedule/eso1a.pdf`) that anyone can open without logging in to EMS, so the centre's
  website can link each group's timetable. The group form shows it as a link that opens the PDF in
  a new tab, with a copy button next to it (the browser only allows copying over HTTPS).
- The PDF behind the link is pre-rendered and stored (in Catalan), never generated on request.
  It is re-rendered only when something it prints changes: a schedule block of the group (created,
  edited, moved to another group, removed or archived with its teacher's calendar), the level's
  break in the schedule framework, the group's own name/tutor/reference classroom/level/shift or
  reactivation, a renamed subject/classroom/teacher it shows, or the current course.
- Changes only flag the affected groups; a cron woken up once per transaction renders them in the
  background, in batches of 10 through Odoo's own cron progress API. A bulk change (the schedule
  import, an upgrade's data reload) renders each affected group once, outside the user's request.
- An unknown slug, an archived group or a group whose first PDF isn't rendered yet returns 404.
  Every existing group is flagged on upgrade, so the first PDFs appear on the cron's first run with
  no migration.

## Public link to every group schedule of a study in one PDF:

- Every study with active groups now has a public link too (`<web.base.url>/ems/schedule/study/<acronym-slug>.pdf`,
  e.g. `/ems/schedule/study/smx.pdf`), shown on the study form with the same copy button: one PDF
  with the schedule of each of the study's active groups, by course and then name (SMX1A...SMX1D,
  then SMX2A...SMX2D), so the website needs a single link per study that follows each year's groups.
- Nothing new is rendered or stored: the groups' own stored PDFs are merged on request, so the
  study PDF picks up schedule changes as soon as each group is re-rendered, and a group added to or
  archived from the study with no trigger of its own. Groups whose first PDF isn't rendered yet are
  left out; studies sharing an acronym (a curriculum change mid-cycle) share one PDF. 404 when no
  group has a PDF yet.
- The group links stay as they are (the portal and the group form keep using them).

## Student's weekly schedule on the portal:

- The portal's Attendance card (`/my/asistencia`) now shows the student's weekly class schedule
  (subjects, classrooms, breaks and a Subject/Teacher(s) table) instead of the "under construction"
  page; Grades keeps the placeholder. On narrow screens the grid scrolls sideways.
- A Download PDF button renders the same student schedule report used in the backend, on
  request and in the portal user's language.
- A family always sees the child selected in the portal header, and a student only their own
  schedule: the routes take no student id, so nobody can request someone else's schedule.

# Internal changes

## Shared schedule grid sub-template:

- The weekly grid and Subject/Teacher(s) table were copied in the group and student schedule
  reports; both reports and the new portal page now call a single `ems.schedule_report_grid`
  QWeb sub-template.
- `tests/__init__.py` had two imports fused on one line (a syntax error that stopped the test
  package from loading); split back into two lines.
