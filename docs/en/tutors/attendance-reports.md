[Català](../../ca/tutors/attendance-reports.md) | [Castellano](../../es/tutors/attendance-reports.md) | [English](attendance-reports.md)

---

# Attendance Reports

**Attendance → Reports** opens the **Attendance reports** screen: a pivot table you can explore and export
yourself, plus 3 printable PDF reports (by group, by student, by subject) reachable from its header.

**Required role:** Teacher (group tutors use the same reports as any teacher)

---

## Exploring Attendance Reports

1. Navigate to **Attendance → Reports**. It opens directly on a **pivot table**, showing **only your own
   groups and subjects** by default (same scope as the PDF wizards below — being someone's tutor alone
   doesn't widen this, only actually teaching a subject in their group does).
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

On the **Attendance reports** screen, click the **⚙ (gear)** icon in the header and choose **Print attendance
report**. In the form, pick the **Report type** — by group, by student, or by subject — and the fields adapt
to your choice.

**Attendance report (by group):**
1. Pick a **Group** — the dropdown only shows the groups **you actually teach**, not every group you
   tutor: being the tutor of a group doesn't by itself grant it access here if you don't teach any subject
   in it.
2. The **Tutor** and the **From**/**To** dates fill in automatically from the group and its full session
   range.
3. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, and any
   session notes recorded for the period.

**Attendance report (by student):**
1. Pick a **Student** — the dropdown only shows students enrolled in a subject **you actually teach**, not
   every tutee: being someone's tutor doesn't by itself grant it access here if you don't teach any of
   their subjects.
2. The **Tutor** and the **From**/**To** dates fill in automatically from the student and their full
   session range.
3. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, and any
   session notes recorded for the period.

**Attendance report (by subject):**
1. Pick a **Subject** — the dropdown only shows subjects **you actually teach**, not every subject taught
   in a group you tutor.
2. The **Groups** field fills in automatically with every group where you teach that subject, and
   **Tutors** shows their tutors for reference (this is where you can actually see who tutors each group —
   not by picking the group yourself first). If you only want some of those groups in the report, remove
   the others from the **Groups** field — it stays editable.
3. The **From**/**To** dates fill in automatically to cover the full session range for your selection.
4. Click **Print**. The PDF opens with an overall assistance/absence breakdown, a per-status count, and any
   session notes recorded for the period.

**For any report type**, two controls govern the per-line detail in the PDF:
- **Detail statuses** — which statuses appear in the "Details" tables. It defaults to absence-related
  statuses only (**Miss**, **Justified Miss**) so the report stays a manageable size; add more and a warning
  appears that the report may become slow to generate or fail for large selections.
- **Include strikes** (on by default) — adds tables of the disciplinary strikes recorded during the period.

> For a broader, per-course view of a tutee's attendance across their whole record, see
> [Academic history of your students](academic-history.md) instead.

---

[← Back to Tutors manuals](index.md)
