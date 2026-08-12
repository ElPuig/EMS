[Català](../../ca/admin/curriculum-studies.md) | [Castellano](../../es/admin/curriculum-studies.md) | [English](curriculum-studies.md)

---

# Studies

Studies represent the **concrete study programmes** offered by the institution (e.g., DAM, DAW, ASIX). Each study belongs to one Level and groups the Subjects that make it up, together with its official curriculum documents.

**Required role:** Administrator

---

## Access

Navigate to: **Educational Community → Configuration → Curriculum → Studies**

---

## View All Studies

Opening the menu shows a list of all studies sorted by code. Each row shows the code, acronym and name.

---

## Create a Study

1. Click **New**.
2. Fill in the required fields:
   - **Acronym** *(required)*: Short code used across the system (e.g., `DAM`, `DAW`).
   - **Name** *(required)*: Full descriptive name.
   - **Level** *(recommended)*: The educational level this study belongs to.
   - **Code** *(required)*: Official code, must be unique (e.g., `CFGS_ICB0`).
   - **Release Date** *(required)*: Date the curriculum was published.
   - **Deprecated**: Leave unchecked for an active study; check it to retire a study without deleting it.
3. In the **Subjects** tab, add the subjects that make up this study.
4. In the **Attached files** tab, attach curriculum reference documents (official gazette publications, guidance documents, etc.).
5. Optionally, add free-form notes in the **Notes** tab.
6. Click **Save** (or use the breadcrumb to navigate away — Odoo saves automatically).

---

## Edit a Study

1. Open the study from the list.
2. Click any field to edit it inline, or click **Edit** if required.
3. Make your changes.
4. Click **Save**.

---

## Retire a Study

Studies are rarely deleted, since doing so is blocked once other records (enrolments, groups, grades) reference them. To stop offering a study while keeping its history:

1. Open the study.
2. Check the **Deprecated** field.
3. Click **Save**.

---

## Delete a Study

1. Select the study in the list (tick the checkbox on the left).
2. Click the **Action** menu (⚙) and select **Delete**.
3. Confirm the deletion in the dialog.

> **Warning:** A study cannot be deleted if it has linked records elsewhere in the system (enrolments, groups, planning...). Use **Deprecated** instead in that case.

---

[← Back to Administrator index](index.md)
