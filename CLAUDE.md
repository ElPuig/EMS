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

**Email safety in tests:** this environment's `ir.mail_server` table can point to real, credentialed outgoing servers (e.g. AWS SES, Gmail). Odoo's test runner does **not** suppress real SMTP delivery on its own — `mail.mail.send()` attempts a genuine connection/send even during `TransactionCase`/`HttpCase` tests, regardless of `--test-enable`. Any test whose code path can trigger an email (`send_mail(..., force_send=True)`, `message_post()` with followers, a cron/queue_job send invoked synchronously, etc.) must neutralize real delivery — never let a test send to an address read from seed/production data, since it could be a real person's mailbox. Two options, in order of preference:
- **Default — mock the transport:** patch `odoo.addons.base.models.ir_mail_server.IrMailServer.send_email` (e.g. `unittest.mock.patch(...).start()` + `cls.addClassCleanup(...)` in `setUpClass`) so the full recipient-resolution/template logic still runs and stays assertable, but no network call happens. See `tests/test_strike.py`/`tests/test_strike_tour.py` for the pattern. Use only fictitious addresses (`@example.com` or similar) in test fixtures.
- **Only if explicitly requested by the developer:** if a real send is genuinely needed (e.g. to visually verify formatting), do not use an address read from the database — require an explicit, authorized address from the developer (their own inbox, a designated test mailbox) passed in for that run, and confirm with them before sending.

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

There are **two distinct categories** of documentation, for two different audiences — every new feature needs both, they are not alternatives:

- **Technical documentation** (`docs/en/developers/`): for developers reading the code. English only. Mermaid diagrams of hierarchy/relations, CRUD flow, access-control tables.
- **User documentation** (`docs/{en,ca,es}/<role>/`): manuals for the people who actually operate the feature in the running app — one folder per role (`admin`, `teachers`, `tutors`, `secretary`, `head_of_studies`, `families`). Trilingual: every user doc needs a Catalan, Spanish and English version. A single feature can need more than one role's manual (e.g. a teacher-facing screen plus the admin config behind it) — see the New feature workflow below for how to identify which roles apply.

Trilingual tree: English (`docs/en/`), Catalan (`docs/ca/`), Spanish (`docs/es/`).

```
docs/
├── assets/            # Shared images (all languages reference this)
│   ├── families/
│   └── tutors/
├── en/
│   ├── admin/         # [USER doc] Administrator manuals
│   ├── developers/    # [TECHNICAL doc] Mermaid diagrams, CRUD flow, access-control tables (English only)
│   ├── families/      # [USER doc] Family/student manuals
│   ├── head_of_studies/  # [USER doc] Head of Studies / Deputy / Director manuals
│   ├── secretary/      # [USER doc] Secretariat manuals
│   ├── teachers/       # [USER doc] Teacher manuals
│   └── tutors/         # [USER doc] Group tutor manuals
├── ca/  (same structure, minus developers/ — user docs only, no technical docs in Catalan)
└── es/  (same structure, minus developers/ — user docs only, no technical docs in Spanish)
```

Folder names are always in English regardless of the language tree (`teachers/`, not `professors/`; `secretary/`, not `secretaria/`), so paths stay consistent across `en/`, `ca/` and `es/` — only the file contents and index labels are translated.

Image references in markdown use relative paths: `../../assets/<section>/filename.png`

## Data folder conventions

The `data/` directory has three subfolders with different ID ownership semantics:

| Folder | ID prefix | Owned by | Survives EMS upgrade? |
|--------|-----------|----------|-----------------------|
| `data/main/` | `ems.` | EMS module | No — Odoo deletes on upgrade if removed from manifest |
| `data/cat/` | `ems.` | EMS module | No |
| `data/custom/` | `__import__.` | The centre (not EMS) | Yes — Odoo never deletes `__import__` records during module upgrades |

**Rule:** every record `id` in `data/custom/` must use the `__import__.` prefix. Records in `data/main/` and `data/cat/` must use `ems.` (or no prefix, which Odoo expands to `ems.` automatically).

**Exception — overriding a native Odoo record:** when a `data/custom/` record's `id` deliberately matches the XML ID of a record already shipped by a native Odoo module (e.g. `hr.dep_administration`, the default "Administration" department from the `hr` module, deactivated in `data/custom/hr.department.csv` instead of replaced), keep that module's own prefix (`hr.`, `base.`, etc.) instead of `__import__.`. Using `__import__.` there would create a *new* record instead of overriding the existing one.

**Exception — extending a `data/cat/` record with centre-specific data:** when a `data/custom/` record deliberately reuses the exact `ems.*` id of a record already declared in `data/cat/` to attach centre-specific data to it (e.g. `data/custom/ccff/ems.study.csv` re-declares `ems.study_cfgs_icb0_dam_2024` — already defined in `data/cat/ems.study.csv` — solely to add the centre's own optional subjects to `subject_ids`), keep the `ems.` prefix instead of `__import__.`. This is intentional: it's the same underlying record, updated in place, not a new one — every `ems.planning.*` file's `study_id` ref still needs to resolve to that single shared record. Using `__import__.` there would fork it into two disconnected studies. Only reuse an `ems.*` id like this when the intent really is "extend the shared `data/cat` record in place"; a `data/custom/` record that happens to duplicate `data/cat` content verbatim (not extending it, just repeating it) is a bug, not this exception — consolidate into one file instead (see the `product.category.csv` history in this repo for an example fix).

These two exceptions are the only cases where a non-`__import__.` prefix in `data/custom/` is correct — everywhere else it's a bug.

**Why `__import__`?** When Odoo stores a record with a fully-qualified ID whose module part is `__import__`, it is not associated with any installable module. This means removing the corresponding line from the manifest — or upgrading EMS — will never cause Odoo to delete that record. This is the same behaviour as data imported via the Odoo UI CSV importer, which also assigns `__import__.*` IDs.

**Hard limitation — `__import__.` only works in CSV, not XML `<record>` tags:** Odoo's XML data loader (`odoo/tools/convert.py::_test_xml_id`) unconditionally rejects any `<record id="module.name">` whose module isn't an *actually installed* Odoo module, and `__import__` never is — this raises `AssertionError: The ID "__import__.xxx" refers to an uninstalled module` and aborts the entire file's load. `__import__` is only accepted by the CSV/`load()` import path (`odoo/models.py`), which is why the UI CSV importer and CSV data files can use it but a `data/custom/*.xml` file cannot. There is no XML-side workaround — a `data/custom/` model currently declared via XML (e.g. `ems.planning`, `ems.authorization.template`, `ems.course`) can only get real `__import__.` ids by converting that file to CSV (straightforward for flat models; needs a separate related CSV file, not inline `eval=`, for one2many data like `ems.planning`'s `planning_outcome_ids`). Don't attempt `id="__import__.xxx"` in a `<record>` tag — verify with `./upgrade.sh` after any id-prefix change in `data/custom/`.

**Load order:** within `data/custom/`, always list files so that referenced records are declared before the files that reference them (e.g. `ems.subject.csv` before `ems.study.csv`).

## Migrations

Any change that alters or renames something Odoo identifies by **XML ID** — records, fields backing a reified view, etc. — on an environment where that XML ID may already exist in production (i.e. it isn't brand new in this branch) must ship with a migration script under `migrations/<version>/{pre,post}-migrate.py`, following the existing examples in that folder (e.g. `migrations/18.0.0.18.0/pre-migrate.py`, which renames `ems.level` view/action/menu XML IDs via `UPDATE ir_model_data`).

**Why:** renaming an XML ID in the source (e.g. `security/groups.xml`'s `<record id="group_admin">` → `<record id="group_academic_admin">`) without a matching migration means Odoo won't find the old ID on upgrade, creates a brand-new record for the new ID, and can leave the original record — along with any data attached to it in production (e.g. a `res.groups` with real users assigned) — orphaned or deleted. Applying the fix by hand in one environment (e.g. via `odoo shell`, as done for `group_admin` → `group_academic_admin`) does **not** carry over to other environments; production still needs the migration script to apply the same fix when it upgrades.

**How to apply:** before renaming/removing an XML ID, check whether it already exists in the target production database (assume yes unless the record was introduced earlier in the same unreleased branch). If so, add a `pre-migrate.py` under `migrations/<manifest version>/` that renames it at the DB level (`UPDATE ir_model_data SET name = '<new>' WHERE module = 'ems' AND name = '<old>'`) before the module's data files reload. Use `pre-migrate` (not `post-migrate`) so the rename happens before Odoo's data loader tries to resolve the new ID. Never bump the manifest version yourself to create the migration folder — per the rule above, propose it and wait for user go-ahead first.

## DTON cleaning methodology

A retroactive code quality process applied model by model:

1. **D — Diagrams:** Technical docs in English (`docs/en/developers/`) with Mermaid diagrams; user docs in all three languages, one file per role that actually interacts with the feature (`docs/{en,ca,es}/<role>/`, where `<role>` is `admin`, `teachers`, `tutors`, `secretary`, `head_of_studies` or `families` — not only `admin/`; a feature can be relevant to more than one role and then needs a doc file under each).
2. **T — Testing:** Backend `TransactionCase` tests + browser tour test.
3. **O — Optimization:** `_order`, `_sql_constraints`, view fixes, computed field guards, refactoring, cleaner and simple code.
4. **N — Normalization:** Apply Odoo v18 official coding guidelines.

Run the full test suite after O and again after N to gate each phase.

## New feature workflow (TDD + DTON)

DTON above is the retroactive process; this is how new models/features should be built so that they arrive already DTON-compliant instead of needing a cleanup pass later. It is TDD's Red-Green-Refactor cycle, with D/O/N slotted into it — no separate process to remember:

1. **Spec (before Red) — D:** Before any test or code, stub `docs/en/developers/<area>/<model>.md` (Mermaid diagram of hierarchy/relations, CRUD flow, access-control table). From that access-control table, identify **every role that will actually use the feature** (`admin`, `teachers`, `tutors`, `secretary`, `head_of_studies`, `families` — a feature is frequently relevant to more than one, e.g. a teacher-facing grading screen plus an admin config screen) and stub one `docs/{en,ca,es}/<role>/<model>.md` per role identified, not just `admin/`. These stubs are the acceptance criteria for the cycle below.
2. **Red — T:** Write `tests/test_<model>.py` (`TransactionCase`) and, if applicable, the tour (`static/tests/tours/<model>_tour.js` + `tests/test_<model>_tour.py`) before the model exists. `./test.sh` must fail.
3. **Green — T:** Write the minimum code to pass: `models/<area>/<model>.py`, `security/ir.model.access.csv` (+ `security/rules/*.xml` if needed), `views/<area>/<model>/{form,list,menu}.xml`, manifest bump. `./test.sh` must pass.
4. **Refactor — O + N:** In the same cycle, not as a later pass: add `_order`, `_sql_constraints`, computed field guards, view fixes (O); apply the Odoo v18 coding guidelines from the "Coding standards" section above — model attribute order, alphabetical imports, f-strings, loop variable naming, translatable literals (N).
5. **Gate:** `./upgrade.sh` and `./test.sh` after each Red-Green-Refactor cycle.
6. **Close — D:** For every role identified in the Spec step, fill in the three language versions of that role's user doc (`docs/{en,ca,es}/<role>/<model>.md`) — this is a mandatory deliverable of every new feature, not an optional extra to be requested separately; skipping it because the feature "isn't for admins" is the most common way this step gets missed. Also update the role's `index.md` to link the new manual. Add the new strings' real Catalan/Spanish translations to `i18n/ca_ES.po` and `i18n/es_ES.po` (see "All literals must be translatable" above — wrapping in `_()`/`_t()` during Green/Refactor is not enough on its own), and reconcile the developer doc's diagram if the implementation diverged from the initial spec during the cycle.
