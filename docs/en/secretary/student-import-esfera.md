[Català](../../ca/secretary/student-import-esfera.md) | [Castellano](../../es/secretary/student-import-esfera.md) | [English](student-import-esfera.md)

---

# Importing students from Esfera (SAGA)

This guide explains how to bulk-import or refresh student and family-contact data from an **Esfera (SAGA)** export file.

---

## Contents

1. [Esfera vs. GEDAC — two different imports](#esfera-vs-gedac--two-different-imports)
2. [Running the import](#running-the-import)
3. [What gets created or updated](#what-gets-created-or-updated)
4. [Reading the result and the log](#reading-the-result-and-the-log)
5. [Things to check afterwards](#things-to-check-afterwards)

---

## Esfera vs. GEDAC — two different imports

Don't confuse this with [Enrolling the preinscription students](manual-matriculacio-preinscripcio.md), which is a **different** import from a **different** system:

- **GEDAC** (preinscription) brings in **applicants** — people who don't have a place at the centre yet, or current students changing study.
- **Esfera (SAGA)** — this guide — refreshes **already-enrolled students'** data: personal details, address, documents and family contacts, from the centre's official record in the Catalan education administration's system.

For a smaller, ad-hoc update from any other CSV file (not the official Esfera format, and unable to create new students), see [Updating student data from a CSV file](student-update-csv.md) instead.

## Running the import

From the **Students** list, open the actions menu (the gear icon ⚙️ next to the list) and choose **Import from Esfera**. Select the `.xlsx` file exported from Esfera/SAGA and click **Import students**.

## What gets created or updated

- **Students** are matched by their **RALC** identifier (the student's official Catalan ID). An existing match is updated in place; if it belonged to a former student (alumni/withdrawal), it is **reactivated** as an active student rather than creating a duplicate.
- **Family contacts** (tutors/guardians) are matched by their document number (DNI/NIE/passport) — matched contacts are updated, unmatched ones are created. A tutor row with **no document number on file** always creates a new contact rather than being matched to an existing one; if the same undocumented tutor appears in a later import, expect a second contact rather than an update. Merge duplicates by hand from **Contacts → Families** if this happens.
- **Family relationship** (mother, father, grandparent, sibling, legal guardian…) is guessed from a free-text note in the file. When it can't be confidently guessed, the tutor is linked as a generic "Tutor" and a note is added to the **student's own record** quoting the original text — worth a quick check afterwards for anyone flagged this way.
- A student whose **group code** in the file doesn't match any group in EMS is still imported (with no group assigned) — a note naming the unmatched code is added to their record so it can be corrected by hand.

## Reading the result and the log

After the import, the wizard shows how many students were **created**/**updated**, and lists any rows that raised an error (one bad row never blocks the rest of the file — it's just reported and skipped). A downloadable **CSV log** lists every student and family contact touched by that specific run, with what was linked to what — useful for spot-checking a large import.

## Things to check afterwards

- Any note left by the "unmatched group code" or "guessed relationship" cases above.
- New family contacts created without a document number, in case the same person already existed under a slightly different prior import.

---

[← Back to Secretariat index](index.md)
