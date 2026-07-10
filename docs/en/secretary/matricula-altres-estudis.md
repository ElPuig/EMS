[Català](../../ca/secretary/matricula-altres-estudis.md) | [Castellano](../../es/secretary/matricula-altres-estudis.md) | [English](matricula-altres-estudis.md)

---

# Enrolling a current student into a different study

This guide explains how to propose an enrollment to a student **who already belongs to the centre** but who will follow **a different study** next year.

---

## Contents

1. [When to use this procedure](#when-to-use-this-procedure)
2. [Access](#access)
3. [Step 1 — Find the students](#step-1--find-the-students)
4. [Step 2 — Tick "Enroll in a different study"](#step-2--tick-enroll-in-a-different-study)
5. [Step 3 — Choose the template and the destination group](#step-3--choose-the-template-and-the-destination-group)
6. [Who can do it](#who-can-do-it)
7. [Frequently asked questions](#frequently-asked-questions)

---

## When to use this procedure

Every year the GEDAC import finds applicants who **are already active students of the centre**: 4th-course ESO students granted a place in SMX, AO students moving to GA, SMX students switching to GA. Because they are still enrolled in their current study, the importer **leaves them untouched** and lists them apart, in the `gedac_alumnes_actius_<date>.csv` file you can download once the import finishes.

These students need an enrollment proposal like everybody else, but for the **new study**. If you try the normal procedure, the system only offers templates of the study the student is currently in, which is why you used to get *"No enrollment templates available for the selected students' study"*.

> **Note:** This procedure also covers any change of study unrelated to GEDAC (for instance, a student asking in October to move from SMX to GA).

---

## Access

**Academic management → Enrollment → Enrollment proposal**

Every student is listed there, including those changing study: they are still students of the centre. Use the `gedac_alumnes_actius_<date>.csv` file as your working list.

---

## Step 1 — Find the students

Use the left panel to filter by current group (ESO4E, AO1A…) and tick, in the list, the students heading for **the same destination study**.

> **Important:** Make one pass per destination study. The dialog applies **a single template to every selected student**, so those going to GA and those going to SMX must be processed separately, even when they come from the same origin group.

Once the selection is made, click the **Enrollment proposal** button in the top bar.

---

## Step 2 — Tick "Enroll in a different study"

The proposal dialog opens. It contains an **Enroll in a different study** checkbox.

- If you selected students from **different origins** (say one from ESO and one from AO), or from a study with no template at all, the checkbox is **already ticked automatically** and the dialog warns you that templates from every study are being listed.
- In any other case, tick it yourself.

Ticking it makes the **Enrollment template** dropdown stop filtering and list **every** template of the centre.

---

## Step 3 — Choose the template and the destination group

1. In the **Enrollment template** dropdown, pick the template of the destination study and course (for example, *GA-1* for the first course of Gestió administrativa).
2. In the **Destination group** dropdown, pick the actual group — it now only lists groups of the template's study. **Pick the right shift** (for example, *GA1A-afternoon*): the enrollment shift is taken from this group, not from the student's current group. A morning AO student moving to an afternoon GA group ends up correctly on the afternoon shift.
3. Review the student list. To exclude one, click the ✕ on its row.
4. Click **Create enrollments**.

The enrollments are created in **draft** state, against the destination study, and follow the usual circuit: review, sending to the family and confirmation through the portal.

---

## Who can do it

The **Enroll in a different study** checkbox is only visible to **secretary** and **academic administration**.

Tutors keep proposing same-study renewals for their own students, as always, but cannot move them to another study. A tutor who spots a student in this situation should tell the secretary.

---

## Frequently asked questions

**I ticked the box but picked the wrong template. What now?**
Untick it and the dropdown filters by the student's current study again. If you already created the enrollments, open each draft and change its study, or cancel it and start over.

**Why can't I select students from different groups at once?**
You can, as long as they share the same destination study. What you cannot do is apply a GA template and an SMX template in the same pass.

**The student still shows up in the old group.**
That is correct. The student does not change group until the enrollment is confirmed and the course transition runs. The **Destination group** you picked is stored on the enrollment.

---

[← Back to the secretary index](index.md)
