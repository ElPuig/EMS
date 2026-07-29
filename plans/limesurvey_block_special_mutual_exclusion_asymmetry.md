# PLAN — `ems.limesurvey_block._onchange_special`'s mutual exclusion is asymmetric

> **Status: flagged during the `limesurvey.py` DTON pass, Block 5 (2026-07-29), not
> implemented.** This is not a design for new work — it's an open question for whoever owns
> the LimeSurvey block UI to answer before any fix is written. Nothing below has been built.
> Verify file/line references against current code before acting, since the branch may have
> moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once the
> question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/communications/limesurvey.md`).

## Problem

`ems.limesurvey_block` has two boolean flags meant to be mutually exclusive —
`special_wpi_enrolled` and `special_subject_enrolled` — enforced by:

```python
@api.onchange("special_wpi_enrolled", "special_subject_enrolled")
def _onchange_special(self):
    for block in self:
        # TODO: mutually excluded, check if it's more appropiate to use radios instead of checkboxes.
        if block.special_wpi_enrolled: block.special_subject_enrolled = False
        elif block.special_subject_enrolled: block.special_wpi_enrolled = False
```

The `elif` branch can only execute when `special_wpi_enrolled` is already falsy (otherwise the
`if` branch already fired) — so `block.special_wpi_enrolled = False` in that branch is a
no-op in every reachable case; there is no state where it actually clears a `True` value.

**Concrete effect:** if a user checks "WPI" first, then checks "Subject (all enrolled)" too,
the onchange re-fires and the `if` branch wins — "Subject" is silently reverted to `False`
immediately, with no visible feedback that the checkbox "didn't take". The reverse order
(checking "Subject" first, then "WPI") works as expected — "Subject" gets cleared. So the
mutual exclusion only works in one direction, not symmetrically as the field pair's intent
implies.

## Why not fixed in this pass

The TODO comment already sitting above this code acknowledges the general shakiness of doing
mutual exclusion this way ("check if it's more appropriate to use radios instead of
checkboxes") — but doesn't specify what the *current* code should do in the meantime. Two
reasonable fixes exist and picking between them is a product decision, not a mechanical bug
fix:

1. **Keep checkboxes, fix the asymmetry** — track which field actually changed (Odoo onchange
   doesn't tell you this directly; would need `@api.onchange` split into two separate methods,
   one per field, each unconditionally clearing the other) so whichever was toggled *last*
   wins, symmetrically.
2. **Follow the TODO's own suggestion** — replace both booleans with a single `Selection`
   field (radio-button UI), which makes "mutually exclusive" structurally guaranteed instead
   of onchange-enforced. This is a bigger change: touches the view, and potentially any other
   code reading `special_wpi_enrolled`/`special_subject_enrolled` directly (see
   `compute_survey_data` in `ems.limesurvey_header`, which branches on both).

## Where this is also documented

`docs/en/developers/communications/limesurvey.md`, Block 5 section — a one-line pointer to
this plan file.
