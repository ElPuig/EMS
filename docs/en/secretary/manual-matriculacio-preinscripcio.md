[Català](../../ca/secretary/manual-matriculacio-preinscripcio.md) | [Castellano](../../es/secretary/manual-matriculacio-preinscripcio.md) | [English](manual-matriculacio-preinscripcio.md)

---

# Enrolling the preinscription students

This guide explains, step by step, how the **secretary** staff processes the **preinscription** students (applicants granted a place) all the way to generating their **enrollment proposal** and sending it to the families, all from the **Academic management** module.

The GEDAC import brings in **two kinds of students**, each found in a different view:

* **New students** — applicants who do not belong to the centre yet. They are created as *Applicant* contacts.
* **Current students** — internal continuers who **change study** next year (a 4th-year ESO student granted a place in SMX, an AO student moving to GA…). They already are students, so they are not touched: only the **destination** GEDAC granted them is recorded.

From Step 3 on, the circuit is the same for both.

---

## Index

1. [Step 1 — Import the applicants from GEDAC](#step-1--import-the-applicants-from-gedac)
2. [Step 2 (new students) — Review the preinscription applicants](#step-2-new-students--review-the-preinscription-applicants)
3. [Step 2 (current students) — Find the internal continuers](#step-2-current-students--find-the-internal-continuers)
4. [Step 3 — Create the enrollment proposals](#step-3--create-the-enrollment-proposals)
5. [Step 4 — Give portal access to students and families](#step-4--give-portal-access-to-students-and-families)
6. [Step 5 — Review the generated enrollments](#step-5--review-the-generated-enrollments)
7. [Step 6 — Send the enrollment proposals](#step-6--send-the-enrollment-proposals)
8. [Study changes that do not come from GEDAC](#study-changes-that-do-not-come-from-gedac)
9. [Bonifications and exemptions approved after confirmation](#bonifications-and-exemptions-approved-after-confirmation)
10. [FAQ](#faq)

---

## Step 1 — Import the applicants from GEDAC

In the **Preinscription** view (menu **Enrollment → Preinscription**), open the actions menu (the gear icon ⚙️ next to the title) and choose **Import from GEDAC (1)**.

![Preinscription actions menu with the Import from GEDAC option](../../assets/secretary/preinscrpcio-Secretaria-01.png)

The **Import from GEDAC** wizard opens. This process imports the applicants granted a place **at this centre** from the GEDAC preinscription file (Excel `.xlsx` or `.csv`). Specifically, it:

* Creates the new applicants (contact type *Applicant*, with no group), matching by RALC.
* Fills in the granted study and the preinscription shift from the assignment.
* Stores the provenance data (origin centre and study) in the notes.
* For students **already belonging to the centre**, it does not touch their own data (name, current group, contact details): it only **records the granted destination** (study, shift and course).
* Skips the rows assigned to another centre or with no place granted.

To run the import:

1. Click **Upload your file (1)** and select the GEDAC file (`.xlsx` or `.csv`).
2. Press **Import applicants (2)**.

![GEDAC import wizard](../../assets/secretary/preinscrpcio-Secretaria-02.png)

When it finishes, the wizard shows an **import summary**: how many applicants were created, how many were updated and how many rows were skipped. You can also **download the log (CSV)** and, if there are any, the `gedac_alumnes_actius_<date>.csv` file with the internal continuers.

![Import result summary](../../assets/secretary/preinscrpcio-Secretaria-03.png)

---

## Step 2 (new students) — Review the preinscription applicants

New applicants appear in the **Preinscription** view. To review them comfortably:

* Use the **study panel** on the left **(1)** to filter the students by study (SMX, ASIX, GA...). The number of applicants is shown next to each study.
* The list comes **automatically grouped by shift** (*Afternoon* / *Morning*) **(2)** and, within each shift, **by course** (1st, 2nd) **(3)**. This grouping makes applying the **enrollment template** simpler: each combination of **study, shift and course** has a default template and destination group.

![Preinscription view with the study panel and the grouping by shift and course](../../assets/secretary/preinscrpcio-Secretaria-04.png)

Select the applicants (the header checkbox for those on the page, or **Select all** for the whole study) and go to [Step 3](#step-3--create-the-enrollment-proposals).

> **Tip:** work **study by study**. That way every selected applicant shares the same template.

---

## Step 2 (current students) — Find the internal continuers

Students who already belong to the centre **do not show up in Preinscription**: they are still students. You will find them in **Enrollment → Enrollment proposals**, using the **With GEDAC assignment (1)** filter, which lists only those with a granted destination who are **not enrolled yet**.

![Enrollment proposals with the With GEDAC assignment filter](../../assets/secretary/preinscrpcio-Secretaria-04b.png)

With the **column selector** (the sliders icon, at the far right of the list header) you can show **Assigned study**, **Assigned course** and **Assigned shift**, and with *Group by* → **Assigned study** you can work through them block by block (first the ones heading to GA, then the ones heading to SMX).

Tick the students heading to **the same destination study** and go to [Step 3](#step-3--create-the-enrollment-proposals).

> **Important:** do one pass per destination study. The wizard applies **a single template to every selected student**.

---

## Step 3 — Create the enrollment proposals

With the students selected (whether from the new-students Step 2 or the continuers one), press the **Enrollment proposal (1)** button in the top bar.

![Applicant selection and the Enrollment proposal button](../../assets/secretary/preinscrpcio-Secretaria-05.png)

The **Enrollment proposal** wizard opens, **already filled in** from the preinscription data:

* **Enrollment template** — the one for the granted course (e.g. *SMX-1*). For continuers, the one of the **destination study**, not of their current one.
* **Destination group** — the first group of the granted course and **shift** (e.g. *SMX1C*). You can keep it or change it; if you leave it empty, each student gets their own suggested group.
* **Students** — the selected list. You can remove one with the cross on the right.

Check that everything is correct and press **Create enrollments (1)**.

![Enrollment proposal wizard](../../assets/secretary/preinscrpcio-Secretaria-06.png)

> **Why doesn't a continuer's suggested group keep their current group's letter?** Because across different studies it means nothing: an ESO4**E** student has no SMX1**E** to land in. The system treats it as a new entry and suggests the **first free group of the granted shift**. You can change it if you want to distribute them differently.

> This action **creates a (draft) enrollment** for each student, with the given study, course and destination group. **Nothing is sent** to the families yet: that happens in Step 6.
>
> When a continuer's enrollment is **confirmed**, the GEDAC assignment is considered spent and the student **drops out of the filter**: that way the filter always shows only those still pending.

---

## Step 4 — Give portal access to students and families

For the families to be able to confirm the enrollment later, they need **portal access**. From the **Preinscription** view, with the applicants selected, open the **Actions** menu and choose **Portal access (students/families) (1)**.

![Actions menu with the portal access option](../../assets/secretary/preinscrpcio-Secretaria-07.png)

> This option generates or activates the educational portal access for the students and their families, so that when they receive the proposal email they can log in to answer the authorizations and confirm the enrollment. Students already belonging to the centre usually have it active.

---

## Step 5 — Review the generated enrollments

The enrollments created in Step 3 are in the **Enrollment → Enrollments (1)** view. To see only the ones not sent yet, apply the **Not sent (2)** filter (it shows the enrollments in *draft* state).

![Enrollments view with the Not sent filter](../../assets/secretary/preinscrpcio-Secretaria-08.png)

In the list you can check, for each enrollment, the **student**, the **level** and the **study**, the **shift**, the **academic year**, the **destination group**, the **total amount** and the **state**.

> The available filters are **Not sent** (drafts), **Not confirmed** (drafts and sent), **Confirmed** and **Cancelled**.

---

## Step 6 — Send the enrollment proposals

Once the enrollments are reviewed, select the ones you want to send by ticking their checkboxes **(1)**. The **Send enrollment (2)** button appears at the top; press it.

![Enrollment selection and the Send enrollment button](../../assets/secretary/preinscrpcio-Secretaria-09.png)

Pressing **Send enrollment** does the following for each selected enrollment:

* The enrollment proposal **email is sent** to the student/family (with the centre's template).
* The enrollment moves to the **sent** state.

> From here on, the families receive the email and can **confirm the enrollment** from the portal by following the [Guide to confirm the enrollment proposal](../families/manual-confirmacio-matricula.md).

---

## Study changes that do not come from GEDAC

If a student changes study **outside the preinscription** (e.g. asking in October to move from SMX to GA), they have no GEDAC assignment and the system cannot suggest anything.

In that case, tick the **Enroll in a different study** checkbox in the proposal wizard: the **Enrollment template** dropdown stops filtering and lists **every** template of the centre. Pick the template and the **Destination group** by hand, with the **right shift** (the enrollment's shift is taken from the group you pick).

The checkbox is only visible to **secretary** and **academic administration**. Tutors keep proposing their students' renewals within the same study: a tutor spotting a student who must change study has to tell the secretary.

---

## Bonifications and exemptions approved after confirmation

When a student's fee **bonification or exemption** document is approved, the discount is automatically applied **only to enrollments still in draft**. **Already confirmed** enrollments are frozen: neither the lines nor the total change, because the invoice has already been issued with the original amounts. This way, what the student sees on the portal always matches the invoice.

If the student was entitled to the benefit but uploaded it and it was approved **after** confirming the enrollment, it must be applied explicitly:

1. Open the student's confirmed enrollment.
2. Click the **Re-apply Benefits** button **(1)** in the header.

![Re-apply Benefits button on the confirmed enrollment](../../assets/secretary/preinscrpcio-Secretaria-10.png)

3. Confirm the warning by clicking **Ok**.

![Re-apply benefits confirmation dialog](../../assets/secretary/preinscrpcio-Secretaria-11.png)

4. The system cancels the issued invoice, recomputes the fee lines with the student's current benefit status and generates and posts a new invoice. The operation is logged in the enrollment chatter.

> If the invoice already has **payments registered**, the button is blocked with an error: in that case a **credit note** must be issued manually from Accounting.

---

## FAQ

**The "With GEDAC assignment" filter shows no students.**
Either this year's GEDAC import has not been run yet, or they have all been enrolled already (on confirmation, the student drops out of the filter).

**The suggested group or shift is not the right one.**
Change them in the wizard before creating the enrollments. The suggestion is a starting point, not an imposition.

**I picked the wrong template and already created the enrollments.**
Open each draft enrollment and change its study, or cancel it and start over. While the enrollment is cancelled, the student shows up in the filter again.

**The student is still listed in their old group.**
That is correct. They do not change group until the enrollment is confirmed and the course transition is run. The **Destination group** you picked is stored on the enrollment.

---

[← Back to the secretary index](index.md)
