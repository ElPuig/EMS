# EMS — Educational Management System

An open-source Odoo v18 module for managing an educational centre. Developed by teachers at Institut Puig Castellar (Santa Coloma de Gramenet, Barcelona) as part of the Quality and Continuous Improvement Project (Q&CIP).

## Tech stack

- **Backend:** Odoo v18, Python 3
- **Frontend:** OWL (Odoo Web Library), XML views, JavaScript
- **Database:** PostgreSQL — database name is `ems`
- **Official reference:** https://www.odoo.com/documentation/18.0/ (always consult before making technical decisions)

## Module structure

```
models/
├── attendance/       # Attendance tracking and sessions
├── communications/   # Internal communications
├── contacts/         # Students, groups, enrolments, portal access
├── curriculum/       # Level → Study → Subject → Content hierarchy
├── documentation/    # Minutes and records
├── employees/        # Teachers, roles, working schedules
├── enrollment/       # Enrolment process, templates, payments
├── facilities/       # Spaces and space types
├── grades/           # Grade outcomes
├── limesurvey/       # LimeSurvey integration
├── planning/         # Planning and outcomes
├── settings/         # Company, course, and general settings
└── shared/           # Base mixins and utilities

views/                # XML views organised by model area
static/
├── src/              # Production assets (backend, frontend, scss)
└── tests/            # Test-only assets
    └── tours/        # Browser tour JS files (web.assets_tests)
tests/                # Python test cases
docs/                 # Trilingual user and developer documentation
```

## Development scripts

Both scripts must be run from the project root (`/root/myModules/ems/`).

```bash
./upgrade.sh              # Apply module changes to the running instance
./test.sh                 # Run all EMS tests
./test.sh TestClassName   # Run a specific test class
```

`upgrade.sh` and `test.sh` both stop the Odoo service, run their operation as the `odoo` system user, and restart the service. Output is filtered to show only relevant lines (errors, warnings, test results).

After any change, run `upgrade.sh` and check for WARNING / ERROR / CRITICAL output.

## Testing conventions

**Backend tests** — `tests/test_<model>.py`, using `odoo.tests.common.TransactionCase`:
- Cover: valid create, required fields, display_name, admin CRUD, role access restrictions, relation integrity.
- Use `assertRaises(Exception)` for DB-level violations (Odoo's `assertRaises` does not accept exception tuples).
- Use unique codes/acronyms in test data that do not conflict with production data (ESO, BTX, CFGM, CFGS, EFPS, CFGB, PFI already exist).

**Browser (tour) tests** — `static/tests/tours/<model>_tour.js` + `tests/test_<model>_tour.py`:
- Tours use `registry.category("web_tour.tours").add(...)`.
- Navigate to the target via `url: "/odoo/action-ems.<action_id>"` — do not chain menu-click steps.
- Verify data in the list view after save, not via `input[value=...]` (OWL does not sync the HTML attribute).
- Register in `__manifest__.py` under `web.assets_tests`.
- Python side: `@tagged('post_install', '-at_install')`, `self.start_tour("/odoo", "tour_name", login="admin")`.
- To watch a tour run in a real browser during development: add `watch=True` to `start_tour`.

## Coding standards

Follow the official Odoo v18 coding guidelines:
https://www.odoo.com/documentation/18.0/contributing/development/coding_guidelines.html

Key rules applied in this project:
- Class names: PascalCase derived from `_name` (`ems.level` → `EmsLevel`).
- `from odoo import api, fields, models` — alphabetical order.
- Model attribute order: private attrs (`_name`, `_description`, `_order`, `_sql_constraints`) → fields → compute/inverse/search methods → constraints/onchange → CRUD overrides → action methods → business methods.
- Loop variable named after the model, not `rec` (`for level in self:`).
- XML `<record>`: `id` attribute before `model`.
- f-strings instead of `%s` formatting.
- **DRY, both server (Python) and client (JS):** never duplicate code. Reuse existing methods, extend them, or extract a new shared method/RPC call instead of copy-pasting logic.
- **"Odoo way" first:** don't build a custom solution unless strictly necessary. Always check the official Odoo v18 documentation and existing Odoo/EMS patterns for a built-in mechanism before writing bespoke code.
- Resulting code must be clean, simple, non-redundant, and well-refactored.
- **All literals must be translatable:** wrap every user-facing string for translation (`_("...")` in Python, `_t("...")` in JS/OWL) so it can be picked up by the i18n files, with English as the default/source language. Wrapping is only step one — it makes a string *translatable*, it does not translate it. Every new feature must also add the actual Catalan/Spanish entries to `i18n/ca_ES.po` and `i18n/es_ES.po` before it's considered done (see the "Close" step of the New feature workflow below). To find what's missing: export current terms with `odoo -d ems --i18n-export=<path>.po -l ca_ES --modules=ems --stop-after-init` (repeat for `es_ES`), diff msgids against the checked-in `.po` files, and append translated blocks for the new ones only (don't regenerate/replace the whole file — order doesn't matter to gettext, and the files may already carry unrelated pre-existing gaps that aren't your task's responsibility). Run as the `odoo` user with a path it can write to (not a sandboxed/restricted directory). Do not insert decorative section-header comments between po entries — a comment block with no following `msgid` breaks Odoo's po parser on load.

## Documentation structure

Trilingual: English (`docs/en/`), Catalan (`docs/ca/`), Spanish (`docs/es/`).

```
docs/
├── assets/            # Shared images (all languages reference this)
│   ├── families/
│   └── tutors/
├── en/
│   ├── admin/         # Administrator user guides
│   ├── developers/    # Technical docs with Mermaid diagrams (English only)
│   ├── families/
│   ├── head_of_studies/  # Head of Studies / Deputy / Director user guides
│   ├── secretary/
│   ├── teachers/
│   └── tutors/
├── ca/  (same structure, minus developers/)
└── es/  (same structure, minus developers/)
```

Folder names are always in English regardless of the language tree (`teachers/`, not `professors/`; `secretary/`, not `secretaria/`), so paths stay consistent across `en/`, `ca/` and `es/` — only the file contents and index labels are translated.
```

Image references in markdown use relative paths: `../../assets/<section>/filename.png`

## Data folder conventions

The `data/` directory has three subfolders with different ID ownership semantics:

| Folder | ID prefix | Owned by | Survives EMS upgrade? |
|--------|-----------|----------|-----------------------|
| `data/main/` | `ems.` | EMS module | No — Odoo deletes on upgrade if removed from manifest |
| `data/cat/` | `ems.` | EMS module | No |
| `data/custom/` | `__import__.` | The centre (not EMS) | Yes — Odoo never deletes `__import__` records during module upgrades |

**Rule:** every record `id` in `data/custom/` must use the `__import__.` prefix. Records in `data/main/` and `data/cat/` must use `ems.` (or no prefix, which Odoo expands to `ems.` automatically).

**Why `__import__`?** When Odoo stores a record with a fully-qualified ID whose module part is `__import__`, it is not associated with any installable module. This means removing the corresponding line from the manifest — or upgrading EMS — will never cause Odoo to delete that record. This is the same behaviour as data imported via the Odoo UI CSV importer, which also assigns `__import__.*` IDs.

**Load order:** within `data/custom/`, always list files so that referenced records are declared before the files that reference them (e.g. `ems.subject.csv` before `ems.study.csv`).

## Migrations

Any change that alters or renames something Odoo identifies by **XML ID** — records, fields backing a reified view, etc. — on an environment where that XML ID may already exist in production (i.e. it isn't brand new in this branch) must ship with a migration script under `migrations/<version>/{pre,post}-migrate.py`, following the existing examples in that folder (e.g. `migrations/18.0.0.18.0/pre-migrate.py`, which renames `ems.level` view/action/menu XML IDs via `UPDATE ir_model_data`).

**Why:** renaming an XML ID in the source (e.g. `security/groups.xml`'s `<record id="group_admin">` → `<record id="group_academic_admin">`) without a matching migration means Odoo won't find the old ID on upgrade, creates a brand-new record for the new ID, and can leave the original record — along with any data attached to it in production (e.g. a `res.groups` with real users assigned) — orphaned or deleted. Applying the fix by hand in one environment (e.g. via `odoo shell`, as done for `group_admin` → `group_academic_admin`) does **not** carry over to other environments; production still needs the migration script to apply the same fix when it upgrades.

**How to apply:** before renaming/removing an XML ID, check whether it already exists in the target production database (assume yes unless the record was introduced earlier in the same unreleased branch). If so, add a `pre-migrate.py` under `migrations/<manifest version>/` that renames it at the DB level (`UPDATE ir_model_data SET name = '<new>' WHERE module = 'ems' AND name = '<old>'`) before the module's data files reload. Use `pre-migrate` (not `post-migrate`) so the rename happens before Odoo's data loader tries to resolve the new ID. Never bump the manifest version yourself to create the migration folder — per the rule above, propose it and wait for user go-ahead first.

## DTON cleaning methodology

A retroactive code quality process applied model by model:

1. **D — Diagrams:** Technical docs in English (`docs/en/developers/`) with Mermaid diagrams; user docs in all three languages (`docs/{en,ca,es}/admin/`).
2. **T — Testing:** Backend `TransactionCase` tests + browser tour test.
3. **O — Optimization:** `_order`, `_sql_constraints`, view fixes, computed field guards, refactoring, cleaner and simple code.
4. **N — Normalization:** Apply Odoo v18 official coding guidelines.

Run the full test suite after O and again after N to gate each phase.

## New feature workflow (TDD + DTON)

DTON above is the retroactive process; this is how new models/features should be built so that they arrive already DTON-compliant instead of needing a cleanup pass later. It is TDD's Red-Green-Refactor cycle, with D/O/N slotted into it — no separate process to remember:

1. **Spec (before Red) — D:** Before any test or code, stub `docs/en/developers/<area>/<model>.md` (Mermaid diagram of hierarchy/relations, CRUD flow, access-control table) and `docs/{en,ca,es}/admin/<model>.md`. This stub is the acceptance criteria for the cycle below.
2. **Red — T:** Write `tests/test_<model>.py` (`TransactionCase`) and, if applicable, the tour (`static/tests/tours/<model>_tour.js` + `tests/test_<model>_tour.py`) before the model exists. `./test.sh` must fail.
3. **Green — T:** Write the minimum code to pass: `models/<area>/<model>.py`, `security/ir.model.access.csv` (+ `security/rules/*.xml` if needed), `views/<area>/<model>/{form,list,menu}.xml`, manifest bump. `./test.sh` must pass.
4. **Refactor — O + N:** In the same cycle, not as a later pass: add `_order`, `_sql_constraints`, computed field guards, view fixes (O); apply the Odoo v18 coding guidelines from the "Coding standards" section above — model attribute order, alphabetical imports, f-strings, loop variable naming, translatable literals (N).
5. **Gate:** `./upgrade.sh` and `./test.sh` after each Red-Green-Refactor cycle.
6. **Close — D:** Fill in the three admin doc translations, add the new strings' real Catalan/Spanish translations to `i18n/ca_ES.po` and `i18n/es_ES.po` (see "All literals must be translatable" above — wrapping in `_()`/`_t()` during Green/Refactor is not enough on its own), and reconcile the developer doc's diagram if the implementation diverged from the initial spec during the cycle.
