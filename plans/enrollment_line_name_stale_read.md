# PLAN — `sale.order.line.name` can be transiently stale (side-effect field, not tracked)

> **Status: flagged during the `enrollment_line_extension.py` DTON pass (2026-07-28), not
> implemented.** This is not a design for new work — it's an open question for whoever
> owns the enrollment-line pricing logic to answer before any fix is written. Nothing below
> has been built. Verify file/line references against current code before acting, since the
> branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/enrollment/enrollment_line.md`).

## Problem

`SaleOrderLine._compute_price_unit` (`models/enrollment/enrollment_line_extension.py`)
assigns `line.name` as a side effect, for fee lines only:

```python
@api.depends('product_id', 'order_id.order_line', 'order_id.partner_id.benefit_status')
def _compute_price_unit(self):
    ...
    for line in lines:
        if line.product_template_id.ems_is_enrollment_fee:
            ...
            line.price_unit = min(count * unit_cost, max_fee)
            base_name = f"{line.product_template_id.name} ({count} Subjects)"
            ...
            line.name = f"{base_name}{benefit_suffix}"
```

`price_unit` has a proper `@api.depends` and is a real tracked computed field. `name` does
not — it's a plain `Char` field that happens to get overwritten as a side effect whenever
this method runs *for other reasons* (because `price_unit` needed recomputing). Odoo's
dependency-invalidation machinery only knows to invalidate/recompute `price_unit` when its
declared dependencies change; it has no way to know `name` is also produced here, so
`name`'s cached/stored value is never proactively invalidated the same way.

## Confirmed reproduction

Creating a fee line together with a sibling subject line in one batch write
(`order.order_line = [(0,0,subject_line_vals), (0,0,fee_line_vals)]`) and reading
`fee_line.name` **before** ever touching `.price_unit` in the same transaction returns a
stale `"... (0 Subjects)"` — computed during an earlier, premature pass of this method that
ran before the sibling subject line was fully visible to it (a timing artifact of batch o2m
record creation). Reading `.price_unit` first correctly triggers a fresh recompute (via its
`@api.depends`), which also fixes `.name` as a side effect of that same call — so read order
matters. `tests/test_enrollment_line.py::test_fee_line_name_includes_subject_count` had to
add `self.env.flush_all()` before asserting on `.name`, to force the same settling any fresh
transaction naturally gets before commit.

## Why this is unlikely to be user-visible today

Normal UI usage creates enrollment lines and confirms the order in **separate requests**
(separate transactions) — a secretary/tutor fills the form and saves (which flushes), then
later clicks Confirm (a new transaction, reading already-settled DB values). Odoo also
flushes all pending computes before every transaction commit, so any transaction *after* the
one that created the lines always sees consistent, correct values. The risk is narrow:
**only** code that creates enrollment lines and reads `line.name` in the *same* transaction,
before `price_unit` is read/recomputed, could observe the stale value.

## Open questions (need an answer before touching the code)

1. Does any real code path in this codebase actually create lines and read `.name` in the
   same transaction? Candidates worth checking: `_ems_generate_enrollment_invoice()`'s
   `_create_invoices()` call (native Odoo's invoice-line preparation reads `line.name`) —
   does this ever run in the *same* transaction as the lines' own creation (e.g. a
   programmatic flow that creates an order with lines and immediately confirms it, rather
   than two separate user actions)? If `action_confirm()` is always a separate request from
   whatever created the lines, this is moot in practice.
2. If a fix is warranted, which approach: (a) make `name` a real `@api.depends`-tracked
   compute (loses the ability for a user to manually rename a line, unless combined with
   `readonly=False` like `product.template.ems_study_ids`'s editable-compute pattern — see
   `docs/en/developers/enrollment/enrollment_product_extension.md`); (b) explicitly call
   `self.flush_recordset()`/re-touch `price_unit` at the end of whatever creates lines in
   bulk, papering over the specific batch-creation timing issue without changing the field's
   contract; (c) leave as-is, since real-world exposure appears to be zero.

## Where this is also documented

`docs/en/developers/enrollment/enrollment_line.md`, "Known gap: `name` is a side-effect
field, not a tracked compute" section — stays even after this plan file is deleted; update
it if the resolution differs from what's written there today.
