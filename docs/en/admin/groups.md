[Català](../../ca/admin/groups.md) | [Castellano](../../es/admin/groups.md) | [English](groups.md)

---

# Groups

A Group is the class a student belongs to. There are two kinds:

- **Main**: the group a student is actually enrolled in — has a tutor, a delegate, and a single level/study/course/acronym (e.g. `DAM1A`).
- **Reinforcement**: shows up in the teaching schedule like any other group, but has no tutor or delegate, and can mix students from different main groups and studies (e.g. a shared English reinforcement class).

For the group's weekly timetable (aggregated from teachers' own schedules) and its PDF export, see [A Group's Weekly Schedule](group-schedule.md) — this page covers creating and managing the group itself.

**Required role:** Department Chief (or above — Head of Studies/Deputy/Director/Administrator already have this access via role escalation)

---

## Access

Navigate to: **Educational Community → Groups**

---

## Create a Main Group

1. Click **New**.
2. Leave **Group Type** on **Main** (the default).
3. Fill in:
   - **Level** and **Study** *(both required)*.
   - **Course** *(required)*: the year number (e.g. `1`).
   - **Acronym** *(required)*: e.g. `A`. The group's name is built automatically from Study + Course + Acronym (e.g. `DAM1A`) — you don't type it directly.
   - **Tutor**: the teacher responsible for this group. Assigning it here automatically grants that teacher the Tutor role.
   - **Delegate**: a student representative (only selectable once the group has students).
   - **Shift**, **Classroom**, **External ID** (Esfera/SAGA code) as needed.
4. Click **Save**.

Students aren't added from here — see the **Students** tab to review who's assigned, but a student's own record (or the enrolment flow) is what actually assigns them to a group.

---

## Create a Reinforcement Group

1. Click **New**.
2. Switch **Group Type** to **Reinforcement**. Level, Study, Tutor and Delegate disappear — they don't apply.
3. Fill in a **Name** directly (e.g. `REF-MATHS`).
4. In the **Students** tab, add students from any main group/study.
5. Click **Save**.

---

## Switching a Group's Type

You can switch an existing group between Main and Reinforcement, but:
- Switching **Main → Reinforcement** is blocked if the group still has students enrolled as their main group — reassign them to another group first.
- Switching either way clears the fields that no longer apply (level/study/course/acronym/tutor/delegate, or the reinforcement student list).

---

## Delete a Group

Select it in the list and use the **Action** menu (⚙) → **Delete**. Blocked if the group is still referenced elsewhere (students, sessions, teaching assignments...).

---

[← Back to Administrator index](index.md)
