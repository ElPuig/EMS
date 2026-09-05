# What's new:

## Attendance correction requests default to showing only Pending:
`ems.attendance_correction`'s list (Employee Attendances → Correction Requests) now defaults to a **Pending** filter, matching the exact pattern already used by `ems.student.document` (`search_default_pending: 1` on `action_attendance_correction_tree`). The new search view (`views/attendance/attendance_correction/search.xml`) also exposes standalone **Accepted**/**Rejected** filters and group-by (Status/Employee), so an approver (Head of Studies/Deputy/Director/Academic Admin) can switch to any other state, or remove the default filter to see every request, in a single click — instead of always seeing the full historic list mixed in with what actually needs a decision. `action_view_corrections()` (the "Corrections" smart button on an individual `hr.attendance` record) is unaffected — it already resets the context to show all requests for that one attendance regardless of state. Teacher and Head of Studies/Deputy/Director user manuals updated (EN/CA/ES) to mention the default filter and how to switch it.

# Fixes:

## Attendance correction status shown in English regardless of UI language:
`ems.attendance_correction.state`'s selection values (Pending/Accepted/Rejected) had never been given Catalan/Spanish translations - found while adding the new search filters above, since they reuse the exact same words. The status badge on the list/form, and the new filter labels, now render correctly in `ca_ES`/`es_ES`.

# Internal changes:

## New attendance-correction filter tour reuses the existing shared language-forcing test helper:
The new attendance-correction filter tour, and `TestAttendanceStatusTour`, both call the already-established `force_user_language_to_english()` (`tests/common.py`) to force the admin login to `en_US` before asserting on literal English text - no new helper was needed, since branch `400-communications-some-fixes-needed`, merged around the same time, already carries this exact helper and it's the codebase-wide convention used by every other tour test.
