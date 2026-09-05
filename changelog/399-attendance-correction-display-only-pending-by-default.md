# What's new:

## Attendance correction requests default to showing only Pending:
`ems.attendance_correction`'s list (Employee Attendances → Correction Requests) now defaults to a **Pending** filter, matching the exact pattern already used by `ems.student.document` (`search_default_pending: 1` on `action_attendance_correction_tree`). The new search view (`views/attendance/attendance_correction/search.xml`) also exposes standalone **Accepted**/**Rejected** filters and group-by (Status/Employee), so an approver (Head of Studies/Deputy/Director/Academic Admin) can switch to any other state, or remove the default filter to see every request, in a single click — instead of always seeing the full historic list mixed in with what actually needs a decision. `action_view_corrections()` (the "Corrections" smart button on an individual `hr.attendance` record) is unaffected — it already resets the context to show all requests for that one attendance regardless of state. Teacher and Head of Studies/Deputy/Director user manuals updated (EN/CA/ES) to mention the default filter and how to switch it.

# Fixes:

## Attendance correction status shown in English regardless of UI language:
`ems.attendance_correction.state`'s selection values (Pending/Accepted/Rejected) had never been given Catalan/Spanish translations - found while adding the new search filters above, since they reuse the exact same words. The status badge on the list/form, and the new filter labels, now render correctly in `ca_ES`/`es_ES`.

# Internal changes:

## Shared test helper for forcing the admin user's language to English in tours:
`_force_admin_language_to_english` (previously a private method duplicated on one test class) extracted to `tests/common.py` as `force_admin_language_to_english()`, used by both `TestAttendanceStatusTour` and the new attendance-correction filter tour - any tour asserting on literal English text needs this, and it should no longer be re-written per file.
