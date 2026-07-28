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
plans/                # Design plans for not-yet-implemented work (see "Design plans" below)
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

**The full test suite is slow — don't run it more than necessary.** `./test.sh` (no argument) runs every test class and takes several minutes; running it after every small change wastes time without adding useful signal. Prefer `./test.sh TestClassName`, scoped to whatever model(s) you're actually touching, as the normal gate during iterative work (Red/Green/Refactor cycles, DTON phases, bug fixes). Run the full, unscoped `./test.sh` only once — as the final check before considering a piece of work done — not after every intermediate step. If a change plausibly affects other models (e.g. a shared mixin, a migration, a widget used in several views), scope down to the smallest set of `TestClassName` runs that actually covers the blast radius instead of reaching for the full suite by default.

**If a test run seems to hang with no output, refresh any browser tab you have open on the Odoo backend.** `--test-enable` spins up a real HTTP server for the duration of any `HttpCase`/tour test (e.g. `test_grade_session_tour`, `test_level_tour`, `test_strike_tour` — pulled in by the full, unscoped `./test.sh`, or by name if you target one directly). Odoo's teardown (`_wait_remaining_requests` in `odoo/tests/common.py`) waits for every open HTTP request against that server to finish before the process can exit — including a stray long-polling (bus) connection from an already-open browser tab pointed at the same host/port, which is designed to never close on its own. Refreshing (no need to close) that tab severs the stale connection and lets the run finish. Scoped runs of test classes with no tour/`HttpCase` tests don't hit this specific hang, but closing/refreshing before *any* `./test.sh` run is the standing habit regardless (see the notification trigger below, which fires for every run, not just tour ones).

**Notifications for this developer are handled entirely by an already-built host-side file-drop bridge — never call the `PushNotification` tool on this project.** It proved unreliable in this container/VSCode-extension setup (silently self-suppresses as "terminal active," no mobile push available here) and only adds noise; do not use it for test or completion notifications here, and do not re-attempt Remote Control/DBus approaches — they don't work in this setup and that's settled. The working bridge (`~/claude-notify` on the host ↔ `/mnt/claude-notify` in the container, watched by a `systemd --user` service running `notify-send`) is already built and verified; full rebuild/troubleshooting steps live in `docs/en/developers/tooling/ai_agent_test_notifications.md` — only needed if the bridge itself ever breaks.

Exactly three triggers should ever produce a notification for this developer:
1. **Launching any test** (`./test.sh`, any class — not only tour/`HttpCase` ones), so the developer closes or refreshes their Odoo tab beforehand. This is fully automatic via a `PreToolUse`/`Bash` hook already in the developer's user-level `~/.claude/settings.json`, which writes a trigger file to `/mnt/claude-notify/` on any Bash command containing `test.sh`. No agent action needed — don't duplicate it with anything else.
2. **Finishing all requested work in a task**, so the developer knows to come back and review. There is no Bash command to hook this on ("all done" isn't a tool call), so the agent must write the trigger file itself, right after concluding a task — code changed, tests run, docs/i18n updated, whatever the task actually required.
3. **Blocking on the developer's input before the agent can continue** — an `AskUserQuestion` call, or any chat message that explicitly asks something and then has nothing left to do but wait for the reply. Without a notification here the developer has no way to know the agent stopped *waiting for them* specifically, as opposed to still working — confirmed in practice (2026-07-24): the agent sat idle mid-task waiting on an answer with no notification, and the developer had no way to know that's what was happening. Fire this right when the question is asked (or immediately after, if the question tool itself doesn't allow a preceding action), every time, not just for big/blocking decisions.

For triggers 2 and 3 (no hook can see either coming — "all done" and "asking a question" aren't Bash commands), the agent writes the trigger file itself:
```bash
echo "$(date +%H:%M:%S) EMS: task done — <short summary>" > /mnt/claude-notify/done-$(date +%s%N).txt
echo "$(date +%H:%M:%S) EMS: waiting on you — <short summary of what's being asked>" > /mnt/claude-notify/waiting-$(date +%s%N).txt
```

**Redirect `./test.sh`/`./upgrade.sh` output to a file before inspecting it — never pipe a live run straight into `tail`/`grep` as the only way you look at it.** E.g. `./test.sh TestClassName 2>&1 | tee /path/to/scratchpad/test_output.log`, then `tail`/`grep` against that file for an efficient first pass. Piping directly into `tail`/`grep` on the live command risks silently missing something further up the output, and if that happens the only way to look again is re-running the (slow) run — exactly the redundant-run problem the "don't run the full suite more than necessary" rule above is trying to avoid. With the output already saved to a file, re-reading it (in full, or with a different `tail`/`grep`) costs nothing — only re-run the actual command if the file genuinely doesn't have what's needed (aborted run, or a subsequent code change invalidates it).

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

  **A msgid diff alone is not enough — it misses reused labels.** Odoo's po loader binds a block's `msgstr` to the *exact* `#:` reference lines in that block (`model:ir.model.fields,field_description:ems.field_<model>__<field>`, `model:res.groups,name:ems.<xmlid>`, `model:ir.ui.menu,name:ems.<xmlid>`, `model:mail.template,subject/body_html/name:ems.<xmlid>`, etc.) — never by matching msgid text alone. So when a new field/record's label happens to be a common word already translated for a *different* field (`Teacher`, `Name`, `Active`, `Manager`, `Administrator`, `Configuration`, `Sequence`...), a msgid-only diff reports nothing missing — the text isn't new — yet the new field still renders untranslated, because its own `#:` reference was never added to that existing block. For every new field/model/group/menu/template introduced by the feature: search the checked-in `.po` for its exact label text first; if a block already exists, add your new record's `#:` reference to it (same `msgstr`, no translation work needed) instead of assuming it's already covered; only create a brand-new block if the text itself doesn't exist anywhere yet. **Verify, don't just trust the diff:** after `./upgrade.sh`, spot-check a sample of the new fields/records directly in the DB, e.g. `psql -c "SELECT field_description FROM ir_model_fields WHERE model='<model>' AND name='<field>';"` (or the equivalent column for `ir.model.name`, `ir.ui.menu.name`, `res.groups.name`, `mail.template.name`/`subject`/`body_html`, etc.), and confirm the jsonb value actually has `ca_ES`/`es_ES` keys, not just `en_US`. A `.po` entry existing is necessary but not sufficient — only a DB read proves the reference actually matched.

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

## Design plans (`plans/`)

`plans/` (project root) holds **design plans for work that hasn't been implemented yet** —
e.g. a plan drafted in one session/branch to be executed later in a different one. It is
deliberately separate from `docs/`: it is not documentation of shipped behaviour, it's a
working note that becomes stale/obsolete the moment the described work either lands (at
which point the real `docs/en/developers/` + `docs/{en,ca,es}/<role>/` docs are what's
authoritative — fold anything still relevant from the plan into them and delete the plan
file) or gets superseded by a different approach.

- One file per plan, `plans/<short_topic>.md`, English.
- State at the top whether it's still current: a plan can go stale as the surrounding code
  moves on between when it was written and when someone picks it up — say so explicitly
  rather than letting a reader assume it's up to date.
- Not trilingual, not linked from any `index.md` — it's a working note, not a manual.
- Once the plan is implemented (or abandoned), delete the file rather than leaving a
  stale plan behind — `git log` still has it if anyone needs the history.

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

**Every change must work on both paths: a brand-new clean install and an upgrade of an already-existing installation.** These are two different Odoo code paths and neither implies the other:
- **Clean install** (`-i ems` on a database that has never had EMS): manifest `data`/`demo` files load, then `post_init_hook` (defined in `__init__.py`) runs once. Migration scripts under `migrations/` never run on a clean install — there is no "previous version" to migrate from.
- **Upgrade of an existing install** (`-u ems`, what `./upgrade.sh` runs): `pre-migrate.py`/`post-migrate.py` under `migrations/<version>/` run (only if the module's stored version differs from the manifest's), then `data` files reload. `post_init_hook` does **not** run again on upgrade — it already ran when that installation was first created.
- Any one-time setup action that isn't captured by a versioned data file (e.g. enabling a PostgreSQL extension, backfilling a column, deduplicating rows) needs **both**: the logic in `post_init_hook` for installations created from now on, and the equivalent in a `migrations/<version>/post-migrate.py` (or `pre-migrate.py`, see below) for installations that already exist and will upgrade into this version. Skipping either one means one class of environment silently never gets the fix — see `_backfill_default_schedule_framework`/`_enable_unaccent_extension` in `__init__.py` alongside their `migrations/18.0.0.20.0`, `18.0.0.21.0`, `18.0.0.22.0` `post-migrate.py` counterparts for the established pattern.
- When testing locally, remember `./upgrade.sh` only exercises the upgrade path (this box already has EMS installed) — it never re-runs `post_init_hook`. Verifying the clean-install path requires actually installing on a fresh database (or at minimum, code review confirming the same logic exists in both places).

Any change that alters or renames something Odoo identifies by **XML ID** — records, fields backing a reified view, etc. — on an environment where that XML ID may already exist in production (i.e. it isn't brand new in this branch) must ship with a migration script under `migrations/<version>/{pre,post}-migrate.py`, following the existing examples in that folder (e.g. `migrations/18.0.0.18.0/pre-migrate.py`, which renames `ems.level` view/action/menu XML IDs via `UPDATE ir_model_data`).

**Why:** renaming an XML ID in the source (e.g. `security/groups.xml`'s `<record id="group_admin">` → `<record id="group_academic_admin">`) without a matching migration means Odoo won't find the old ID on upgrade, creates a brand-new record for the new ID, and can leave the original record — along with any data attached to it in production (e.g. a `res.groups` with real users assigned) — orphaned or deleted. Applying the fix by hand in one environment (e.g. via `odoo shell`, as done for `group_admin` → `group_academic_admin`) does **not** carry over to other environments; production still needs the migration script to apply the same fix when it upgrades.

**How to apply:** before renaming/removing an XML ID, check whether it already exists in the target production database (assume yes unless the record was introduced earlier in the same unreleased branch). If so, add a `pre-migrate.py` under `migrations/<manifest version>/` that renames it at the DB level (`UPDATE ir_model_data SET name = '<new>' WHERE module = 'ems' AND name = '<old>'`) before the module's data files reload. Use `pre-migrate` (not `post-migrate`) so the rename happens before Odoo's data loader tries to resolve the new ID. Never bump the manifest version yourself to create the migration folder — per the rule above, propose it and wait for user go-ahead first.

**`pre-migrate.py` vs `post-migrate.py` — know what exists at each point:** `pre-migrate` runs *before* Odoo syncs the module's schema/data for this version (new columns/tables from the model definitions do not exist yet; XML data from `data/`/`views/` has not reloaded yet). `post-migrate` runs *after* — schema and data are already in their new-version state. Concretely:
- A column backing a field **introduced in this same version** does not exist during `pre-migrate` — referencing it there fails with `UndefinedColumn`/`column "..." does not exist`. Any backfill of a new field (e.g. seeding a new required field before Odoo enforces `NOT NULL`) belongs in **`post-migrate`**, never `pre-migrate` — "before the constraint is enforced" refers to Odoo's own internal ALTER TABLE step, which already happens automatically between pre and post; it is not an instruction to run the backfill as early as possible.
- Renaming an **existing** XML ID (the case above) belongs in **`pre-migrate`**, precisely because it must happen before the data loader tries to resolve the new name against old data — the opposite situation from a brand-new field.
- Rule of thumb: if the migration script references a field/column/table that is *new* in this version's models, it goes in `post-migrate`. If it operates on something that already existed before this version (renames, data transforms on pre-existing columns), it goes in `pre-migrate`.
- Test this locally with `./upgrade.sh` from the actual pre-upgrade DB state before shipping — a migration script that only gets exercised for the first time in production is exactly how this class of bug (`migrations/18.0.0.20.0/pre-migrate.py` initially referencing the new `default_schedule_framework_id` column) reached production undetected: the `/deploy-check` dry-run that should have caught it never actually loaded the `ems` module at all due to an unrelated bug in `deploy-check.yml`'s `addons_path` — don't rely on `/deploy-check` alone; a clean upgrade there is not proof the migration scripts ran.

**Merging/rebasing across branches that each add migration scripts:** when two branches developed in parallel each add a `migrations/<version>/{pre,post}-migrate.py`, a naive merge can silently strand one branch's script in an already-released version folder instead of the current unreleased one (exactly what happened when `migrations/18.0.0.20.1/post-migrate.py` was added by a feature branch merged after `18.0.0.20.1` had already been tagged/released — the script would never run on any environment that had already upgraded past that tag). Before finishing any merge that touches `migrations/`: (1) check `git tag` for the most recent released version and confirm every new/changed migration script lives under a version folder *higher* than that tag; (2) if two branches each created their own `migrations/<same-current-version>/{pre,post}-migrate.py`, merge their `migrate()` bodies into one file (e.g. as separate helper functions called from a single `migrate()`) rather than keeping duplicate files or silently dropping one side's script — Odoo only runs one `pre-migrate.py`/`post-migrate.py` per version folder.

## Resolving merge conflicts

When resolving a merge conflict, never pick a side (ours/theirs) blindly. Before resolving each conflicted hunk:

- Inspect the commit tree around the conflict (`git log --graph --oneline` for both branches, `git log <branch>..<other-branch>`, `git diff`/`git show` on the relevant commits) to understand what each side actually changed and why.
- Confirm the resolution keeps every change from both sides that is still relevant — don't silently drop a change just because it's on the losing side of a textual conflict.
- If, after this review, it's still unclear which change should prevail or how to combine them, ask the user instead of guessing.

## DTON cleaning methodology

A retroactive code quality process applied model by model.

**Trigger — don't wait for a dedicated cleanup pass:** whenever a change is requested to an existing model that hasn't had DTON applied yet, apply DTON to that model as part of the same piece of work, not deferred to "later" — a scheduled backlog item is exactly how a model goes untested indefinitely. (This is what happened with `ems.role` and `hr.department`: a color-widget change landed on both without DTON ever having been applied to either, which is exactly how their tour-test gap went unnoticed until a screen broke in production use and had to be caught by hand.) If DTON hasn't been applied yet to a model you're about to touch, apply it — Testing (T) at minimum — before or alongside the requested change.

1. **D — Diagrams:** Technical docs in English (`docs/en/developers/`) with Mermaid diagrams; user docs in all three languages, one file per role that actually interacts with the feature (`docs/{en,ca,es}/<role>/`, where `<role>` is `admin`, `teachers`, `tutors`, `secretary`, `head_of_studies` or `families` — not only `admin/`; a feature can be relevant to more than one role and then needs a doc file under each).
2. **T — Testing:** Backend `TransactionCase` tests + browser tour test. The tour must exercise **every view where the model's data is actually rendered**, not just its own canonical list/kanban/form action — a clean `./upgrade.sh` and passing `TransactionCase` tests only prove the arch loads and the model's logic works; neither renders anything in a browser, so neither catches a client-side (OWL template, widget) crash. Concretely, check for and cover:
   - The model's own primary list/kanban/form views (the ones reachable from its normal menu).
   - Any **secondary view** for the same model reachable only via a different action (e.g. a kanban view inherited/overridden separately from the model's main list+form action) — these are easy to forget precisely because they're not in the model's own menu.
   - Any **other model's view that embeds this model's fields** — a `many2many_tags`/custom widget showing this model's records on a *different* model's form or kanban (e.g. `ems.role` colors rendered as badges on `hr.employee`'s form), a related/computed field surfacing this model's data elsewhere, etc. Grep for the model's name and its fields across `views/` before assuming the model's own screens are the full picture.
3. **O — Optimization:** `_order`, `_sql_constraints`, view fixes, computed field guards, refactoring, cleaner and simple code.
4. **N — Normalization:** Apply Odoo v18 official coding guidelines.

Gate O and N with `./test.sh TestClassName` for the model being cleaned (see "The full test suite is slow" above); run the full, unscoped `./test.sh` once, after N, not after both phases.

## New feature workflow (TDD + DTON)

DTON above is the retroactive process; this is how new models/features should be built so that they arrive already DTON-compliant instead of needing a cleanup pass later. It is TDD's Red-Green-Refactor cycle, with D/O/N slotted into it — no separate process to remember:

1. **Spec (before Red) — D:** Before any test or code, stub `docs/en/developers/<area>/<model>.md` (Mermaid diagram of hierarchy/relations, CRUD flow, access-control table). From that access-control table, identify **every role that will actually use the feature** (`admin`, `teachers`, `tutors`, `secretary`, `head_of_studies`, `families` — a feature is frequently relevant to more than one, e.g. a teacher-facing grading screen plus an admin config screen) and stub one `docs/{en,ca,es}/<role>/<model>.md` per role identified, not just `admin/`. These stubs are the acceptance criteria for the cycle below.
2. **Red — T:** Write `tests/test_<model>.py` (`TransactionCase`) and the tour (`static/tests/tours/<model>_tour.js` + `tests/test_<model>_tour.py`) before the model exists — the tour is the default, not an optional extra; skip it only for a model with no UI surface at all (pure backend/abstract model, never rendered in any view). As in DTON above, the tour must cover every view the model's data ends up in, including secondary views under a different action and any embedding in another model's view — not only the new model's own screen. `./test.sh TestClassName` (scoped to the new test class) must fail.
3. **Green — T:** Write the minimum code to pass: `models/<area>/<model>.py`, `security/ir.model.access.csv` (+ `security/rules/*.xml` if needed), `views/<area>/<model>/{form,list,menu}.xml`, manifest bump. `./test.sh TestClassName` must pass.
4. **Refactor — O + N:** In the same cycle, not as a later pass: add `_order`, `_sql_constraints`, computed field guards, view fixes (O); apply the Odoo v18 coding guidelines from the "Coding standards" section above — model attribute order, alphabetical imports, f-strings, loop variable naming, translatable literals (N).
5. **Gate:** `./upgrade.sh` and `./test.sh TestClassName` after each Red-Green-Refactor cycle (see "The full test suite is slow" above — don't reach for the unscoped `./test.sh` here).
6. **Close — D:** For every role identified in the Spec step, fill in the three language versions of that role's user doc (`docs/{en,ca,es}/<role>/<model>.md`) — this is a mandatory deliverable of every new feature, not an optional extra to be requested separately; skipping it because the feature "isn't for admins" is the most common way this step gets missed. Also update the role's `index.md` to link the new manual. Add the new strings' real Catalan/Spanish translations to `i18n/ca_ES.po` and `i18n/es_ES.po` (see "All literals must be translatable" above — wrapping in `_()`/`_t()` during Green/Refactor is not enough on its own), and reconcile the developer doc's diagram if the implementation diverged from the initial spec during the cycle. Finish by running the full, unscoped `./test.sh` exactly once, as the final gate for the whole feature.
