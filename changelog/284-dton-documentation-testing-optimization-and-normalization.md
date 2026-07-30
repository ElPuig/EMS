<!-- Working draft, not permanent documentation - one file per branch in changelog/, named
     after the branch, so multiple contributors' branches never conflict on this file when
     merged together. Once all of a branch's changes are folded into a target release branch,
     read every file under changelog/ to reconstruct the combined picture across contributors.
     The whole changelog/ folder gets deleted as the last step before merging into main.
     See CLAUDE.md's "PR changelog summary" section for how/when this gets appended to.

     This file is complete, ready-to-paste markdown - copy the whole thing as the PR body,
     no per-section extraction needed (that per-block-fence convention is for chat delivery
     only, where the developer already has the section headings in place on GitHub and pastes
     bullets under each one individually).

     COVERAGE NOTE (2026-07-30): this file currently covers everything from commit 4e1b342
     ("IBAN fix") through HEAD - the portion reconstructable with full fidelity from this
     session's own conversation/memory. It does NOT yet cover the ~80 earlier commits on this
     branch (main..4e1b342^, the "Fase 7"-"Fase 12"/"Fase A"-"Fase E" DTON rollout history) -
     the developer confirmed reconstructing those now wouldn't save any work over doing it
     once, in full, right before the PR is actually finalized (git history doesn't get harder
     to read later). When that time comes: walk `git log --oneline main..4e1b342^` and each
     commit's diff/message, prepend the resulting entries to this file (they predate everything
     below), then proceed as normal. -->

# Fixes

## Portal IBAN renewal (bank account never trusted):
- The portal IBAN renewal route could mark a document "approved" without ever setting `allow_out_payment=True` on the underlying bank account, unlike the staff-side approval flow — 332 already-posted direct-debit invoices ended up with no usable bank reference as a result, out of 408 affected students. Portal renewal now trusts the bank the same way staff approval does; a migration backfills the 408 already-affected students, and invoicing now raises instead of silently self-granting trust.

## Authorization template matching semantics (level + study both required):
- A template scoped to both a level and a study matched if *either* condition held (OR), instead of requiring both (AND) — inconsistent with how templates scoped to only one condition already behaved. Unified to AND via a shared `_matches_scope()` predicate used both on create and on write.

## Enrollment header unique-per-course race condition:
- Two concurrent transactions could each pass the pre-check and create two live enrollments for the same student/course. Closed defensively with a partial unique index (`ems.planning`-style) plus a friendly error translation, even though 0 real occurrences were found in dev or production data.

## Enrollment header tutor guard (cross-study + write access):
- A tutor could be blocked from confirming their own tutored student's enrollment in some cases, or allowed to act outside their real scope in others. Fixed with a cross-study `@api.constrains` and by switching `_is_blocked_tutor` to Odoo's `has_access('write')` instead of hand-duplicating the access rule's own condition in Python.

## Enrollment junction duplicate constraint:
- `ems.enrollment` (student × group × subject) had no uniqueness constraint at the DB level. Added `UNIQUE(student_id, group_id, subject_id)`; a migration deduplicates the 21 pre-existing duplicate triples found in production (42 rows, confirmed field-identical within each pair).

## grade_session_remove missing still-enrolled guard:
- `_ems_sync_grade_session_remove` had no guard against removing grade lines for a still-enrolled student, unlike its sibling `_ems_sync_attendance_template_remove`. Added a shared `_ems_still_enrolled()` helper used by both, for symmetry, even though the gap is currently unreachable via the ORM thanks to the new junction constraint above.

## Student import wizard data-quality gaps surfaced, not silently dropped:
- Two known data-quality edge cases (no matching Esfera group, tutor row with no document number) were previously only noted in a code comment, invisible to the person running the import. Both are now surfaced via a new `stats['warnings']` block shown in the import result.

## LimeSurvey block special-filter mutual exclusion:
- `special_wpi_enrolled`/`special_subject_enrolled` were two independent Booleans that could both be checked at once, an invalid combination the UI didn't prevent. Replaced with a single `special_type` Selection (radio widget), with a migration backfilling existing data. Added the block's first browser tour, which caught two real, pre-existing (not new) bugs along the way: the tour's `select` action doesn't work on Odoo's `SelectionField` widget (`selectByLabel` needed instead — Odoo JSON-stringifies the option value), and `widget="code"` fields are an Ace editor, not a plain textarea (needs `ace.edit(...).setValue()`).

## Google Workspace welcome emails had a hardcoded, centre-specific domain:
- Both `mail.template` welcome emails (student and staff) hardcoded `@elpuig.xeill.net` in the subject and a link, even though `res.company.google_ws_domain` already exists as a proper per-company configurable field and the surrounding Python already used it correctly everywhere else. Any other centre installing EMS would have gotten Puig Castellar's own domain in these emails regardless of their own configuration. Fixed to read the same configured field (`env.company.google_ws_domain`) consistently in the templates and in four Python call sites that previously each had their own inconsistent `or 'elpuig.xeill.net'` fallback (one of the four even read a different field, `company_id` instead of `env.company`) — extracted into one shared `_gw_domain()` helper on `GoogleWorkspaceMixin` that raises a clear error if the domain isn't configured, rather than silently falling back to a literal that only made sense for one specific centre.

# Internal changes

## `data/custom/` fully migrated to the `__import__.` xmlid prefix:
- Closed a long-standing backlog: all 140 remaining XML records under `data/custom/` (`ems.planning`, `ems.course`, `ems.authorization.template`, `ir.sequence`) converted to CSV and rescoped to `__import__.`, so an EMS module upgrade can never again silently delete centre-specific configuration. One file (`ems_enrollment_template_opt.xml`) stays XML as a confirmed, permanent exception — its `product_id` is resolved via a dynamic domain search with no static external id to reference, which CSV cannot express.
- Along the way, fixed a real migration bug found only by testing against a genuine `./upgrade.sh` run (not the test suite, which happened to bypass it): the IBAN-trust backfill migration would have failed on a real production upgrade because `res.partner.bank`'s trust check explicitly refuses `SUPERUSER_ID` unless `install_mode` is set in context.
- Also fixed a second, unrelated latent bug surfaced by the same testing: one `ems.course` row had a legacy `NULL` boolean (from before the field existed on the model) that a plain data-file resync could never have corrected on its own, since Odoo's ORM reads `NULL` and `False` as equivalent — backfilled explicitly via a one-time migration.
- Documented the exact, empirically-verified mechanics of Odoo's data-loading system (the `__import__` module-ownership check vs. the separately-stored `noupdate` flag are two independent mechanisms, easy to conflate) in a new technical reference (`docs/en/developers/shared/data_loading.md`), including a capability table of what XML can do that CSV genuinely cannot (and vice versa) and a decision framework for `noupdate=True` vs `False`, cited against Odoo's own official documentation.

## `data/main/`+`data/cat/` XML files reviewed against the same criteria:
- Applied the same "XML only where CSV genuinely can't" discipline to the remaining XML files outside `data/custom/`. Six of seven converted to CSV; two of those were deleted outright rather than converted 1:1 (`ems.job_group_relationship.xml`/`ems.role_group_relationship.xml` only ever existed to add one field to records already declared elsewhere — folded directly into the existing files instead).
- Reviewed all three files that were `noupdate="1"` for undocumented reasons. Two (`ems.mail_activity_type.xml`, `res.partner.category.xml`) had no real justification and are now `noupdate=False`/CSV — EMS can freely improve cosmetic/business-label content it fully controls. One (`ems.schedule_framework_default.xml`) turned out to be this centre's own live, in-use bell-schedule template (traced via its actual consumers, not assumed) and correctly stays `noupdate=True`/XML.
- Moved two `mail.template` records that were sitting directly in `data/` (outside all three documented subfolders) into `data/main/` as CSV, alongside the domain-hardcoding fix above.
