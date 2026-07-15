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
| Department chieff | Department Chief | Manual — added to the teacher's roles |
| Head of studies / Deputy head of studies | Head of Studies | Manual — added to the teacher's roles |
| Director | Director | Manual — added to the teacher's roles |

> Department Chief currently grants the same permissions as Tutor, plus the ability to create, edit and delete Class Groups (Contacts → Groups). It exists as its own level so it can be extended independently in the future.

---

## Access

Navigate to: **Employees → [open the teacher's record]**

---

## Assign a Role

1. Open the teacher's employee record.
2. In the **Roles** field, add the role that matches the permission level to grant (e.g. **Department chieff**).
3. Click **Save** (or navigate away — Odoo saves automatically).

The teacher's user account is updated immediately: the security group tied to the role is granted, together with everything it implies (e.g. assigning **Department chieff** also grants Tutor and Teacher access).

> The **Tutor** role cannot be added or removed manually here — it is managed automatically based on whether the teacher is set as the tutor of a Class Group.

---

## Remove a Role

1. Open the teacher's employee record.
2. In the **Roles** field, remove the role.
3. Click **Save**.

The corresponding security group (and anything only that role justified) is revoked from the teacher's user account.

---

[← Back to main index](index.md)
