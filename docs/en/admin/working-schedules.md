[Català](../../ca/admin/working-schedules.md) | [Castellano](../../es/admin/working-schedules.md) | [English](working-schedules.md)

---

# Teacher Working Schedules & Schedule Frameworks

Manage each teacher's weekly timetable from their own employee record, and set up the bell-schedule templates ("schedule frameworks") new teachers start from.

**Required role:** Administrator (this is currently the only role that can edit schedules — everyone else can only view their own, read-only)

---

## Concepts

- **Schedule framework**: a reusable weekly bell-schedule template (periods, breaks, coordination meetings) for a level of studies — e.g. one framework for ESO, one for BTX, one shared by the vocational-training levels. Frameworks never carry real subject assignments.
- **A teacher's schedule**: their own personal calendar, built from a framework and then filled in with their actual subjects/groups. It is never shared between two teachers.
- **Default schedule framework**: the one framework automatically used to start every new teacher's schedule.

---

## Access

- Schedule frameworks: **Configuration → Teachers → Schedule frameworks**
- Default framework setting: **Settings → Employees → "Default schedule framework"**
- A teacher's own schedule: **Employees → [open the teacher] → Schedule** tab

---

## Set Up a Schedule Framework

1. Go to **Configuration → Teachers → Schedule frameworks** and create a new one (or open an existing one).
2. Set its **Name** and, if it's specific to one level of studies, its **Level**.
3. Add its weekly periods in the attendance lines below: day, start/end time, and optionally a name. Use exact times — periods don't need to be aligned to the hour (e.g. `10:25–11:25`).
4. For breaks and coordination meetings, use the **non-teaching** field on that line (e.g. `Break`, `Coordination Meeting`) instead of leaving it blank — these are real commitments every teacher following the framework will inherit.

> A framework is a template only: it never has subjects or groups assigned to its own periods.

---

## Set the Default Schedule Framework

1. Go to **Settings → Employees**.
2. Under **Default schedule framework**, pick the framework every *new* teacher should start from.
3. Save.

This field is required — the module ships with a generic default framework so it is never empty out of the box, but you should point it at the framework that matches your centre's most common level.

---

## A New Teacher's Schedule

When you create a new employee of type **Teacher**, EMS automatically:
- creates a personal working calendar for them (never shared with anyone else),
- points it at the centre's default schedule framework.

Nothing needs to be assigned yet — open their **Schedule** tab and use **Edit** to start filling in subjects, following the "Edit a Teacher's Schedule" section below. Renaming the teacher later automatically renames their calendar to match; deleting the teacher automatically deletes their personal calendar.

---

## View a Teacher's Schedule

1. Open the teacher's employee record.
2. Go to the **Schedule** tab.

Each block shows its exact start–end time, the subject/group or the non-teaching reason, and the classroom (taken from the group's own default classroom). Periods that are still unassigned simply show no block — the framework's structure (breaks, meetings) is what tells you a slot is expected there.

---

## Edit a Teacher's Schedule

1. Open the teacher's **Schedule** tab and click **Edit**.
2. Every row is one real weekly period (its own exact time, editable via the two time fields on the left) — pick a **subject** and a **group** for it, or a **non-teaching** reason, from the dropdowns in each day's column.
3. To change a period's time: edit the start or end time field directly (moving the start keeps the period's length).
4. To remove a period entirely: use the trash icon next to its time.
5. To add a period the framework didn't have (e.g. a teacher who mixes two levels' bell schedules): click **Add period** at the bottom of the time column, set its time, and fill it in for whichever day(s) it applies to.
6. Click **Save** to apply, or **Cancel** to discard everything and leave the schedule untouched.

> Leaving a manually-added period unassigned and saving simply drops it — only real assignments are kept. If you re-open **Edit** later, the framework's own periods reappear as gaps to fill in, but a discarded manual period does not.

---

## Import a Teacher's Schedule from a File

If your centre already exports schedules from an external planning tool (XML), you can import one directly for a specific teacher instead of building it by hand:

1. Open the teacher's **Schedule** tab and click **Import**.
2. Attach the XML file.
3. If the teacher already has a schedule, you'll see a warning that it will be updated (not replaced from scratch) — subject assignments and attendance templates are kept in sync with the new file.
4. Click **Import**.

---

## Start a Teacher's Schedule From a Framework or From Another Teacher

Use this to reset a teacher onto a different framework (e.g. they now teach a different level), or to set up a **substitute** with the same schedule as the teacher they're covering for:

1. Open the teacher's **Schedule** tab and click **New**.
2. Choose either a **schedule framework** (starts blank, following that framework's periods) or **another teacher** (copies their real subjects/groups — ideal for substitutions).
3. Click **Load** — you'll see the loaded schedule in edit mode.
4. Adjust anything needed, then click **Save** to apply, or **Cancel** to discard and keep the teacher's previous schedule untouched.

> **New** replaces the whole schedule — nothing from before is kept unless it also appears in what you just loaded. Cancelling before Save leaves everything exactly as it was.

---

[← Back to main index](index.md)
