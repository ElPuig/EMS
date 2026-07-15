[Català](../../ca/admin/alta-professor-compte-google.md) | [Castellano](../../es/admin/alta-professor-compte-google.md) | [English](alta-professor-compte-google.md)

---

# Onboarding a Teacher and Creating Their Corporate Email Account (Google Workspace)

This guide explains how to onboard a teacher or **ASP** (Administrative and Services Personnel) staff member, and how their corporate Google Workspace email account is created automatically.

**Required role:** Administrator or Human Resources

---

## Index

1. [Access](#access)
2. [Step 1 — Create the Teacher Record](#step-1--create-the-teacher-record)
3. [Step 2 — Fill in the Basic Data](#step-2--fill-in-the-basic-data)
4. [Step 3 — Fill in the Private Email](#step-3--fill-in-the-private-email)
5. [What Happens Next](#what-happens-next)
6. [Special Cases](#special-cases)

---

## Access

**Educational Community → Teachers**

---

## Step 1 — Create the Teacher Record

In the top menu, click **Teachers (1)** and then the **New (2)** button to open the onboarding form.

![Teachers menu and New button](../../assets/admin/alta-professor-01-menu-nou.png)

---

## Step 2 — Fill in the Basic Data

On the onboarding form:

1. Enter the **Teacher's Name (1)**.
2. Fill in the job details under **Department / Job Position (2)**.
3. Optionally, provide a **Suggested Google username (3)**: only the part before the domain (e.g. `jdoe`), shown next to `@elpuig.xeill.net`. If left blank, the system will generate one automatically from the name.

![Onboarding form with name, department and suggested Google username](../../assets/admin/alta-professor-02-dades-formulari.png)

> The **Work Email** field is shown greyed out (read-only): it is the corporate email that will be generated automatically (see [What Happens Next](#what-happens-next)).

---

## Step 3 — Fill in the Private Email

Go to the **Private Information** tab and fill in the **Private Email** field (1). This personal email address is where the password for the new corporate email will be sent.

![Private Information tab with the private email field](../../assets/admin/alta-professor-03-correu-privat.png)

> **Important:** this **Private Email** field is **required** for the Google account to be created — the form will not let you save a **new** teacher/ASP record without it. On records created before this rule, it may still be missing: in that case no account is created automatically and the reason is recorded in the record's message log (chatter).

> **Other data:** it is important to **fill in as much data as possible**, such as the emergency contact, personal phone number, car license plate…

Once the data is filled in, save the record (Odoo saves automatically when navigating away, or click the save cloud icon).

---

## What Happens Next

When the record is saved, if all the required data is present (name and private email), the system automatically creates the Google Workspace account in the background:

- Assigns a corporate email `@elpuig.xeill.net` (the suggested username, or one generated from the name if none was given or it is already taken).
- Generates a temporary password (which must be changed on first login).
- **Creates the teacher's EMS user automatically**, with the corporate email as login and **Sign in with Google already connected**: the teacher enters EMS with the Google button, no separate password is needed and no password email is sent. Teachers get the *Teacher* permissions; ASP staff get a basic internal user (their permissions arrive with their roles/job position).
- Sends the credentials by email to the private address provided in step 3 (the message also explains how to enter EMS).
- Attaches a PDF with the credentials to the teacher's record.

The **Create Google account** button, at the top of the record, lets you force this process instantly without waiting for the background processing.

---

## Special Cases

- **The teacher already had a corporate email:** if the work email field already contained an `@elpuig.xeill.net` address, the system adopts it as-is and does not create a new one. If that teacher has no EMS user yet, the **Create Google account** button (still visible in this case) creates and links it.
- **The teacher has a work email from another domain:** the system does not overwrite it automatically; a notice is posted in the record's message log for manual review.
- **Manual email assignment:** the **Assign corporate email manually** checkbox, on the teacher's record, lets Human Resources enter the work email by hand, for exceptional cases. **When checked, the system does not generate any account automatically.** After typing a corporate address, the **Create Google account** button creates/links the EMS user for it.
- **Departure (archiving the record):** besides suspending the Google account, archiving the employee **immediately deactivates their EMS user**, so they can no longer sign in. Unarchiving restores both.

---

[← Back to Administrator index](index.md)
