# Technical Reference: `ems.student_import_wizard`

## Overview

Bulk-imports/updates student and family-contact records from an **Esfera (SAGA)** xlsx export — the Catalan education administration's official system of record for already-enrolled students. Not to be confused with the GEDAC **preinscription** import (`ems.applicant_import_wizard`, documented separately): Esfera/SAGA is a different source system, covering students already admitted, not applicants.

**Module file:** `models/contacts/student_import_wizard.py` (`EmsStudentImportWizard`)

**Entry point:** a **cog-menu item** ("Import from Esfera") on the Students list/kanban view — not a `<menuitem>`. See `static/src/js/backend/import_student_cog_menu.js`: it registers into Odoo's `cogMenu` registry and is only shown when the current action is `ems.menu_students`' own action and the view isn't a form (`isDisplayed`, checked against the *action*, not the current *user's group* — the wizard's own `ir.model.access.csv`/action `groups_id` is what actually enforces admin/secretary-only, the cog menu item itself doesn't hide for other roles).

---

## Import flow

```mermaid
flowchart TD
    A["action_import()"] --> B["decode xlsx, load with openpyxl"]
    B --> C["_find_headers() — scan first 20 rows\nfor a 'Grup Classe' column"]
    C -->|not found| X1["UserError"]
    C --> D["_check_required_columns()\n— 35 required headers +\n2 trailing-space variants"]
    D -->|missing| X2["UserError, lists them"]
    D --> E["for each data row:\n_process_row(), wrapped in try/except"]
    E -->|exception| F["append to stats.errors,\ncontinue with next row"]
    E --> G["_get_or_create_student()"]
    G --> H["_process_tutor() × 2\n(Tutor 1, Tutor 2)"]
    H --> I["_build_log_csv() + _build_result_html()"]
```

One row failing (a raised exception anywhere in `_process_row`) does **not** abort the batch — it's logged into `stats['errors']` and the loop continues, so a single malformed row can't block importing the rest of the file.

### Column mapping — `_col_get`

`_process_row`/`_process_tutor` each locally re-declared an identical `get(col_name)` closure before this DTON pass (2026-07-28) — deduplicated into `_col_get(row, col_map, col_name)`. Looks up a column by its **exact Esfera header text** in `col_map` (built once by `_find_headers`), returns `None` if the column doesn't exist in this particular file or the cell is empty for this row.

### Student upsert — `_get_or_create_student`

Matched by `student_id` (RALC, the Catalan student identifier), searched with `active_test=False` — re-importing after a withdrawal (which archives the contact, see [Graduation & withdrawal wizards](exit_wizards.md)) **reactivates** the same record with `active: True` rather than creating a duplicate. This is the one piece of the wizard with dedicated `TransactionCase` coverage from before this DTON pass (create/update/reactivate).

### Tutor upsert — `_process_tutor` / `_get_or_create_family` / `_deduce_relation_type`

Up to 2 tutors per row (`Tutor 1`/`Tutor 2` column prefixes). For each: parse name/document/contact/address columns, resolve or create a `contact_type='family'` partner, guess the family relationship from a free-text observation column via keyword matching (`_deduce_relation_type`: mare/madre → mother, pare/padre → father, àvia/avia/abuela → grandmother, etc.), defaulting to the generic "Tutor" relation type when no keyword matches — in that fallback case a note is appended to the **student's** own `comment` field quoting the original free text, so a secretary can review and correct the guess later.

---

## Known limitations (flagged, not fixed in this pass)

- **Family dedup only matches by document number.** `_get_or_create_family` searches existing `family` contacts by `document_id`/`passport_id` only; a tutor row with **no document number** always creates a new partner. Re-importing the same file for an undocumented tutor creates one duplicate family contact per run. Locked in by `test_get_or_create_family_without_document_always_creates_new` so a future fix is a deliberate decision, not an accidental behavior change caught by surprise.
- **A group code that doesn't match any `ems.group.external_id` fails silently** into the student's `comment` notes (`"Grup Classe (SAGA): <code>"`) rather than into `stats['errors']` — the row still succeeds (student created/updated without a group), so a renamed/typo'd Esfera group code is only visible if someone reads the notes field afterward, not from the import summary counts.
- **Country/state matching is `ilike` on the translated name** (`_find_country`/`_find_state`, forced `lang='ca_ES'`), `limit=1` with no disambiguation — fragile against accents/synonyms and could in principle match the wrong same-named state across different countries (mitigated for state by the `country_id` filter, not for country itself).
- **`_deduce_relation_type` resolves `env.ref` without `raise_if_not_found=False`** — if any of the 7 `ems.relation_type_*` XML IDs were ever renamed, every tutor row would raise. Degrades gracefully today only because the outer `action_import` loop already catches per-row exceptions — not a crash, just an unusually large error list.

## Fixed in this pass (2026-07-28)

- **`_build_result_html` now escapes error content.** It used to interpolate `stats['errors']` (stringified exceptions, which can echo raw row data) directly into HTML with no escaping — a latent HTML-injection risk into an admin-only readonly field. Now built with `markupsafe.Markup(...).format(...)`, which auto-escapes any plain-`str` argument (see `test_build_result_html_escapes_error_content`).
- **The `openpyxl is required to import xlsx files.` `UserError` was the only one of its 3 call sites (this wizard, `applicant_import_wizard.py`, `grade_import_wizard.py`) not wrapped in `_()`** — fixed; the existing `ca_ES`/`es_ES` translations (already present for the other two call sites) needed only a new `#:` reference added, not new translation text.
- Class renamed `ems_student_import_wizard` → `EmsStudentImportWizard` (zero external coupling — grepped clean).
- All `%`-style string formatting converted to f-strings (or, for `_()`-wrapped strings, to the project's named-placeholder convention).

**Deliberately NOT translated**: the note-building labels in `_build_student_notes`/`_process_tutor` (e.g. `"Província de naixement"`, `"Alumne tutelat legalment"`) stay in literal Catalan even though they end up in a user-visible `comment` field. They are a verbatim echo of Esfera/SAGA's **own** official Catalan field names — translating them would weaken the ability to trace a note back to exactly what the source system exported for that student. Same reasoning for the CSV log's column headers (`_build_log_csv`) — an internal operational log, not app UI chrome.

---

## Access Control

`ir.model.access.csv`: `ems.group_academic_admin`/`ems.group_secretary` only. The `action_student_import_wizard` window action additionally sets `groups_id` to the same two groups — belt-and-braces with the cog-menu item's own lack of group-awareness noted above.

---

## Views

| View | File | Notes |
|------|------|-------|
| Form | `views/community/contact/import_wizard.xml` (`view_student_import_wizard_form`) | Explanatory panel → file picker → (after import) result summary + downloadable CSV log via `auto_download_binary` |
| Action | same file | `action_student_import_wizard`, no standalone menu — see the cog-menu entry point above |
