[Català](../../ca/secretary/attendance-reports.md) | [Castellano](../../es/secretary/attendance-reports.md) | [English](attendance-reports.md)

---

# Attendance Reports

**Attendance → Reports** opens the **Attendance reports** screen: a pivot table you can explore and export
yourself, plus 3 printable PDF reports (by group, by student, by subject) reachable from its header.

**Required role:** Secretariat (read-only)

---

## Exploring Attendance Reports

1. Navigate to **Attendance → Reports**. It opens directly on a **pivot table**, showing the **whole
   centre** by default.
2. The table groups by **subject, then student**. Click the **Expand all** icon (top-right, next to Flip
   axis) twice: once to unfold the subjects, once more to unfold each subject's students. The main number
   is the **% of absences per student** — **Count** (number of sessions counted) and **Strike count** are
   shown alongside it, so you can tell whether a 33% comes from 3 sessions or from 30, and whether it comes
   with disciplinary strikes attached.
3. Use the search bar to filter further (by student, group, subject or status), and **Group By** to change
   how the table is folded.
4. Use the **spreadsheet/download icon** in the header to export the current pivot to Excel.
5. Switch to the **graph** view (top-right icons) for a visual breakdown — by default it shows the
   **% of absence per subject**, so you can spot which subjects have the highest absenteeism at a glance.
   The graph shows one measure at a time — use the **Measures** dropdown in its header to switch to
   **Strike count** if you want to see disciplinary strikes per subject instead.

---

## Printing a PDF Report

On the **Attendance reports** screen, click the **⚙ (gear)** icon in the header and choose one of the 3
reports.

**Attendance report (by group):**
1. Pick a **Group**.
2. The **Tutor** and the **From**/**To** dates fill in automatically from the group and its full session
   range.
3. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, and any
   session notes recorded for the period.

**Attendance report (by student):**
1. Pick a **Student**.
2. The **Tutor** and the **From**/**To** dates fill in automatically from the student and their full
   session range.
3. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, and any
   session notes recorded for the period.

**Attendance report (by subject):**
1. Pick a **Subject**.
2. The **Groups** field fills in automatically with every group that teaches the subject, and **Tutors**
   shows their tutors for reference. Remove any groups you don't want in the report — **Groups** stays
   editable.
3. The **From**/**To** dates fill in automatically to cover the full session range for your selection.
4. **Detail statuses** controls which statuses appear in each student's per-session "Details" table in the
   PDF — it defaults to absence-related statuses only (**Miss**, **Justified Miss**), so the report stays a
   manageable size. Add more statuses if you need them; picking anything beyond the default shows a warning
   that the report may become slow to generate or fail outright for large subject/group combinations.
   **Include strikes** (on by default) adds a per-student table of disciplinary strikes recorded during the
   period.
5. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, any
   session notes recorded for the period, and — per student — the Details/Strikes tables described above.

---

[← Back to Secretariat manuals](index.md)
