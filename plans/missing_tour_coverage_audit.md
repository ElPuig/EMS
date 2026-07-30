# PLAN — Audit and fill missing browser tour coverage across EMS

> **Status: flagged 2026-07-30, not started.** Requested by the developer after a concrete
> incident: a checkbox-to-radio widget change on `ems.limesurvey_block`'s form
> (`plans`/memory: `limesurvey_block_special_mutual_exclusion_asymmetry`, now resolved) was
> initially shipped with no tour, on the reasoning "no tour exists for this view" — which
> is itself the gap, not a reason to skip verification. Adding the tour afterward (per the
> developer's explicit ask) caught two real, non-trivial browser-only bugs that no amount of
> `./upgrade.sh`/`TransactionCase` testing would ever have surfaced (see below). This plan is
> the systematic follow-up: how many other views are in the same unverified state, and what
> order to close them in.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete once the audit is
> complete and either every gap is closed or explicitly triaged/deferred with reasoning
> recorded somewhere durable (this file, or the relevant model's dev doc).

## Why this matters (not just a coverage-percentage nit)

`./upgrade.sh` succeeding only proves a view's XML is structurally valid — every field
referenced exists on the model, every widget is compatible with its field's type (Odoo
validates this on every module load/upgrade, not just in test mode). It proves **nothing**
about whether the page actually renders correctly in a browser, or whether an interaction a
user would actually perform (click, type, select) works. `TransactionCase` tests never touch
the browser/OWL layer at all. Only an `HttpCase` tour, run through Odoo's real headless-Chrome
test harness, catches that class of bug.

**Concrete proof this isn't theoretical:** writing the first tour for `ems.limesurvey_block`
(2026-07-30) immediately caught two bugs that had shipped invisibly:
1. `run: "select students"` on a plain Selection `<select>` silently failed to select
   anything — Odoo's `SelectionField` widget JSON-stringifies the option `value` attribute
   (`stringify(option[0])`), so the raw selection key never matches. The **existing, already-
   shipped** `target` field on this exact form has had this same widget type since before this
   pass — meaning the header form's Target field may have been just as fragile to certain
   interactions, just never actually driven by anything that would have revealed it.
2. `tsv_raw_text` (`widget="code"`, used on both the header and block forms, and potentially
   elsewhere) renders via the Ace editor library — its real input element is a deliberately
   invisible textarea that the tour engine's generic `edit` action can't drive at all;
   filling it requires calling into the global `ace` object directly.

Neither of these is specific to the `special_type` change — they're pre-existing
characteristics of widgets used **elsewhere in the module** too. Any other view using
`widget="code"` or being driven through a `<select>` in a not-yet-written tour is an unknown
until it's actually tested.

## Rough scope (quick count, 2026-07-30 — not a precise audit)

- 26 tour files currently exist (`static/tests/tours/*.js`).
- 72 distinct `ir.actions.act_window` ids are defined across `views/`.
- 52 files under `views/` contain at least one `<form>`.

Even accounting for actions that share a tour, or models genuinely covered indirectly through
another model's tour (e.g. an embedded one2many form, like `ems.limesurvey_block` itself used
to be before 2026-07-30), this suggests a large fraction of the module's form/list/kanban
surface has never been driven by a real browser. The exact list needs the actual audit below,
not this rough count.

## Proposed approach

1. **Enumerate real gaps**, not just a file-count mismatch: for every model with a view
   (`grep` `<form>`/`<list>`/`<kanban>` under `views/`), check whether it's reachable from an
   *existing* tour — either as the tour's own primary target, or embedded inside another
   model's form (matching the "secondary/embedded view" requirement already in `CLAUDE.md`'s
   Development workflow). Produce a concrete list of models/views with **zero** tour coverage
   today — this is real, non-trivial exploration work, likely worth delegating to an `Explore`
   agent given the breadth (many files, cross-referencing views against tour files).
2. **Triage, don't blanket-fix**: not every gap is equally worth closing immediately — a
   rarely-touched admin config screen is lower priority than a screen teachers/families use
   daily. Group the findings by rough priority (role-facing frequency, complexity of the view,
   whether it's read-only/reference data vs. something users actively edit) rather than
   working through them alphabetically.
3. **Fix incrementally**, one model/view at a time, each as its own small Red-Green cycle
   (write the tour, confirm it currently would have nothing to catch since the view isn't
   changing, but still run it to prove the view itself renders and basic interactions work) —
   not as one giant PR. Reuse the two gotchas found above (`selectByLabel` for plain
   `<select>`s, `ace.edit(anchor).setValue(...)` for `widget="code"`) rather than
   rediscovering them per file.
4. Going forward, per the now-updated `CLAUDE.md` Development workflow: **any new change to a
   model with a UI surface gets a tour as part of that same change**, closing off new gaps
   from accumulating while this backlog is worked through.

## Open questions

1. Should this be one large sweep, or folded opportunistically into whatever model each future
   session happens to be touching anyway (mirroring how the original DTON rollout worked
   model-by-model)? The DTON rollout precedent suggests the latter is more sustainable, but
   the developer may want a dedicated push instead.
2. Is there a way to make "view has no tour" mechanically checkable (e.g. a script comparing
   `views/` against `static/tests/tours/`) so this doesn't silently regress again, or is manual
   vigilance (now reinforced in `CLAUDE.md`) enough?

## Where this is also documented

Not yet documented elsewhere — this plan is the only record until the audit produces
per-model findings worth folding into individual dev docs.
