[Català](../../ca/admin/working-schedules.md) | [Castellano](../../es/admin/working-schedules.md) | [English](working-schedules.md)

---

# Teacher Working Schedules & Schedule Frameworks

Manage each teacher's weekly timetable from their own employee record, and set up the bell-schedule templates ("schedule frameworks") new teachers start from.

**Required role:** Department Chief or above (Department Chief, Head of Studies, Director, Administrator) can edit schedules and use the import wizard; every other role can only view their own schedule, read-only, but everyone can export a schedule to PDF.

---

## Concepts

- **Schedule framework**: a reusable weekly bell-schedule template (periods, breaks, coordination meetings) for a level of studies — e.g. one framework for ESO, one for BTX, one shared by the vocational-training levels. Frameworks never carry real subject assignments.
- **A teacher's schedule**: their own personal calendar, built from a framework and then filled in with their actual subjects/groups. It is never shared between two teachers.
- **Default schedule framework**: the one framework automatically used to start every new teacher's schedule.
- **Reinforcement group**: a class group that mixes students from different regular groups (and even different studies) for a specific reinforcement class — it has no tutor or delegate, but still appears in a teacher's schedule like any other group. See "Reinforcement Groups" below.

---

## Access

- Schedule frameworks: **Configuration → Teachers → Schedule frameworks**
- Default framework setting: **Settings → Employees → "Default schedule framework"**
- A teacher's own schedule: **Employees → [open the teacher] → Schedule** tab
- Batch import from a file: **Configuration → Teachers → Working schedules** → ⚙️ (cog) menu → **Import: planner data**

---

## Set Up a Schedule Framework

1. Go to **Configuration → Teachers → Schedule frameworks** and create a new one (or open an existing one).
2. Set its **Name** and, if it's specific to one level of studies, its **Level**.
3. Add its weekly periods in the attendance lines below: day, start/end time, and optionally a name. Use exact times — periods don't need to be aligned to the hour (e.g. `10:25–11:25`).
4. For breaks and coordination meetings, use the **non-teaching** field on that line (e.g. `Break`, `Coordination Meeting`) instead of leaving it blank — these are real commitments every teacher following the framework will inherit.

> A framework is a template only: it never has subjects or groups assigned to its own periods.

---

## Co-teaching

If two teachers genuinely teach the same class together (same subject, same group, same room, same hour), EMS treats it as a **single** shared class rather than two independent ones: both teachers are listed as holders of that period, and there is only **one** attendance session for it — either teacher can mark it, and both see the same result.

This is detected automatically, whether the schedule was built by hand or imported:
- **Editing a schedule by hand**: if you assign a teacher to a period that exactly matches (same subject, group, room, day and time) a period already assigned to another teacher, EMS merges them into a shared period instead of raising a room-conflict error. If a teacher is later removed from that period while their co-teacher keeps it, the shared period simply reverts to being that co-teacher's own.
- **Importing schedules**: if a planner file assigns the exact same class to two teachers, importing it produces one shared period, the same as if you'd set it up by hand.

A shared period is otherwise not any different to look at: it just shows up, identically, on each holder's own **Schedule** tab.

---

## Set the Default Schedule Framework

1. Go to **Settings → Employees**.
2. Under **Default schedule framework**, pick the framework every *new* teacher should start from.
3. Save.

This field is required — the module ships with a generic default framework so it is never empty out of the box, but you should point it at the framework that matches your centre's most common level.

---

## Manage Non-teaching Types

The list of non-teaching reasons (Break, Guard, Coordination Meeting...) shown wherever a period isn't a subject is configurable, so you can add a new one yourself if your centre's external planner starts sending a code EMS doesn't recognise yet — no developer needed.

1. Go to **Configuration → Teachers → Non-teaching types**.
2. Click **New**, set a short **Code** (must match exactly what the external planner uses for that activity) and a **Name** (what teachers and reports will show).
3. Optionally mark it **Is a break** (dropped from the weekly hours summary entirely, like the patio break) or **Always a fixed-schedule commitment** (always counted in the "Other fixed-schedule hours" column, like a guard duty).
4. Save. The new type is immediately available in the "non-teaching" dropdown when editing a schedule, and recognised the next time you import a planner file that uses its code.

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

Below the grid, a small summary table shows the teacher's total weekly hours in two columns:
- **Weekly teaching hours**: one row per level of studies (e.g. CFGS, CFGM, ESO), one row per reinforcement group taught (these don't belong to a single level), plus any non-teaching activity not listed in the other column.
- **Other fixed-schedule hours**: guard duties (any day) and coordination meetings specifically on Wednesday.

The break is never counted in either column. A period that only partially overlaps an hour still counts as a full hour. Each column shows its own total, followed by the overall total (24 hours for a full-time teacher). This summary always reflects the saved schedule, so it disappears while you're editing and reappears (updated) once you save.

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

## Import Working Schedules From a File

If your centre already exports schedules from an external planning tool (XML), use the batch importer instead of building schedules by hand — each file can already describe several teachers at once (matched by e-mail), and you can attach more than one file in the same run. There is no separate per-teacher import any more: a teacher joining mid-year gets their schedule via **New** on their own **Schedule** tab (see "Start a Teacher's Schedule From a Framework or From Another Teacher" below) or by hand, never a single-teacher file upload.

1. Go to **Configuration → Teachers → Working schedules**.
2. Open the ⚙️ (cog) menu above the list and choose **Import: planner data**.
3. On the **Welcome** screen, attach one or more XML files, then click **Continue** — nothing is written yet at this point, and nothing about the files' content is checked here either.

   ![The wizard's Welcome screen with a planner file attached](../../assets/admin/working-schedules-import-01-welcome.png)
4. If the files mention any group name EMS couldn't match automatically, a **Resolve groups** screen lists each one: pick the real group from the dropdown for each row (or create one on the spot, the same way you would from any other group field), then click **Continue**. If every group was recognized automatically, you'll see a confirmation message instead of a list. **Continue** shows grayed out until every row has a group picked.
5. If the files mention a teacher e-mail EMS couldn't find, a **Resolve teachers** screen lists each one, with **New** ticked by default (assuming a genuinely never-hired teacher) — leave it ticked to create a brand-new pending-identification teacher for that e-mail at the final Import step, the same way a not-yet-hired post code does (see "Teachers Not Yet Hired" below), except the file's own e-mail is kept and pre-filled as their **Work email**, editable by hand (**Assign corporate email manually** ticked) rather than auto-generated, since it hasn't been confirmed yet; or, if it's actually a typo/mismatch of an already-existing teacher, untick **New** and pick the real teacher from the dropdown instead (unticking is what unlocks it). If every e-mail was recognized, you'll see a confirmation message instead. **Continue** shows grayed out here too until every row has either a teacher picked or **New** ticked.

   ![The Resolve teachers screen with the New checkbox before the Teacher dropdown](../../assets/admin/working-schedules-import-02-resolve-teachers-new.png)
6. If two different teachers in the same batch end up scheduled in the same classroom at the same time, a **File conflicts** screen lists each colliding pair (both the "File" columns are entries from the file you're importing) with a way to resolve it: **"Confirm"** if they're genuinely sharing that class (the default when it's the same subject and group — only offered for this exact case, not shown at all for the others); **"Reassign rooms"** for a real room clash — a split ("Split session") needing two different rooms (same subject, different groups) or two entirely different classes that happen to collide (different subjects, "Room conflict") — pick the actual room for each side, since both start pre-filled with the same colliding one (their group's own currently-assigned classroom); or **"Left prevails"/"Right prevails"** to simply keep one side and drop the other instead. Each row is tinted by how urgent it is: yellow for a co-teaching/split-session row that's only asking for a quick confirmation, red for a genuine room clash that needs an actual decision. If there's nothing to resolve, you'll see a confirmation message instead. **Continue** shows grayed out until every row has an actual resolution (for "Reassign rooms", that means the two rooms must actually differ).

   ![The File conflicts screen with a yellow-tinted split-session row](../../assets/admin/working-schedules-import-03-internal-conflicts-colors.png)
7. If any entry from the file collides with a classroom+time already actively used by someone else's existing schedule, an **Existing schedule conflicts** screen lists each one (same yellow/red row tinting) — here the columns are labeled **"File"** (the new entry) and **"Database"** (the already-existing session), instead of both saying "File" like the previous screen — with the same resolution options as "File conflicts" above. Choosing **"Left prevails"** archives the existing session (freeing the slot for the new one); choosing **"Right prevails"** drops the new entry instead, keeping the existing session untouched. One case defaults differently: a teacher already double-booked in *time* against their own existing schedule, in a genuinely different room (not a room clash at all — reassigning rooms wouldn't fix a teacher needed in two places at once), defaults to **"Left prevails"** with no room pickers, rather than "Reassign rooms". If there's nothing to resolve, you'll see a confirmation message instead.
8. Click **Continue** through the remaining steps (not yet built as their own screens).
9. On the final step, click **Import**. This is the point where everything is actually written, and where any remaining problem (a missing classroom) is reported, naming exactly what needs fixing.

> Run this during next-course preparation, once the previous course's schedules have already been archived by the "Setting Up the Next Course" wizard — running it against a course already in progress can create conflicts that then need manual resolution.

If any of the teachers found across the files already has a schedule, it's updated in place (not replaced from scratch) once you click **Import** — existing subject assignments and attendance templates stay in sync with the new file.

---

## Teachers Not Yet Hired (Pending Identification)

New timetables sometimes arrive before every post is staffed — your planner tool names those rows with a placeholder code (`X1`, `X2`...) instead of a real teacher's e-mail. Importing such a file no longer fails on those rows:

> The same pending-identification mechanism also covers a genuine e-mail that doesn't match any existing teacher — tick **New** for that row on the **Resolve teachers** screen instead of picking one (see step 5 of "Import Working Schedules From a File" above). The only difference from a placeholder code is that the file's e-mail is kept, pre-filled as an editable **Work email** (**Assign corporate email manually** ticked), rather than left for a later "Generate Google account" to assign automatically.

1. Attach the file and click through the wizard as usual (see "Import Working Schedules From a File" above) — a placeholder code isn't treated as a problem at any step.
2. Click **Import** on the final step. A new employee record is created for each not-yet-identified code, already named e.g. "Pending teacher (X1)", with **their schedule, subjects and attendance lists already set up** exactly as if they were a known teacher.
3. These records show a **"Pending identification"** badge in the Teachers list/kanban and a ribbon on their own form, so they're easy to find (use the **Pending identification** filter/group-by in the Teachers list) and easy to tell apart from a real, already-identified teacher.

When the post is filled:

1. Open the pending teacher's employee record.
2. Replace the placeholder **Name** with the real teacher's name, and fill in their **Personal email**.
3. Click **Generate Google account**, exactly as you would for any new teacher.

That single click both creates the teacher's Google Workspace account/EMS login **and** confirms their identity — the "Pending identification" badge disappears, and nothing about their already-imported schedule, subjects or attendance lists needs to be redone.

Re-importing an updated file for a post that's still unstaffed (same placeholder code) updates that same pending teacher's schedule in place, the same way re-importing an already-identified teacher's file does — it never creates a second, duplicate record for the same code.

---

## Start a Teacher's Schedule From a Framework or From Another Teacher

Use this to reset a teacher onto a different framework (e.g. they now teach a different level), or to set up a **substitute** with the same schedule as the teacher they're covering for:

1. Open the teacher's **Schedule** tab and click **New**.
2. Choose either a **schedule framework** (starts blank, following that framework's periods) or **another teacher** (copies their real subjects/groups — ideal for substitutions).
3. Click **Load** — you'll see the loaded schedule in edit mode.
4. Adjust anything needed, then click **Save** to apply, or **Cancel** to discard and keep the teacher's previous schedule untouched.

> **New** replaces the whole schedule — nothing from before is kept unless it also appears in what you just loaded. Cancelling before Save leaves everything exactly as it was.

---

## Reinforcement Groups

A reinforcement group is a class **group** (the same "Groups" record a regular class group is) used for a support/reinforcement class that mixes students from different regular groups, and even different studies — e.g. a small maths reinforcement group with students pulled from three different first-year groups.

1. Go to **Configuration → Students → Groups** and create a new one.
2. Set its **Group type** to **Reinforcement**. This hides the Level/Study/Course/Acronym/Tutor/Delegate fields (a reinforcement group has none of these) and lets you type the group's **Name** directly — set it to exactly match whatever your external planner exports for this group, since the schedule importer matches by exact name.
3. Set its **Classroom**, same as any other group — it's still required for the schedule to import correctly.
4. On the **Students** tab, add the students who attend this reinforcement class, regardless of which regular group or study they belong to. This does **not** change each student's own main group.
5. Save.

Once created, a reinforcement group is used in a teacher's schedule exactly like any other group — assign it manually in the Schedule tab, or let the file importer resolve it by name.

---

## Export a Teacher's Schedule to PDF

1. Open the teacher's **Schedule** tab and click **PDF**.
2. A printable weekly timetable is generated and downloaded — one row per period, one column per weekday, each cell showing the subject/group or non-teaching reason and the classroom.

The document opens with the teacher's name and the current course, followed by their department (if assigned) and their role(s) — a tutor's line also shows which group they tutor, and a department head's line shows which department.

This is also available from the employee form's own **Print** menu, in case you need to export several teachers' schedules from a list view.

---

[← Back to main index](index.md)
