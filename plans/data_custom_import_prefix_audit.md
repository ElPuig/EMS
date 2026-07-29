# PLAN — `data/custom/`'s `__import__.` prefix rule: XML records still not fixed

> **Status: partially fixed 2026-07-08 (CSV records), XML records still pending — not
> implemented.** Predates the "every DTON gap gets a plans/ file" standing rule, so this is a
> retroactive write-up of an already-tracked gap (see `project_data_custom_import_prefix_audit`
> in memory for the original 2026-07-08 session's findings), not a new discovery. Nothing below
> has been built. Verify file/line references against current code before acting, since the
> branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once the
> XML→CSV conversion is done (or explicitly decided against) and the resolution is reflected in
> `CLAUDE.md`'s "Data folder conventions" section.

## Problem

`CLAUDE.md`'s "Data folder conventions" requires every record in `data/custom/` to use the
`__import__.` id prefix, so Odoo never deletes it on a module upgrade (see that section for
why). An audit on 2026-07-08 (triggered by a production crash on
`ems_planning_unique_study_subject`) found this rule violated almost everywhere under
`data/custom/`.

**Already fixed (shipped in v18.0.0.19.1):** `ems.group.csv` (24 ids), `crm.team.csv` (3 ids)
— both CSV, so the rename was a straightforward `pre-migrate.py` reassigning the existing
`ir_model_data` rows from `module='ems'` to `module='__import__'` in place. A duplicate
`product.category.csv`/XML pair was also consolidated into one CSV file during the same pass.

**Still pending:** every `data/custom/` record declared via an XML `<record>` tag instead of
CSV — `ems.planning.*.xml` (123 records across several centre-specific files), 
`ems_authorization_template_data.xml` (5), `ems.course.xml` (4), `ems.sequence.enrollment.xml`
(1), and `ems_enrollment_template_opt.xml`'s `sale.order.template.line` records (7).

## Why this is hard, not just tedious

Per `CLAUDE.md`'s own documented hard limitation: Odoo's XML data loader
(`odoo/tools/convert.py::_test_xml_id`) unconditionally rejects any `<record id="__import__.xxx">`
— `__import__` is only accepted by the CSV/`load()` import path. There is no XML-side
workaround. The only fix is converting each of these files from XML to CSV.

For flat models (`ems.course`, `ems.sequence.enrollment`, the authorization template data),
this is a mechanical format conversion. For `ems.planning`, it's genuinely harder: its
`planning_outcome_ids` is a `one2many` currently populated via inline `eval=` inside the XML
`<record>` — CSV's `load()` path has no equivalent inline-eval mechanism for one2many data, so
this needs a **separate related CSV file** (one row per `ems.planning_outcome`, referencing
its parent `ems.planning` row by id) rather than a 1:1 XML→CSV transliteration.

## Why this matters (not just a style nit)

A `data/custom/` record with an `ems.*`-prefixed (not `__import__.`-prefixed) id is deleted by
Odoo the moment it's removed from the manifest, or on some upgrade paths — this is
centre-specific configuration (planning ponderations, authorization templates, the active
course/enrollment sequence), not EMS's own shared data. Losing it silently on a future upgrade
would be a real, currently-live risk for every one of these ~140 records, not a hypothetical.

## Open questions (need an answer before touching the code)

1. **Scope for one pass vs. several:** do all ~140 records get converted together, or should
   `ems.planning` (the hard one, needing a new related CSV file) be split into its own
   follow-up from the four flat-model conversions (which are comparatively mechanical)?
2. **Migration shape:** each conversion needs the same `pre-migrate.py` pattern already used
   for `ems.group.csv`/`crm.team.csv` (`UPDATE ir_model_data SET module='__import__' WHERE
   module='ems' AND name IN (...)`), scoped to that file's specific ids — per
   `CLAUDE.md`'s manifest-version rule, propose the version bump and wait for go-ahead rather
   than assuming one.
3. **Re-verify current state first** — this was last audited 2026-07-08; re-run the audit
   commands below before starting, since the branch may have added new `data/custom/` XML
   records since then that also need converting:
   ```bash
   grep -rhoE '<record\s+id="[^"]+"' data/custom | grep -v '__import__\.'
   ```
   (for CSV files, per-file: `awk -F',' 'NR>1{print $1}' file.csv | grep -vE '^__import__\.|^base\.'`)

## Where this is also documented

`CLAUDE.md`'s "Data folder conventions" section already documents the `__import__.`
CSV-vs-XML limitation in general terms (not specific to this remaining backlog) — update it
if the resolution here changes the documented pattern. [[feedback_import_prefix_xml_vs_csv]]
in memory has the original discovery of the XML limitation itself.
