# EMS — Educational Management System

An open-source Odoo v18 module for managing an educational centre. Developed by teachers at Institut Puig Castellar (Santa Coloma de Gramenet, Barcelona) as part of the Quality and Continuous Improvement Project (Q&CIP).

## Tech stack

- **Backend:** Odoo v18, Python 3
- **Frontend:** OWL (Odoo Web Library), XML views, JavaScript
- **Database:** PostgreSQL — database name is `ems`
- **Official reference:** https://www.odoo.com/documentation/18.0/ (always consult before making technical decisions)

## This environment is development, not production

The `ems` PostgreSQL database on this box — the one `psql -d ems`, `./upgrade.sh` and
`./test.sh` all operate on — is a **development/sandbox database. It is not production**,
regardless of how plausible its data looks (real-looking student names, hundreds of rows,
counts that seem too specific to be fake). There is no direct access to the real production
database from this environment.

**How to apply:** never phrase a finding from a local `psql -d ems` query as a fact about
"production" — phrase it as a fact about this dev database (e.g. "0 rows in this dev DB",
not "0 rows in production"). If a finding needs confirming against real production data
before it can inform a decision (an incident report, a data-quality question, an urgency
call), **ask the developer** — either for the specific query results run directly against
prod, or for an unimported backup dump left somewhere readable, which can be restored into a
**new, separate** database (the `odoo` OS/Postgres role has `CREATEDB`; use
`sudo -u odoo createdb <name>` + `pg_restore`/`psql -d <name>`, mirroring the
`sudo -u odoo psql ...` pattern `upgrade.sh` already uses for privileged writes) — never
restore over the existing `ems` dev database, which the running Odoo instance and the test
suite both depend on staying intact. See `feedback_dont_conflate_sandbox_with_prod` in
memory for the incident this rule comes from, and a second, broader one from 2026-07-30
where dev-DB findings were repeatedly mislabeled "production" across an entire session
before being caught.

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

**Ask before launching the full, unscoped `./test.sh` at all — even for that single final-gate run.** There is no downside to asking first: CI already runs the full suite unconditionally before anything merges, so a local full run is pure convenience/early-signal, never the actual safety net. Push it as late as possible and check with whoever's driving (the developer, or an AI agent's user) instead of launching it unprompted once work seems done.

**If a test run seems to hang with no output, refresh any browser tab you have open on the Odoo backend.** `--test-enable` spins up a real HTTP server for the duration of any `HttpCase`/tour test (e.g. `test_grade_session_tour`, `test_level_tour`, `test_strike_tour` — pulled in by the full, unscoped `./test.sh`, or by name if you target one directly). Odoo's teardown (`_wait_remaining_requests` in `odoo/tests/common.py`) waits for every open HTTP request against that server to finish before the process can exit — including a stray long-polling (bus) connection from an already-open browser tab pointed at the same host/port, which is designed to never close on its own. Refreshing (no need to close) that tab severs the stale connection and lets the run finish. Scoped runs of test classes with no tour/`HttpCase` tests don't hit this specific hang, but closing/refreshing before *any* `./test.sh` run is the standing habit regardless (see the notification trigger below, which fires for every run, not just tour ones).

**Notifications for this developer are handled entirely by an already-built host-side file-drop bridge — never call the `PushNotification` tool on this project.** It proved unreliable in this container/VSCode-extension setup (silently self-suppresses as "terminal active," no mobile push available here) and only adds noise; do not use it for test or completion notifications here, and do not re-attempt Remote Control/DBus approaches — they don't work in this setup and that's settled. The working bridge (`~/claude-notify` on the host ↔ `/mnt/claude-notify` in the container, watched by a `systemd --user` service running `notify-send`) is already built and verified; full rebuild/troubleshooting steps live in `docs/en/developers/tooling/ai_agent_test_notifications.md` — only needed if the bridge itself ever breaks.

Exactly three triggers should ever produce a notification for this developer:
1. **Launching a test run that actually needs the browser-tab close/refresh** — i.e. one that will exercise a tour/`HttpCase` test (see "If a test run seems to hang" above): the full, unscoped `./test.sh`, a scoped run of a `*Tour`/`HttpCase` class, or a `--test-tags` expression the hook can't cheaply classify (treated as "yes, notify" to stay safe). A scoped run of a plain `TransactionCase`-only class never hits that hang, so it deliberately stays silent — notifying for those too would just be noise (changed 2026-08-01, after being unconditional for a while). This is fully automatic via a `PreToolUse`/`Bash` hook already in the developer's user-level `~/.claude/settings.json`, which pipes the command through `/root/.claude/hooks/ems-test-notify.sh` (checks the class name against `tests/*_tour.py` before deciding) and writes a trigger file to `/mnt/claude-notify/` only when it decides to. No agent action needed — don't duplicate it with anything else.
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
- **No shadowed builtins** (`list`, `type`, `hash`, `bytes`, `id`, `date`, ...) as local variable or parameter names — this bug class was found by hand several times during the DTON rollout (`LimesurveyApi.count_participants`'s `list`, `ems.base.notify`'s `type` parameter, `datetime_utils`' `datetime` parameters). Check for it with `pylint --disable=all --enable=redefined-builtin models/` (installed via `apt install pylint`) — not wired into a blocking hook, run it by hand after any pass touching several files.
- XML `<record>`: `id` attribute before `model`.
- f-strings instead of `%s` formatting.
- **DRY, both server (Python) and client (JS):** never duplicate code. Reuse existing methods, extend them, or extract a new shared method/RPC call instead of copy-pasting logic.
- **"Odoo way" first:** don't build a custom solution unless strictly necessary. Always check the official Odoo v18 documentation and existing Odoo/EMS patterns for a built-in mechanism before writing bespoke code.
- **Full-scenario exploration before implementing — never assume, ask when ambiguous.** Before writing or relaxing any validation/constraint/guard, grep and read *every* real write path for the field(s) it touches (every wizard, compute/onchange method, direct ORM call, view `required`/`readonly` attribute) — not just the one test or scenario currently in front of you. Don't guess whether a state that conflicts with a new check is a "legitimate real case" or merely a test fixture bypassing what the real UI/ORM would otherwise enforce — verify it by tracing the actual code paths, every one of them, before deciding which side (the new check, or the conflicting test/code) is wrong. If, after that exploration, genuine ambiguity remains — however small — ask the developer rather than picking a side. Found the hard way (2026-07-30): a new `sale.order` constraint broke an existing test, and the first fix relaxed the constraint on the unverified assumption that the test reflected a real production scenario; only the developer's follow-up question ("¿tiene sentido que esto ocurra? ¿se me escapa algo?") prompted the full write-path audit that should have happened *before* proposing that fix — which then showed the assumption was wrong (no real path can produce that state) and the test's fixture needed fixing instead, not the constraint. A relaxed-on-assumption constraint can silently end up less protective than intended, which is exactly the class of mistake this rule exists to prevent.
- Resulting code must be clean, simple, non-redundant, and well-refactored.
- **All literals must be translatable:** wrap every user-facing string for translation (`_("...")` in Python, `_t("...")` in JS/OWL) so it can be picked up by the i18n files, with English as the default/source language. Wrapping is only step one — it makes a string *translatable*, it does not translate it. Every new feature must also add the actual Catalan/Spanish entries to `i18n/ca_ES.po` and `i18n/es_ES.po` before it's considered done (see the "Close" step of the Development workflow below). To find what's missing: export current terms with `odoo -d ems --i18n-export=<path>.po -l ca_ES --modules=ems --stop-after-init` (repeat for `es_ES`), diff msgids against the checked-in `.po` files, and append translated blocks for the new ones only (don't regenerate/replace the whole file — order doesn't matter to gettext, and the files may already carry unrelated pre-existing gaps that aren't your task's responsibility). Run as the `odoo` user with a path it can write to (not a sandboxed/restricted directory). Do not insert decorative section-header comments between po entries — a comment block with no following `msgid` breaks Odoo's po parser on load.

  **A msgid diff alone is not enough — it misses reused labels.** Odoo's po loader binds a block's `msgstr` to the *exact* `#:` reference lines in that block (`model:ir.model.fields,field_description:ems.field_<model>__<field>`, `model:res.groups,name:ems.<xmlid>`, `model:ir.ui.menu,name:ems.<xmlid>`, `model:mail.template,subject/body_html/name:ems.<xmlid>`, etc.) — never by matching msgid text alone. So when a new field/record's label happens to be a common word already translated for a *different* field (`Teacher`, `Name`, `Active`, `Manager`, `Administrator`, `Configuration`, `Sequence`...), a msgid-only diff reports nothing missing — the text isn't new — yet the new field still renders untranslated, because its own `#:` reference was never added to that existing block. For every new field/model/group/menu/template introduced by the feature: search the checked-in `.po` for its exact label text first; if a block already exists, add your new record's `#:` reference to it (same `msgstr`, no translation work needed) instead of assuming it's already covered; only create a brand-new block if the text itself doesn't exist anywhere yet. **Verify, don't just trust the diff:** after `./upgrade.sh`, spot-check a sample of the new fields/records directly in the DB, e.g. `psql -c "SELECT field_description FROM ir_model_fields WHERE model='<model>' AND name='<field>';"` (or the equivalent column for `ir.model.name`, `ir.ui.menu.name`, `res.groups.name`, `mail.template.name`/`subject`/`body_html`, etc.), and confirm the jsonb value actually has `ca_ES`/`es_ES` keys, not just `en_US`. A `.po` entry existing is necessary but not sufficient — only a DB read proves the reference actually matched.

## Documentation structure

There are **two distinct categories** of documentation, for two different audiences — every new feature needs both, they are not alternatives:

- **Technical documentation** (`docs/en/developers/`): for developers reading the code. English only. Mermaid diagrams of hierarchy/relations, CRUD flow, access-control tables.
- **User documentation** (`docs/{en,ca,es}/<role>/`): manuals for the people who actually operate the feature in the running app — one folder per role (`admin`, `teachers`, `tutors`, `secretary`, `head_of_studies`, `families`). Trilingual: every user doc needs a Catalan, Spanish and English version. A single feature can need more than one role's manual (e.g. a teacher-facing screen plus the admin config behind it) — see the Development workflow below for how to identify which roles apply.

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

**Precise mechanism, verified empirically 2026-07-30 (removed a row from an already-`__import__.`-prefixed CSV, ran `./upgrade.sh`, confirmed the DB record survived untouched; re-added the row, confirmed it re-linked to the same record, no duplicate) and by reading `odoo/addons/base/models/ir_model.py::_process_end`** — the method Odoo calls at the end of every module load to delete records whose xmlid vanished from the reloaded data:
```sql
SELECT ... FROM ir_model_data
WHERE module IN %(modules_being_processed)s AND COALESCE(noupdate, false) != true ...
```
Two independent conditions gate deletion, both need to hold: **(1)** the record's `ir_model_data.module` must be one of the modules actually being installed/updated in this run (e.g. `('ems',)`) — `__import__` is never in that set, so a `__import__`-owned record is never even a *candidate* for this cleanup, full stop, regardless of `noupdate`; **(2)** even for a module-owned record, `noupdate=True` also independently exempts it from deletion. This means deletion-safety and update-safety are two genuinely separate mechanisms that happen to both be governed by columns on the same `ir_model_data` row: `module='__import__'` is what makes a `data/custom/` record here survive being removed from its CSV file entirely; `noupdate` (deliberately `False` for `data/custom/`, see above) is what makes its *field values* keep tracking the file while the record itself still exists. **Removing a row from a `data/custom/` CSV and running `./upgrade.sh` does *not* delete the corresponding record — it just stops that field data from being pushed to it going forward.** If a record genuinely needs to be deleted, that has to be done explicitly (a migration script, or by hand) — the file alone can't do it once a record is `__import__`-owned.

**Rule — author new `data/` records as CSV, not XML, wherever the model allows it.** This is what makes the `__import__.` prefix rule above achievable at all (see the hard limitation below) — an XML `<record>` in `data/custom/` can *never* get a real `__import__.` id, so starting a new centre-specific dataset in XML guarantees this exact gap has to be paid down again later. Applies to teammates too, not just AI-assisted changes. CSV is only unusable for a genuine, confirmed technical reason (see the two confirmed blockers just below) — if in doubt whether a new dataset hits one of them, check first rather than defaulting to XML out of habit.

**Hard limitation #1 — `__import__.` only works in CSV, not XML `<record>` tags:** Odoo's XML data loader (`odoo/tools/convert.py::_test_xml_id`) unconditionally rejects any `<record id="module.name">` whose module isn't an *actually installed* Odoo module, and `__import__` never is — this raises `AssertionError: The ID "__import__.xxx" refers to an uninstalled module` and aborts the entire file's load. `__import__` is only accepted by the CSV/`load()` import path (`odoo/models.py`), which is why the UI CSV importer and CSV data files can use it but a `data/custom/*.xml` file cannot. There is no XML-side workaround for this one — a one2many populated inline via `eval="[(0, 0, {...})]"` (e.g. `ems.planning`'s `planning_outcome_ids`) needs a **separate related CSV file** (one row per child record, referencing its parent by id) instead of a 1:1 XML→CSV transliteration; CSV's `load()` path has no inline-eval equivalent. Don't attempt `id="__import__.xxx"` in a `<record>` tag — verify with `./upgrade.sh` after any id-prefix change in `data/custom/`.

**Confirmed real, remaining CSV-incompatible case — a field resolved via `search=`, not a static `ref=`.** `<field name="..." search="[(...)]"/>` runs an arbitrary domain lookup at load time to resolve a many2one that has no external id of its own (e.g. `data/custom/ccff/ems_enrollment_template_opt.xml`'s `product_id`, resolved via `[('product_tmpl_id.ems_subject_ids', '=', ref('__import__.subject_OPTn'))]` because the `product.product` variant is auto-generated by `ems.subject` and never gets its own xmlid). CSV's `load()` only supports a static `field/id` external-id reference or a plain value — there's no domain-search equivalent, and minting a brand-new xmlid for the resolved record doesn't fully work around it either: that new xmlid would have to exist *before* this CSV loads (it's what the row references), but it can only be created by code that itself needs the earlier-loaded data already in place — a chicken-and-egg ordering problem with no clean fix via `post_init_hook` (which runs after all data, too late for a file that references the id it would create). Files that only use `search=` for this reason stay in XML, without a `__import__.` id, as a deliberate, confirmed exception — not a gap to keep re-litigating; a real fix would need product-level changes (e.g. `ems.subject`'s own create() logic assigning its generated product an xmlid at creation time), out of scope for a `data/` format conversion.

**`data/custom/` is versioned config, not runtime state — embrace `noupdate=False`, matching `data/cat/`.** CSV loaded via the manifest's plain `data` key is always `noupdate=False` — every upgrade re-syncs the record's fields to match the file. This is deliberate and desired for `data/custom/`, exactly like `data/cat/` already works today (100% `noupdate=False`, whether CSV or the handful of XML files there): each centre's `data/custom/` is that centre's own versioned configuration (planning ponderations, authorization templates, course setup, etc.), the CSV file is its single source of truth, and re-applying it every upgrade is what lets one centre adopt another's fork by patching these files and running an upgrade — the same workflow already used for EMS's own shared `data/cat/` content. An admin's in-app edit to a `data/custom/`-backed record (e.g. editing a planning's ponderations from its form view) is expected to be reverted on the next upgrade unless it's also committed to the CSV — that's the contract, not a bug.

**CSV cannot actually be marked `noupdate=True` in this Odoo version — that's exclusive to XML.** An earlier version of this note claimed the deprecated `init_xml` manifest key gives a CSV file `noupdate=True`; that was wrong and has been corrected after a live test (2026-07-30, `data/custom/res.partner.category-<probe>.csv` listed under `'init_xml': [...]`, ran `./upgrade.sh`) showed the file never even loaded — no "loading ems/..." log line, record never created. Root cause, confirmed by reading the actual installed `odoo/modules/loading.py::load_data._get_files_of_kind`: `keys = ['init_xml', 'update_xml', 'data']` is set inside an `elif kind == 'data':` branch, but the very next line, `if isinstance(kind, str): keys = [kind]`, is a **separate, unconditional `if`, not an `elif`** — since `kind` is always a plain string, this second `if` always fires and silently overwrites `keys` back down to just `['data']`, discarding the `init_xml`/`update_xml` merge entirely. Files listed under `init_xml`/`update_xml` are therefore never read at all during the normal 'data' load phase in this Odoo build, regardless of noupdate — apparent dead code, not a working (if deprecated) mechanism. The only manifest key that actually produces `noupdate=True` is `demo` — semantically wrong for real config (demo data is optional, skipped entirely with `--without-demo`, and conceptually sample data, not a centre's real configuration). **Practical conclusion: if a `data/custom/` (or any EMS) CSV record genuinely needs `noupdate=True` protection, there is no clean file-based way to get it — the only options are (a) keep it XML, or (b) set `ir_model_data.noupdate=True` directly via a migration script**, bypassing the file-loading mechanism's noupdate handling entirely (not something to reach for casually, since it also means the file's own content stops being an honest description of what the record actually does on upgrade).

**Critical, easy-to-miss detail when converting an existing `noupdate="1"` XML file to CSV: the file's load-time `noupdate` context is not what decides whether an *already-existing* record gets updated — `ir_model_data.noupdate`, a value stored per-record at the time it was first created, is.** Confirmed empirically 2026-07-30 (edited a value in an already-`__import__.`-renamed CSV row and ran a plain `./upgrade.sh`; nothing changed) and by reading `odoo/models.py::_load_records`: `if not (update and d_noupdate): to_update.append(data)` reads `d_noupdate` from the **existing** `ir_model_data` row, not from the noupdate the calling file was loaded with. A record originally created under `<data noupdate="1">` XML has `True` permanently baked into that stored column — converting its file to CSV and even renaming its `module` to `__import__` changes nothing about whether it gets updated, because the stored flag still says "don't touch me." **A rename migration must explicitly clear it**: `UPDATE ir_model_data SET module = '__import__', noupdate = FALSE WHERE ...` — not just the module column (see `migrations/18.0.0.22.0/pre-migrate.py::_rename_data_custom_xmlid_ownership` for the fixed pattern; the earlier `18.0.0.19.1` rename for `ems.group`/`crm.team` didn't need this because those files were always plain CSV, never noupdate=1 XML, so their stored flag was already `False`). Verify with the same empirical test used here — change a value in the converted CSV, run a plain `./upgrade.sh` (no version forcing), confirm the DB actually picked it up — rather than trusting that "it's CSV now" is sufficient on its own.

**Gotcha confirmed while converting `ems.course.xml`: a legacy NULL boolean can't self-heal via CSV resync.** A Boolean field added to a model *after* some rows already existed leaves those rows' column raw SQL NULL forever, unless something explicitly backfills it — Odoo's own `Boolean.convert_to_cache` does `bool(None) == False`, so the ORM (including the CSV loader's own read-current-value-before-deciding-to-write step) can never tell a legacy NULL apart from a real `False`. Converting the file from `noupdate="1"` XML to `noupdate=False` CSV does **not** fix this on its own: the loader sees "current value False (really NULL), desired value False" as no change and skips the `write()`, so the NULL survives every future upgrade untouched — confirmed on `ems_course.is_enrollment_default` (one legacy row, backfilled explicitly via `migrations/18.0.0.22.0/post-migrate.py::_backfill_null_course_enrollment_default`, not something the format conversion itself could resolve). Before converting any `noupdate="1"` file whose model has Boolean fields, spot-check `col IS NULL` (not just the ORM-friendly `SELECT col`, which masks it) on the existing production data and add an explicit one-time SQL backfill in the same migration if any legacy NULLs turn up.

**The one real exception: fields that are live application state, not configuration.** A field a running EMS instance mutates itself as part of normal operation (not a one-off admin edit) must **not** be a synced CSV column at all, or every upgrade breaks that operation — e.g. `ems.course.is_current`/`is_enrollment_default`, flipped by `res.company._sync_current_course_flag()` whenever the "Current course" setting changes, or `ir.sequence.number_next_actual` (never a data-file column in the first place, for the same reason). Leave such fields out of the CSV entirely — the record still gets `__import__.`-prefixed and survives upgrades/module removal like every other `data/custom/` row, it just isn't re-seeded from the file after its first creation for that specific field. Seed the field's actual initial value (if not the model's plain default) via a one-time `post_init_hook`/migration write instead, same pattern as any other one-time backfill (see "Migrations" below). This is a narrow, field-level carve-out, not a reason to keep a whole record/file in XML or under a different noupdate policy.

**Deciding `noupdate=True` vs `False` for `data/main/`/`data/cat/` (EMS's own data, not `data/custom/`'s centre config): default to `False` — EMS owns its data and should keep improving it. `noupdate=True` is the exception, earned per record, not a default courtesy** — and being Odoo-native vs EMS-authored has no bearing on the decision either way (Odoo's own official docs leave this entirely to each module's judgment, and Odoo core itself is inconsistent about it). The actual test, and worked examples (`ems.schedule_framework_default.xml` genuinely earns `noupdate=True`; `ems.mail_activity_type.xml`/`res.partner.category.xml` don't): see `docs/en/developers/shared/data_loading.md`'s "Deciding `noupdate=True` vs `False`" section.

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

## DTON cleaning methodology (historical — retroactive backlog completed 2026-07-29)

This was the retroactive code-quality process applied model by model, one phase at a time
(tracked in memory as `project_dton_rollout_roadmap`), followed by a refactor/test-
optimization pass (`project_post_dton_refactor_roadmap`). **Every model in EMS now has DTON
applied — there is no backlog left.** This section is kept so the D/T/O/N terminology below
stays defined and so the history is discoverable; the trigger rule it used to carry ("apply
DTON to any not-yet-covered model you're about to touch") has no live targets anymore. Going
forward, use the **Development workflow** below for both new models and changes to existing
ones — it already folds D/T/O/N into a single cycle and doesn't need a separate retroactive
pass to catch up to.

1. **D — Diagrams:** Technical docs in English (`docs/en/developers/`) with Mermaid diagrams; user docs in all three languages, one file per role that actually interacts with the feature (`docs/{en,ca,es}/<role>/`, where `<role>` is `admin`, `teachers`, `tutors`, `secretary`, `head_of_studies` or `families` — not only `admin/`; a feature can be relevant to more than one role and then needs a doc file under each).
2. **T — Testing:** Backend `TransactionCase` tests + browser tour test. The tour must exercise **every view where the model's data is actually rendered**, not just its own canonical list/kanban/form action — a clean `./upgrade.sh` and passing `TransactionCase` tests only prove the arch loads and the model's logic works; neither renders anything in a browser, so neither catches a client-side (OWL template, widget) crash. Concretely, check for and cover:
   - The model's own primary list/kanban/form views (the ones reachable from its normal menu).
   - Any **secondary view** for the same model reachable only via a different action (e.g. a kanban view inherited/overridden separately from the model's main list+form action) — these are easy to forget precisely because they're not in the model's own menu.
   - Any **other model's view that embeds this model's fields** — a `many2many_tags`/custom widget showing this model's records on a *different* model's form or kanban (e.g. `ems.role` colors rendered as badges on `hr.employee`'s form), a related/computed field surfacing this model's data elsewhere, etc. Grep for the model's name and its fields across `views/` before assuming the model's own screens are the full picture.
3. **O — Optimization:** `_order`, `_sql_constraints`, view fixes, computed field guards, refactoring, cleaner and simple code.
4. **N — Normalization:** Apply Odoo v18 official coding guidelines.

Gate O and N with `./test.sh TestClassName` for the model being cleaned (see "The full test suite is slow" above); ask before running the full, unscoped `./test.sh`, after N rather than after both phases.

## Development workflow (TDD + DTON)

The standard workflow for **any** change — a brand-new model/feature, or a modification to an
already-DTON-compliant one — so it arrives (or stays) DTON-compliant instead of needing a
separate cleanup pass later. It is TDD's Red-Green-Refactor cycle, with D/O/N slotted into it —
no separate process to remember, and no distinction between "new" and "existing" beyond
whether Spec/Red start from a blank file or a diff:

1. **Spec (before Red) — D:** Before any test or code, stub or update `docs/en/developers/<area>/<model>.md` (Mermaid diagram of hierarchy/relations, CRUD flow, access-control table) with the requirements this change needs to cover. From that access-control table, identify **every role that will actually use the feature** (`admin`, `teachers`, `tutors`, `secretary`, `head_of_studies`, `families` — a feature is frequently relevant to more than one, e.g. a teacher-facing grading screen plus an admin config screen) and stub or update one `docs/{en,ca,es}/<role>/<model>.md` per role identified, not just `admin/`. These stubs are the acceptance criteria for the cycle below.
2. **Red — T:** Write or adapt `tests/test_<model>.py` (`TransactionCase`) and the tour (`static/tests/tours/<model>_tour.js` + `tests/test_<model>_tour.py`) for the behavior this change needs — before writing the implementation. The tour is the default, not an optional extra; skip it only for a model with no UI surface at all (pure backend/abstract model, never rendered in any view). The tour must cover every view the model's data ends up in, including secondary views under a different action and any embedding in another model's view — not only the model's own screen. **This applies just as much to a change on an already-DTON'd model as to a brand-new one** — found the hard way (2026-07-30): a checkbox-to-radio widget change on `ems.limesurvey_block` was initially shipped without a tour ("no tour exists for this view" was treated as a reason to move on, not as the gap it was); the developer had to ask "¿no haría falta un tour para comprobar que abrir esta vista no falla?" before one got added — and it caught real, non-trivial bugs in the process (`select` on a plain `<select>` doesn't work the way it looks like it should, since Odoo's `SelectionField` JSON-stringifies the option `value` attribute — use `selectByLabel` instead; a `widget="code"` field is an Ace editor, not a plain `<textarea>`, and needs `ace.edit(anchor).setValue(...)` in a custom `run()`, not the generic `edit` action). `./upgrade.sh` succeeding only proves the view's XML is structurally valid (fields exist, widgets are compatible with the field type) — it proves nothing about whether the page actually renders or a click actually works in a real browser. `./test.sh TestClassName` (scoped to the relevant test class) must fail.
3. **Green — T:** Write the minimum code to pass: `models/<area>/<model>.py`, `security/ir.model.access.csv` (+ `security/rules/*.xml` if needed), `views/<area>/<model>/{form,list,menu}.xml`, manifest bump. `./test.sh TestClassName` must pass. If a new validation/constraint conflicts with an existing test, don't relax the new check to fit the test on assumption alone — see "Full-scenario exploration before implementing" in Coding standards above.
4. **Refactor — O:** In the same cycle, not as a later pass: add `_order`, `_sql_constraints`, computed field guards, view fixes for *this* model. Also check for **cross-cutting duplication** while you're here — the same shape of code (or test fixture/mock boilerplate) hand-written in more than one file is worth extracting into a shared helper (`ems.base` for production code, `tests/common.py` for test utilities) rather than left copy-pasted; this is exactly how the same escaping bug got independently found and fixed five times before `EmsBase.build_html_list` existed. Don't go looking for unrelated duplication elsewhere in the codebase on every change — but if this change's own work reveals an existing duplicate, fold the extraction into this same cycle instead of deferring it.
5. **Normalize — N:** Apply the Odoo v18 coding guidelines from the "Coding standards" section above — model attribute order, alphabetical imports, f-strings, loop variable naming, translatable literals, no shadowed builtins. Run `pylint --disable=all --enable=redefined-builtin` on the files you touched (see "Coding standards" above for the full command) — cheap, and this exact bug class (`list`, `type`, `datetime`, `bytes`/`hash` shadowing builtins) has recurred often enough to be worth a mechanical check rather than relying on reading alone.
6. **Gate:** `./upgrade.sh` and `./test.sh TestClassName` after each Red-Green-Refactor-Normalize cycle (see "The full test suite is slow" above — don't reach for the unscoped `./test.sh` here).
7. **Close — D:** For every role identified in the Spec step, fill in (or update) the three language versions of that role's user doc (`docs/{en,ca,es}/<role>/<model>.md`) — this is a mandatory deliverable of every change with a user-facing effect, not an optional extra to be requested separately; skipping it because the change "isn't for admins" is the most common way this step gets missed. Also update the role's `index.md` to link the manual if it's new. Add the new/changed strings' real Catalan/Spanish translations to `i18n/ca_ES.po` and `i18n/es_ES.po` (see "All literals must be translatable" above — wrapping in `_()`/`_t()` during Green/Refactor is not enough on its own), and reconcile the developer doc's diagram if the implementation diverged from the initial spec during the cycle. Finish by asking whether to run the full, unscoped `./test.sh` as the final gate for the whole change (see "Ask before launching the full, unscoped `./test.sh`" above — CI runs it anyway before merge). Then deliver the PR changelog summary described below — it's part of Close, not a separate ask.

## PR changelog: persist silently, deliver only on request

The developer keeps the chat in Spanish but writes their GitHub PR description in English,
using `.github/pull_request_template.md`'s sections (`Breaking changes` / `What's new` /
`Changes` / `Fixes` / `Internal changes` / `Related with`).

**No automatic chat delivery per task (retired 2026-07-30 — an earlier version of this rule
had the agent post an English block after every finished task; the developer simplified it
away since the persisted file below makes that unnecessary).** Instead: whenever a piece of
work finishes — a gap fix, a migration, a DTON cycle, anything the developer would want in the
PR body — silently append it to `changelog/<current-branch-name>.md` (e.g.
`changelog/284-dton-....md`; create the file, with real `#` section headings matching
`.github/pull_request_template.md`, if it doesn't exist yet). No chat output for this at task
completion — just the file write. (The separate "notify when a task finishes" bridge in
`/mnt/claude-notify/`, described elsewhere in this doc, is unrelated and unaffected — that
notification still fires normally.)

**Per-item formatting when writing to the file:** the item's own descriptive title directly as
the `##` heading (no "Item 1:"/"Item 2:" prefix, despite the template file's own placeholder
text), **ending that heading line with a colon**, no em dash (—) in the title as a separator
(parentheses instead) — e.g. `## Portal IBAN renewal (bank account never trusted):`. Group
items under their matching section (`# Fixes`, `# Internal changes`, etc.); a later item under
a section already present is appended under that existing heading, not a new one. Plain
markdown throughout, no code fences — the file is meant to be copied as a whole.

**Deliver in chat only when explicitly asked** — trigger phrases like "dame el texto/los
detalles para la PR" or similar (ask for clarification if genuinely ambiguous, don't guess).
When asked: read **every** file currently under `changelog/` (not just the current branch's
own — after pulling in a colleague's branch there may be several) and paste their combined
content directly into chat as plain markdown, exactly as stored, ready for the developer to
copy the whole thing as the PR body in one shot. This can be asked at any point, not only right
before publishing — always return whatever has accumulated so far.

**One file per branch, not one shared file** — deliberate, not just tidiness: every developer's
own Claude session does the same on their own branch, so `changelog/` ends up with multiple
independently-named files (one per contributor). A single shared file would conflict on every
merge between two branches that both touched it; separate, uniquely-named files never collide,
and simply accumulate side by side when branches are combined. **This folder must be tracked by
git** (not gitignored) so it survives a branch switch/pull-from. **Delete the entire
`changelog/` folder as the very last step before merging into `main`** (its contents are a
working draft, not permanent documentation — same lifecycle as a `plans/` file) once they've
been copied into the actual GitHub PR description.

**This deletion step is enforced and automated, not left to memory** (2026-07-30) — three
CI pieces work together:
- `.github/workflows/require-changelog-clean.yml`: a required status check on PRs targeting
  `main` that fails while `changelog/` still has any content, blocking the merge button.
- `.github/workflows/changelog-clean.yml`: comment `/changelog-clean` on the PR (same
  Integrators-team authorization as `/deploy-check`) to remove `changelog/` via an automated
  commit pushed to the PR's own branch, right before merging.
- `.github/workflows/ci-unit-testing.yml`: detects when a push only touched `changelog/` (the
  cleanup commit above) and skips its own expensive install/test steps for that run, so the
  cleanup doesn't trigger a full ~6-minute re-run — while still actually running (fast) and
  reporting a real result, deliberately not using `[skip ci]` or a path-filtered trigger for
  this, both of which risk GitHub leaving a required check stuck "pending" forever instead of
  passing.
