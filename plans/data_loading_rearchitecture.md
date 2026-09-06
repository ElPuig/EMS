# `data/` loading rearchitecture: living vs. master data, XML vs. CSV, demo data

**Status: current as of 2026-09-06 — not started.** Written after fixing `ems.group` on branch
`404-schedule-import-if-replace-mode-no-conflicts-with-the-current-one-can-occur` (the only part
of this file's content actually implemented so far — see that fix's own writeup in
`docs/en/developers/shared/data_loading.md`'s "`data/custom/` living data" section, kept as
accurate documentation of what exists today). Everything else in this file is deferred to a
future branch. This supersedes and folds in the earlier, narrower
`data_custom_living_vs_master_audit.md` plan (same investigation, now with a load-bearing
technical finding added — see below — that changes the recommended approach for `data/custom/`
substantially, so it's written up fresh rather than patched).

## The key technical finding that shapes everything below

`noupdate=True` does **not** protect a record from a full module **uninstall** — only from the
narrower cleanup Odoo runs at the end of every **upgrade** (`ir.model.data._process_end()`,
which only removes records whose xmlid disappeared from the reloaded file). Verified by reading
the actual uninstall code path, `ir.model.data._module_data_uninstall()`
(`odoo/addons/base/models/ir_model.py:2471`):

```python
module_data = self.search([('module', 'in', modules_to_remove)], order='id DESC')
```

No `noupdate` filter at all — every `ir_model_data` row owned by the module being uninstalled is
deleted, `noupdate` or not. Only `module='__import__'` is immune, because `__import__` can never
appear in `modules_to_remove` (it isn't a real, installable module).

**Consequence:** `noupdate` and the module-ownership prefix (`ems.` vs `__import__.`) are two
genuinely independent axes in Odoo, protecting against two different things:
- `noupdate=True` → survives a record's own file row disappearing during a normal upgrade.
- `module='__import__'` (this project's own convention for `data/custom/`, not a stock Odoo
  concept) → survives even a full uninstall/reinstall of the `ems` module itself.

Stock Odoo modules never need both at once: a module's own shipped data (master **or**
initial/seed alike) is *expected* to disappear if the module is uninstalled — that's correct,
intended behaviour. That's why in vanilla Odoo, `noupdate` alone (on the module's own real
prefix) is the complete answer to "master vs. one-time initial data" — there's no need for a
separate ownership trick, because uninstall-survival was never a requirement in the first place.

`data/custom/` breaks that assumption on purpose: it holds the *centre's* data, riding inside
*EMS's* module/manifest, and that data must survive even if EMS itself is fully reinstalled
(disaster recovery, a module rename, whatever). That's a genuinely different requirement stock
Odoo doesn't have an answer for, which is exactly why this project invented the `__import__.`
convention for it in the first place (see `CLAUDE.md`'s Data folder conventions). It follows
that `data/custom/` needs **both** axes at once for every record, master or living — and no
single file-based mechanism in this Odoo version gives both (`__import__.` is CSV-only; real
`noupdate=True` is XML-only) — see the Capability table in `data_loading.md` for the underlying
CSV/XML limitations this runs into.

## What this means, split by folder

### `data/main/` / `data/cat/` (EMS's own data)

No `__import__.`/uninstall-survival need here at all — this is EMS's own data, and it's correct
for it to disappear if EMS is uninstalled. So the vanilla Odoo answer applies cleanly: **XML,
`noupdate="0"` for master config (the default, current policy — see `CLAUDE.md`'s "Deciding
`noupdate=True` vs `False`" section, unaffected by anything in this file) or `noupdate="1"` for
data meant to seed once and become instance-owned (rare, needs the same concrete justification
`data_loading.md` already documents for `ems.schedule_framework_default.xml`).**

CSV is not *needed* here for anything functional (no `__import__.` requirement) — it remains
useful only as an ergonomic choice for large tabular datasets (`ems.subject.csv`,
`ems.study.csv`, ...), not a technical necessity. **Not a mandate to rewrite existing `data/cat/`
CSV files to XML** — that would be significant, low-value churn for files that are working fine
today under the existing `noupdate=False`-almost-always policy. Worth evaluating file by file
only if a *specific* file's data turns out to need `noupdate=True` in the future (rare, per the
existing decision framework), not as a blanket conversion project.

### `data/custom/` (the centre's own data)

Keep `__import__.` + CSV for **every** record here, master or living alike — dropping to `ems.`
+ XML for any of it would trade away real, deliberate protection (uninstall-survival) for no
functional gain. The living/master distinction within `data/custom/` has to keep being
reconstructed by code (the `_ems_freeze_living_custom_data()` / `_EMS_LIVING_CUSTOM_DATA_MODELS`
mechanism already built for `ems.group`, in `models/settings/company.py`) — not because it's
elegant, but because it's the only way to keep all three properties (survives file-row removal,
survives a full EMS reinstall, freezes after first creation) at once in this Odoo version.

**To do:** extend `_EMS_LIVING_CUSTOM_DATA_MODELS` (and add a
`test_custom_data_records_are_frozen_against_future_upgrades`-style test, following the
`ems.group`/`tests/test_group.py` precedent) for each model confirmed living below, once the
developer has reviewed/corrected this list:

- **Strong candidates:** `ems.space.csv` (classrooms — identical shape to `ems.group`: an admin
  renaming/repurposing a room should not be reverted by the next upgrade); `hr.employee.csv`
  (phone/email/address/role routinely corrected by HR — the highest-risk file of the lot, since
  almost every column is plausible admin-edited content).
- **Needs a closer look:** `hr.department.csv` (`name`/`color` plausibly admin-edited;
  `parent_id`/`is_top_level`/`top_level_area` look more structural — may need a field-level
  split the current per-record freeze can't express); `res.company.csv` (rare edits, but easy to
  lose silently precisely because it's a single low-traffic record nobody's watching).
- **Judged master, no action needed:** `ems.course.csv` (new rows are added by editing the file
  each year by design — no runtime code path creates `ems.course` records), `resource.calendar*
  .csv` (structural bell-schedule framework), `ems.authorization.template.csv` (legal text,
  centrally authored/versioned), `crm.team.csv`, `ir.sequence-enrollment_number.csv`, root
  `res.partner.csv` (`tz` only), and the `btx/`/`eso/`/`ccff` curriculum subfolders (already
  covered by the existing `data/cat` extension convention in `CLAUDE.md`).

### Demo/example content — move out of `data/custom/` entirely

Confirmed by the developer (2026-09-06): root `ems.teaching.csv` (4 rows, one fake teacher) and
`ccff/dam1a/`, `ccff/daw1a/` (`res.partner.csv` with fabricated students like `"Student Name
1"`, `ems.enrollment.csv`) are bundled illustrative/demo content, not real centre data. They
don't need *any* of `data/custom/`'s protections — no admin manages fictional students, and
losing/regenerating this content on reinstall is fine.

**To do:** move these files from the `data` manifest key to the `demo` key, and drop
`__import__.` in favour of a real `ems.` prefix. The `demo` key is the only manifest key
confirmed to actually produce `noupdate=True` in this Odoo build (see `data_loading.md`'s
"confirmed dead-code path" section on `init_xml`/`update_xml`), so this gets real freeze
protection for free, gets properly skipped with `--without-demo`, and is honestly labelled as
non-essential sample content instead of looking like real centre configuration. Format (CSV vs.
XML) doesn't matter much for this content — it's small and disposable either way; CSV is fine to
keep for simplicity.

## Documentation to rewrite once this is implemented

`CLAUDE.md`'s "Data folder conventions" section and `docs/en/developers/shared/data_loading.md`
need a clear, explicit decision tree for "how do I create a new `data/` file" that a future
developer (or an unrelated Claude session) can follow without rediscovering this entire
investigation. It must cover, in order:

1. Is this EMS's own data (`data/main/`/`data/cat/`) or the centre's own (`data/custom/`)? This
   decides whether uninstall-survival (`__import__.`) is even relevant at all.
2. For EMS's own data: plain `noupdate="0"` XML/CSV by default; `noupdate="1"` XML only with a
   concrete, specific justification (existing framework in `data_loading.md`, unchanged).
3. For the centre's own data: is it real, meant to survive both an upgrade *and* a full EMS
   reinstall? → `__import__.` + CSV, always, master or living. Is it disposable
   illustrative/demo content? → `demo` manifest key, `ems.` prefix, no `__import__.` needed.
4. For centre data that also needs to freeze after its first creation (living, not master): the
   file mechanism stops there — must be finished with the `_EMS_LIVING_CUSTOM_DATA_MODELS` /
   `_register_hook()` pattern, code-side, not by picking a different file format.

This rewrite is the explicit deliverable the developer asked to have documented (2026-09-06) so
"a developer, or any Claude session" has this reasoning available without re-deriving it — it
should absorb the reasoning in this plan file once done, at which point this plan file itself
gets deleted per the usual `plans/` lifecycle.
