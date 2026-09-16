[Català](../../ca/admin/attendance-status.md) | [Castellano](../../es/admin/attendance-status.md) | [English](attendance-status.md)

---

# Attendance Statuses: Managing the Passlist Options

**Required role:** Administrator

---

## What This Is

Every button a teacher can click for a student in the roll-call view (Attended, Minor Delay, Severe Delay, Miss, Justified Miss...) comes from a configurable list under **Attendance → Configuration → Sessions → Statuses**, instead of being fixed in the app's code. You can add a new one, reorder them, or retire one the centre no longer uses.

![Attendance statuses list, with category, family notification and color per status](../../assets/admin/admin-attendance-status-list.png)

---

## Managing Statuses

Each status has:

- **Name** (translatable) — shown on the roll-call button, the read-only status list on a session's History entry, and in printed attendance reports.
- **Sequence** — drag to reorder; this is the order buttons appear in on the roll-call view.
- **Category** — *Assistance* or *Absence*. Drives the "Assistance vs. Absence" breakdown shown in the attendance-by-group/student/subject reports.
- **Notify family/tutor** — if marked, a student marked with this status triggers the same family/tutor notification workflow as a Miss.
- **Color** — the text color used for this status in the printed per-session attendance report.

**Retire, don't delete:** there is no delete action from this list for a reason — a status can be referenced by years of historical attendance data. Use the standard **Archive** action instead (⚙ menu on the form, or select rows in the list and use the same menu there) — existing sessions that already used it keep showing it correctly (in the roll-call history and in reports); it just stops being offered as a new choice. Archived statuses are hidden by default; use **Filters → Archived** in the list to see them again, or to Unarchive one. The seeded "Issue" status ships pre-archived this way, since `ems.strike` (see the Strikes manual) now covers what it used to flag.

**Minor Delay vs. Severe Delay:** the centre distinguishes two levels of lateness. "Minor Delay" is `Assistance` category and does not notify the family — it never counts as an absence. "Severe Delay" is `Absence` category and notifies the family, exactly like a Miss — a student marked this way counts as absent in attendance rates and reports. A teacher chooses directly which one applies when passing the roll-call; there is no automatic escalation from repeated minor delays into a severe one. Both reset to "Attended" on the next period's line — a delay of either kind only ever applies to the single period it was marked in.

---

[← Back to Admin manuals](index.md)
