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
| Head of studies / Deputy head of studies | Head of Studies | Manual — added to the teacher's roles |
| Director | Director | Manual — added to the teacher's roles |

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

> The **Tutor**, **Department chieff** and **Seminar leader** roles cannot be added or removed manually here — Tutor is managed automatically based on whether the teacher is set as the tutor of a Class Group; Department chieff and Seminar leader are managed automatically from the department's own form (see below).

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

[← Back to main index](index.md)
