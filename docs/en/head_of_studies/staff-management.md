[Català](../../ca/head_of_studies/staff-management.md) | [Castellano](../../es/head_of_studies/staff-management.md) | [English](staff-management.md)

---

# Creating and Editing Teachers

The Head of Studies, the Deputy Head of Studies and the TAC coordinator can create new teacher records and edit existing ones, without going through an administrator. They manage a teacher's record in full, the **Private Information** and **HR Settings** tabs included.

**Required role:** Head of studies, Deputy head of studies, Director or TAC coordinator

---

## Access

Navigate to: **Educational Community → Teachers**

---

## Create a Teacher

1. Navigate to **Educational Community → Teachers**.
2. Click **New**.
3. Fill in the teacher's name and, in the right-hand column under **Manager**, their **Private Email**. This one is required, and the next section explains why.
4. Click **Save**. The rest of the data (job position, department, working schedule) can be completed now or later.

Saving also creates the teacher's own weekly schedule, prefilled from the centre's schedule framework. You do not have to create it by hand: open the **Schedule** tab on the teacher's record to adjust it.

### Why the personal email is required

It is the address the credentials of the new Google account are sent to. Without it the corporate account is simply not created: the record saves, but nothing else happens and a note is left in the record's message history explaining what is missing. Ask for a personal address before creating the record — it is not a formality, it is the only way the new teacher receives their password. The field appears twice on the record — on the main screen, so that nothing required is hidden behind a tab while you are creating it, and in its usual place inside the **Private Information** tab. They are the same field: filling in one fills in the other.

---

## Edit a Teacher

1. Navigate to **Educational Community → Teachers** and open the record.
2. Change whatever you need and click **Save** (or navigate away — Odoo saves automatically).

---

## Creating the Corporate Google Account

The buttons that manage the teacher's corporate account are on the top bar of their record. Which one appears depends on the state the account is in — only one is ever offered at a time:

| Button | When it appears | What it does |
|--------|-----------------|--------------|
| **Create Google account** | The teacher has no corporate account yet | Creates the Google Workspace account and the EMS user in one step |
| **Create EMS User** | The corporate email already exists, but there is no EMS user linked to it | Only links or creates the EMS user — it does not touch Google |
| **Suspend Google account** | The account is active | Suspends it (for example, when the teacher leaves the centre) |
| **Reactivate Google account** | The account is suspended | Reactivates it |
| **Mark as identified** | The record came from a schedule import and is still a placeholder | Clears the pending-identification state without creating any account |

When the account is created, the credentials travel two ways: a PDF is attached to the teacher's own record, and a welcome email with the password is sent to their personal address. If the account cannot be created because some required data is missing, a note is posted in the record's message history explaining exactly which fields are missing.

---

## What you cannot do

Two limits are deliberate, and Odoo will refuse the operation if you try:

- **You cannot delete a staff record.** Deleting is reserved for the administrator. If a teacher leaves the centre, do not delete their record — suspend their Google account and archive the record instead, so their history is preserved.
- **You cannot edit Administration and Services Personnel (ASP) records.** You can still consult them — and, since you now hold the HR permissions, their private information too — but editing and creating are restricted to teaching staff. ASP records are managed by the Secretariat.

---

## Who else can do this

Creating and editing teachers is also available to the Director (who inherits the Head of Studies permissions) and to the administrator, who can additionally delete records and manage ASP staff. See [Teacher Roles and Permission Levels](../admin/teacher-roles.md) for the full permissions ladder and for how the TAC coordinator role is assigned.

---

[← Back to Head of Studies index](index.md)
