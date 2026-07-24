[Català](../../ca/teachers/attendance-reports.md) | [Castellano](../../es/teachers/attendance-reports.md) | [English](attendance-reports.md)

---

# Attendance Reports

EMS offers 3 printable PDF attendance reports — by group, by student and by subject — plus an
**Attendance analysis** screen to explore the data yourself and export it to Excel.

**Required role:** Teacher

---

## Printing a PDF Report

1. Navigate to **Attendance → Reports** and choose **Attendance by group**, **Attendance by student** or
   **Attendance by subject**.
2. Pick a **Level**, then a **Study**, then a **Group** — each selection filters the next one. The
   dropdowns only show the groups and subjects **you actually teach**; if a group or subject you expect is
   missing, check that you're assigned to it in your teaching schedule.
3. For the by-student and by-subject reports, also pick the **Student**/**Subject** — again limited to
   what's actually enrolled/taught in the group you picked.
4. The **From**/**To** dates are pre-filled with the full range of sessions available for your selection;
   narrow them down if you only want a specific period.
5. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, and any
   session notes recorded for the period.

---

## Attendance Analysis (Explore and Export)

For a more flexible view than the 3 fixed PDF layouts:

1. Navigate to **Attendance → Reports → Attendance analysis**.
2. The list shows every attendance line you have access to. Use the search bar to filter by student,
   group, subject or status, and **Group By** to fold the list by any of those.
3. Switch to the **pivot** view (top-right icons) to cross two dimensions at once — e.g. student rows
   against status columns — and use the **spreadsheet/download icon** to export the current pivot to Excel.
4. Switch to the **graph** view for a quick visual breakdown.

> Unlike the 3 PDF wizards, the analysis screen isn't scoped to only the groups/subjects you teach — it
> shows whatever `ems.attendance_session_line` data you have read access to, same as other teacher-facing
> attendance screens.

---

[← Back to Teachers manuals](index.md)
