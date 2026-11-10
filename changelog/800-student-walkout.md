# What's new:

## Student walkout calls from the portal (issue #800):
- The delegate or sub-delegate of a group opens a student walkout call from the portal (new "Student walkouts" card and menu entry, /my/vagues), attaching the students' union call (at least one file) and choosing the walkout day and the day the vote closes. The halves of a split group sharing that delegate vote together.
- Every student of the group with portal access gets an email and votes, logged in: whether the group supports the walkout (anonymous, only the counts are kept, cannot be changed) and whether they join it (by name, changeable until the vote closes). The portal home shows a "vote pending" banner. Students without portal access are listed in the minute but do not vote.
- The vote closes on its own (hourly cron, first hour of the close day) or earlier from the portal. Closing renders the minute PDF (centre language), emails it right away to the group's Head of Studies / Deputy Head of Studies (the academic administrators when there is none), emails the result to the group and tells the family of each joining minor (or adult sharing with the family).
- The group decides: the walkout is supported with more yes than no among the votes cast (a tie does not support it). If it does, the Head of Studies gets a quiet task "Justify the student walkout" and the call's Actions offer "Generate the justification": one full-day justification of the walkout day for the students who join, skipping (and noting) anyone already justified that day.
- New backend screen Student's Attendances > Student walkouts (list and read-only form), read within the tutor scope (the group's tutor and the chain above, Director) and by the administrators; only the Head of Studies / Deputy / Director in that scope, or an administrator, generates the justification.
- New settings block "Student Walkout Settings": the notice period in days (default 2: no call for a walkout sooner than that, and the vote must close at least that many days before it) and "Levels and courses", an editable list of the levels saying which may call a walkout and, optionally, from/to which course. Seeded once from the law (LODE art. 8): ESO from the 3rd year, BTX, CFGB, CFGM, CFGS and EFPS; PFI not.

# Changes:

## Justification reason "Labour strike" renamed "Student walkout":
- Its English name and xmlid (attendance_justification_reason_strike becomes attendance_justification_reason_walkout) change so that "strike" only means the disciplinary record (Coexistence > Strikes); the Catalan and Spanish names ("Vaga"/"Huelga") stay. A centre that had already renamed it keeps its own name.

# Internal changes:

## Student walkout models, portal and migration:
- New models ems.student_walkout and ems.student_walkout.line (one line per student; the group vote is only a counter on the call, never stored per student; concurrent votes rely on REPEATABLE READ and Odoo's retry), controller controllers/portal_student_walkout.py, report ems.report_student_walkout (added to the centre-language reports), four mail templates, activity type and cron.
- ems.level gets walkout_allowed / walkout_course_from / walkout_course_to (ems.group._ems_walkout_allowed()), res.company gets walkout_notice_days.
- Manifest 18.0.0.48.0: migrations/18.0.0.48.0/pre-migrate.py renames the reason's xmlid (and its English name while still the seeded one); post-migrate.py seeds the walkout levels, the same as post_init_hook on a new installation.
- Tests: TestStudentWalkout (16), TestPortalStudentWalkout (5), the Head of Studies tour TestStudentWalkoutTour, ACCESS_MATRIX rows; the justification tour follows the renamed reason. Developer doc: docs/en/developers/attendance/student_walkout.md.
