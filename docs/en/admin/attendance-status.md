[Català](../../ca/admin/attendance-status.md) | [Castellano](../../es/admin/attendance-status.md) | [English](attendance-status.md)

---

# Attendance Statuses: Managing the Passlist Options

**Required role:** Administrator

---

## What This Is

Every button a teacher can click for a student in the roll-call view (Attended, Delayed, Miss, Justified Miss...) comes from a configurable list under **Attendance → Configuration → Statuses**, instead of being fixed in the app's code. You can add a new one, reorder them, or retire one the centre no longer uses.

---

## Managing Statuses

Each status has:

- **Name** (translatable) — shown on the roll-call button, the read-only status list on a session's History entry, and in printed attendance reports.
- **Sequence** — drag to reorder; this is the order buttons appear in on the roll-call view.
- **Category** — *Assistance* or *Absence*. Drives the "Assistance vs. Absence" breakdown shown in the attendance-by-group/student/subject reports.
- **Notify family/tutor** — if marked, a student marked with this status triggers the same family/tutor notification workflow as a Miss.
- **Color** — the text color used for this status in the printed per-session attendance report.
- **Active** — untick to retire a status without deleting it. Existing sessions that already used it keep showing it correctly (in the roll-call history and in reports); it just stops being offered as a new choice.

**Retire, don't delete:** there is no delete action from this list for a reason — a status can be referenced by years of historical attendance data. Untick **Active** instead; the seeded "Issue" status ships pre-archived this way, since `ems.strike` (see the Strikes manual) now covers what it used to flag.

---

[← Back to Admin manuals](index.md)
