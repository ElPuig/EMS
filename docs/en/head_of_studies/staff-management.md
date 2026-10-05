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
3. Leave **Staffing type** on **Named teacher**, and fill in the teacher's name and, in the right-hand column under **Manager**, their **Private Email**. This one is required, and the next section explains why.
4. Click **Save**. The rest of the data (job position, department, working schedule) can be completed now or later.

Saving also creates the teacher's own weekly schedule, prefilled from the centre's schedule framework. You do not have to create it by hand: open the **Schedule** tab on the teacher's record to adjust it.

### Why the personal email is required

It is the address the credentials of the new Google account are sent to. Without it the corporate account is simply not created: the record saves, but nothing else happens and a note is left in the record's message history explaining what is missing. Ask for a personal address before creating the record — it is not a formality, it is the only way the new teacher receives their password. The field appears twice on the record — on the main screen, so that nothing required is hidden behind a tab while you are creating it, and in its usual place inside the **Private Information** tab. They are the same field: filling in one fills in the other. It can't be an address of the centre's own domain either: EMS refuses to save it, because it is also the recovery address of the corporate account.

---

## Create a Vacancy Pending Identification

When a post already has its department, schedule and so on but nobody filling it yet, create it as a vacancy: it gets no Google account and no EMS user.

1. Navigate to **Educational Community → Teachers** and click **New**.
2. Under the name, set **Staffing type** to **Vacancy pending identification**.
3. Fill in the **Vacancy code** (e.g. `X1`). Two active vacancies can't share a code. If a schedule file later names the same code, its schedule is imported onto this record.
4. Optionally, use the **Name** to describe the post (e.g. "Half-time AAI post"); left blank, the record takes the vacancy code as its name. No personal email is asked for.
5. Click **Save**. The record shows a **Pending identification** ribbon.

![Teacher record created as a vacancy: Staffing type set to Vacancy pending identification, with its vacancy code](../../assets/head_of_studies/hos-staff-management-vacancy.png)

### When the post is filled

1. Open the vacancy.
2. Set **Staffing type** to **Named teacher**.

![The vacancy switched to Named teacher: the Private Email and the suggested Google username appear](../../assets/head_of_studies/hos-staff-management-vacancy-identify.png)

3. Replace the **Name** with the person's real name and fill in their **Private Email**.
4. Click **Save**. The Google account and the EMS user are created automatically in a few moments, the ribbon disappears, and the record's message history notes the vacancy code it had. The schedule, subjects and attendance lists stay as they are.

If the person already has a corporate account (for example, on another record), set **Staffing type** to **Named teacher**, tick **Assign corporate email manually** and type their corporate email: no new account is created. Then use **Create EMS User** in the **Actions** menu.

---

## Edit a Teacher

1. Navigate to **Educational Community → Teachers** and open the record.
2. Change whatever you need and click **Save** (or navigate away — Odoo saves automatically).

---

## Identity Document and Social Security Number

The **Private Information** tab of a teacher's record opens with an **Identification** group holding the **Identity document** (DNI/NIE) and the **Social Security No**. You, the Deputy, the Director and the TAC coordinator can edit them on teachers' records; the Secretariat keeps them up to date for every staff member, ASP included.

A teacher's Department Chief and Seminar Chief can also see these two fields, read-only, on the records of the staff in their own department (only their own chain of command, not other departments). For them the tab shows the **Identification** group alone: the rest of the private information stays hidden.

---

## Creating the Corporate Google Account

When you save a new teacher's record with the name and personal email filled in, the corporate account is created automatically in a few moments: you don't need to press anything.

The actions that manage the teacher's corporate account are in the **Actions** menu on the top bar of their record. Which one appears depends on the state the account is in — only one is ever offered at a time:

| Button | When it appears | What it does |
|--------|-----------------|--------------|
| **Create Google account** | The teacher has no corporate account and none is being created | Creates the Google Workspace account and the EMS user in one step. Only needed when the automatic creation wasn't possible |
| **Create EMS User** | The corporate email already exists, but there is no EMS user linked to it | Only links or creates the EMS user — it does not touch Google |
| **Suspend Google account** | The account is active | Suspends it (for example, when the teacher leaves the centre) |
| **Reactivate Google account** | The account is suspended | Reactivates it |

![Actions menu with Create Google account on a teacher's record with no account yet](../../assets/head_of_studies/hos-staff-management-create-account.png)

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
