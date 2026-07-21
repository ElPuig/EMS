[Català](../../ca/admin/teacher-roles.md) | [Castellano](../../es/admin/teacher-roles.md) | [English](teacher-roles.md)

---

# Teacher Roles and Permission Levels

Teachers gain elevated access by being assigned a **role**. Each role that carries a permission level automatically grants the corresponding security group to the teacher's user account — there is no need to edit user permissions directly.

**Required role:** Administrator

---

## Permission Levels

Permission levels form a hierarchy — each level includes all the permissions of the ones before it:

**Teacher → Tutor → Department Chief → Head of Studies → Director → Administrator**

| Role | Permission level granted | How it is assigned |
|------|---------------------------|---------------------|
| *(none)* | Teacher | Default for every teacher |
| Tutor | Tutor | Automatic — set when the teacher is assigned as the tutor of a Class Group |
| Department chieff | Department Chief | Automatic — set as **Department Chief** on the department's own form |
| Seminar leader | Department Chief | Automatic — set as **Seminar Chief** on the department's own form |
| Head of studies / Deputy head of studies | Head of Studies | Automatic — set as **Head of Studies** on a top-level department's own form |
| Director | Director | Automatic — set as **Director** in Settings > EMS Management |

> Department Chief currently grants the same permissions as Tutor, plus the ability to create, edit and delete Class Groups (Contacts → Groups). It exists as its own level so it can be extended independently in the future. Seminar leader is granted the same permission level.

---

## Access

Navigate to: **Employees → [open the teacher's record]**

---

## Assign a Role

1. Open the teacher's employee record.
2. In the **Roles** field, add the role that matches the permission level to grant (e.g. **Department chieff**).
3. Click **Save** (or navigate away — Odoo saves automatically).

The teacher's user account is updated immediately: the security group tied to the role is granted, together with everything it implies (e.g. assigning **Department chieff** also grants Tutor and Teacher access).

> The **Tutor**, **Department chieff**, **Seminar leader**, **Head of studies**, **Deputy head of studies** and **Director** roles cannot be added or removed manually here — no role in this list can. Tutor is managed automatically based on whether the teacher is set as the tutor of a Class Group; the next four are managed automatically from a department's own form; Director is managed automatically from Settings (see below).

---

## Remove a Role

1. Open the teacher's employee record.
2. In the **Roles** field, remove the role.
3. Click **Save**.

The corresponding security group (and anything only that role justified) is revoked from the teacher's user account.

---

## Assigning a Department Chief / Seminar Chief

Unlike the other roles above, **Department chieff** and **Seminar leader** are not set from the teacher's own record — they are set from the department:

1. Navigate to **Employees → Departments** and open the department.
2. Set **Department Chief** (the department's `Manager` field, required) and, optionally, **Seminar Chief**.
3. Click **Save**.

This has an immediate, automatic effect on every teacher in that department:

- Every teacher in the department, **except the Department Chief**, gets their **Manager** set to the **Seminar Chief**.
- The **Seminar Chief**'s own **Manager** is set to the **Department Chief**.
- If no **Seminar Chief** is set, every teacher in the department (except the Department Chief) gets their **Manager** set directly to the **Department Chief** instead — the Seminar Chief level is simply skipped.
- The **Manager** field on a teacher's own record is read-only — it can only be changed by editing the department, never directly on the teacher's record.
- Reassigning either role to a different teacher automatically revokes it from whoever held it before (in that department).

> **Note for existing departments:** a department created before this feature was enabled may have no Department Chief and/or Seminar Chief until an admin opens it and sets them — nothing is filled in automatically. **Department Chief is required** to save the department form going forward.

---

## Assigning a Head of Studies / Deputy Head of Studies

Some departments (currently **VET** and **ESO/BTX**) are **top-level departments** — this changes their form:

1. Navigate to **Employees → Departments** and open the department. The **Top-level Department** checkbox is already ticked for VET and ESO/BTX.
2. The department can no longer have a parent department, and has no Seminar Chief — instead of "Department Chief", the Manager field is labelled **Head of Studies**.
3. Set the **Head of Studies** (required) and choose their **Role**: **Head of studies** or **Deputy head of studies**.
4. Click **Save**.

This has an effect beyond the department itself:

- Every other department placed *under* a top-level department (e.g. "Computer Science" under VET) has its own **Department Chief**'s **Manager** automatically set to the top-level department's **Head of Studies**. Nothing else about that department changes — its own teachers and Seminar Chief keep working exactly as before, only its own Department Chief's Manager changes.
- Since **Head of studies** and **Deputy head of studies** can each only be held by one person centre-wide, trying to set the same one on two different departments for two different people is rejected — clear the other assignment first if you need to reassign.

> **Note for existing departments:** VET and ESO/BTX are already marked as top-level, but with no Head of Studies set yet — an admin must open each one and set it manually; nothing is filled in automatically.

---

## Assigning the Director

Unlike every other role above, the **Director** is not set from any teacher's record or any department form — it is configured centre-wide from Settings:

1. Navigate to **Settings → EMS Management → Center Data**.
2. Set the **Director**.
3. Click **Save**.

This has an effect beyond the setting itself:

- The **Manager** of every top-level department's Head of Studies/Deputy (e.g. VET's, ESO/BTX's) is automatically set to the **Director** — unless the Director is themselves heading that top-level department, in which case their own Manager is left blank.
- Reassigning the Director to someone else automatically revokes the role from whoever held it before.

> **Note on access:** the Settings screen requires Odoo's Settings access (granted through the "Settings Administrator" group or root/admin) — this is a *different* permission from the one that controls the department forms above. Someone with full academic access is not automatically able to reach Settings.

> **Note for existing installations:** no Director is set by default — an admin must configure one manually; nothing is filled in automatically.

---

[← Back to main index](index.md)
