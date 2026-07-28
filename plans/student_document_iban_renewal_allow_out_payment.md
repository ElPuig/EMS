# PLAN — Portal IBAN renewal never sets `allow_out_payment`

> **Status: flagged during the `ems.student.document` DTON pass (2026-07-28), not
> implemented.** This is not a design for new work — it's an open question for whoever
> owns `controllers/portal_enrollment.py`'s portal documentation flow to answer before any
> fix is written. Nothing below has been built. Verify file/line references against
> current code before acting, since the branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/contacts/student_document.md`).

## Problem

Two different code paths bring an `ems.student.document` of `doc_type == 'iban'` to
`status == 'approved'`. Only one of them keeps the resulting `res.partner.bank` record
usable for direct-debit collection.

**Normal path — review queue (`action_approve`)**, `models/contacts/student_document.py`:

```python
# action_approve(), per document, lines 179-182
if document.doc_type == 'iban' and document.doc_value:
    document._apply_bank_account()

# _apply_bank_account(), lines 272-301 — always, on both the "update existing"
# and "create new" branches:
existing.write({
    'active': True,
    'acc_holder_name': holder,
    'allow_out_payment': True,
})
```

**Portal path — `/my/documentacion/renew-iban`**, `controllers/portal_enrollment.py:420-456`:

```python
if iban_doc:
    # Already-approved IBAN doc exists: only bumps the expiry date.
    iban_doc.sudo().write({'expiry_date': new_expiry})
    # ... message_post, no call to _apply_bank_account()
else:
    # No doc yet, but the student already has an active bank account
    # (imported via CSV): create a document that starts life pre-approved.
    request.env['ems.student.document'].sudo().create({
        'partner_id': student.id,
        'doc_type': 'iban',
        'doc_value': bank.acc_number,
        'doc_value2': bank.acc_holder_name or student.name,
        'expiry_date': new_expiry,
        'status': 'approved',
    })
```

`create()` (`student_document.py:133-158`) only handles notification/activity scheduling
for documents that start `pending` — there is no hook that fires approval side effects for
a document created directly in `approved` state. So **neither branch of the portal renewal
route ever calls `_apply_bank_account()`**, and `allow_out_payment` is never touched by
either of them.

## What this means concretely

`allow_out_payment` (standard `account` module field on `res.partner.bank`) gates whether
that bank account can be used as the destination of an outgoing payment / direct debit.
With it `False`, posting a direct-debit invoice against that account is blocked (or the
bank reference is silently dropped, depending on the flow) — see `_apply_bank_account`'s
own comment.

Production data confirms every active bank account is currently in this state:

```sql
SELECT allow_out_payment, count(*) FROM res_partner_bank WHERE active = true
GROUP BY allow_out_payment;

 allow_out_payment | count
--------------------+-------
 false              |   224
```

Zero active accounts have the flag set. Consistent with none of them ever having gone
through `action_approve()`.

## Open questions (need an answer before touching the code)

1. Is there a separate process — script, import batch, manual step — that sets
   `allow_out_payment` for CSV-imported accounts outside this flow? If so, this is a
   harmless design inconsistency, not a live bug.
2. If not: are direct-debit charges for these 224 students currently failing, or has
   nobody reached the billing step for them yet? Determines urgency.
3. If it's a real gap: is "renew without re-approval doesn't grant trust" intentional
   (a renewed-only account is deliberately not treated as validated), or an oversight?
   The answer decides the fix — either have both portal branches also call
   `_apply_bank_account()` (or set the flag explicitly), or leave it as-is and record the
   reasoning in `student_document.md` instead of in this plan file.

## Where this is also documented

`docs/en/developers/contacts/student_document.md`, section "A known,
deliberately-not-fixed gap" — that section stays even after this plan file is deleted;
update it if the resolution differs from what's written there today.
