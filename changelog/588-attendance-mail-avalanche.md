# Fixes:

## Tutors flooded with one attendance report email per roll-call click (#588):

- Since the per-tutor report (#527, v18.0.0.32.0), an issue recorded after the tutor's chosen
  moment had passed (their working day ended while their students still had class, or a
  roll-call for a past day) queued a report job due now. A roll-call saves each student's status
  in its own request, so each job ran before the next click could join it: one email per student
  (in production, 71 for one tutor and 43 for another on 2026-10-06).
- `hr.employee._ems_attendance_report_eta()` is now always after now: once that day's moment has
  passed, the issue waits for the tutor's next moment (same lookup as `teacher_start`/`fixed_time`,
  with the centre's day end and the company default time as fallbacks), so every late issue joins
  one pending report. This is what the tutors' manual already promised ("those issues arrive in
  the next report").
- Checked against a copy of production: the bursts above would each have been a single report on
  the next day.
