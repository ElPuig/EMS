[Català](../../ca/admin/curriculum-levels.md) | [Castellano](../../es/admin/curriculum-levels.md) | [English](curriculum-levels.md)

---

# Levels

Levels represent the different **educational stages** or **study cycles** of the institution (e.g., Secondary Education, VET, Baccalaureate). They form the top of the curriculum hierarchy: each Level groups related Studies, which in turn group Class Groups.

**Required role:** Administrator

---

## Access

Navigate to: **Educational Community → Configuration → Curriculum → Levels**

---

## View All Levels

Opening the menu shows a list of all levels sorted alphabetically by acronym. Each row displays the acronym and the full name.

---

## Create a Level

1. Click **New**.
2. Fill in the required fields:
   - **Acronym** *(required)*: Short code used across the system (e.g., `BTX`, `CFGM`).
   - **Name** *(required)*: Full descriptive name (e.g., `Batxillerat`, `Cicles Formatius Grau Mitjà`).
3. Optionally, add free-form notes in the **Notes** tab.
4. Click **Save** (or use the breadcrumb to navigate away — Odoo saves automatically).

> The **Studies** tab shows all studies linked to this level. Studies are managed from their own menu (**Configuration → Curriculum → Studies**) and cannot be added directly from the level form.

---

## Edit a Level

1. Open the level from the list.
2. Click any field to edit it inline, or click **Edit** if required.
3. Make your changes.
4. Click **Save**.

---

## Delete a Level

1. Select the level in the list (tick the checkbox on the left).
2. Click the **Action** menu (⚙) and select **Delete**.
3. Confirm the deletion in the dialog.

> **Warning:** A level cannot be deleted if it has linked studies. You must first delete or reassign all studies associated with it.

---

[← Back to Administrator index](index.md)
