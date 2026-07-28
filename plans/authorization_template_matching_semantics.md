# PLAN — Two different level/study matching semantics for authorization templates

> **Status: flagged during the `ems.authorization*` DTON pass (2026-07-28), not
> implemented.** This is not a design for new work — it's an open question for whoever
> owns the authorization-template/enrollment coupling to answer before any fix is written.
> Nothing below has been built. Verify file/line references against current code before
> acting, since the branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/enrollment/authorization.md`).

## Problem

An `ems.authorization.template` is scoped to enrollments via two Many2many fields,
`ems_level_ids` and `ems_study_ids`. When both are empty it applies to every enrollment;
when either is set, an enrollment is supposed to "match" the template. Two different code
paths decide what "match" means, and they don't agree:

**Retroactive apply — template creation/reconfiguration**, `models/enrollment/authorization.py`,
`action_apply_to_open_enrollments()`:

```python
domain = [('state', 'in', ['draft', 'sent'])]
if self.ems_level_ids:
    domain.append(('ems_level_id', 'in', self.ems_level_ids.ids))
if self.ems_study_ids:
    domain.append(('ems_study_id', 'in', self.ems_study_ids.ids))
```

Plain `list.append()` — every condition present is AND-ed together. If a template has
*both* `ems_level_ids` and `ems_study_ids` set, an enrollment must match **both** to get
the authorization.

**Live sync — onchange on the enrollment itself**, `models/enrollment/enrollment.py`,
`sale.order._get_authorization_commands()`:

```python
domain = ['&', ('ems_level_ids', '=', False), ('ems_study_ids', '=', False)]
if self.ems_level_id:
    domain = ['|', ('ems_level_ids', 'in', self.ems_level_id.id)] + domain
if self.ems_study_id:
    domain = ['|', ('ems_study_ids', 'in', self.ems_study_id.id)] + domain
```

Built as nested `'|'` — a template matches if its level scope matches **OR** its study
scope matches **OR** it has no restriction on either. If a template has *both* fields set,
an enrollment only needs to match **one** of them.

## What this means concretely

A template with `ems_level_ids = [Batxillerat]` and `ems_study_ids = [Científic]` (a
specific study within that level, not "every Batxillerat study"):

- Via `action_apply_to_open_enrollments()` (fires once, at template creation/re-save): only
  attaches to open enrollments whose study is *specifically* Científic.
  A Batxillerat-Humanístic enrollment is correctly excluded.
- Via `_get_authorization_commands()` (fires on every level/study onchange on an existing
  enrollment): attaches to **any** Batxillerat enrollment, including Humanístic — because
  the level match alone satisfies the OR condition, regardless of the study restriction.

So the *exact same template*, applied to the *exact same enrollment*, can gain or lose the
authorization purely depending on whether it was captured by the one-time retroactive apply
at template-creation time, or by a later level/study change on that specific enrollment
re-triggering the onchange sync. Neither path is "wrong" in isolation — each is internally
consistent — but they silently disagree with each other on the same input.

## Why this hasn't caused a visible problem yet (as far as this pass could tell)

Every authorization template currently seeded in `data/custom/ems_authorization_template_data.xml`
appears to be scoped to level *or* study, essentially never both at once — so the AND vs OR
distinction is moot for existing production templates (with only one scoping dimension
set, both matching functions reduce to the same single condition). This is why no test
failure or user report surfaced it; it was only found by reading both matching functions
side by side while documenting them for the DTON pass, not from an observed bug.

## Open questions (need an answer before touching the code)

1. Was the AND-vs-OR difference intentional — e.g. "retroactive apply is meant to be
   conservative/narrow, live sync is meant to be permissive/broad" — or is one of them
   simply a copy-paste/reimplementation drift from the other?
2. If a real admin/secretary need ever arises for a template scoped to both a level and a
   specific study within it (e.g. "only Batxillerat-Científic students need this trip
   authorization, not the whole level"), which semantics should win?
3. Once decided, should the fix unify both functions to share one matching-logic helper
   (removing the duplication that let them drift apart in the first place), or is keeping
   them as two independently-tuned queries actually the right shape for this codebase?

## Where this is also documented

`docs/en/developers/enrollment/authorization.md`, section "Known gap: two different
matching semantics", and cross-linked from `docs/en/developers/enrollment/enrollment.md`'s
"Authorization sync" section — both stay even after this plan file is deleted; update them
if the resolution differs from what's written there today.
