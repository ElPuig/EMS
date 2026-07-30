# Technical Reference: `ems.student.document`

## Overview

`ems.student.document` is the reviewable-submission model behind the "Document management" workflow: a student or family uploads (or the secretary/admin registers) a document — an ID card, a medical card, an IBAN, proof of a benefit/exemption — which then goes through a pending → approved/rejected/cancelled review cycle. Approving certain document types has real side effects elsewhere in the app: an approved IBAN updates the student's bank account (`res.partner.bank`), an approved benefit document creates/refreshes an [`ems.student.benefit`](contact.md#emsstudentbenefit) line.

**Module file:** `models/contacts/student_document.py` (`EmsStudentDocument`)

---

## Status lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: create()
    pending --> approved: action_approve()
    pending --> rejected: action_reject()
    pending --> cancelled: action_cancel()
    approved --> pending: action_reset_to_pending()
    rejected --> pending: action_reset_to_pending()
```

Every transition drops any pending review `activity_ids` first (approve/reject/cancel all clear them; reset schedules a fresh one) and posts a chatter message. Creation and reset post an **internal note** (`mail.mt_note` — does not email followers, since the reviewer is already notified via their activity, see below); approve/reject post a **comment** (`mail.mt_comment` — does email the student, the only follower, see `create()` below).

### Who is notified, and how

```mermaid
flowchart LR
    A[create pending document] --> B["message_subscribe(student only)"]
    A --> C["_schedule_review_activities()"]
    C --> D["mail.activity.type._ems_get_task_users(...)\n(Task Assignment config, not a security group)"]
    D --> E["one 'to-do' activity per reviewer"]
    C --> F["_unsubscribe_reviewers()\n(keeps them off message_partner_ids)"]
```

Two deliberately separate notification channels, to avoid double-emailing anyone:
- **The student** is the only chatter follower — they get emailed on `action_approve`/`action_reject` (a `mail.mt_comment` post), which is the outcome they actually need to hear about.
- **Reviewers** (secretary/admin configured in *Academic Management > Configuration > Task Assignment*, keyed off the `ems.mail_activity_student_document_review` activity type — see `docs/en/developers/shared/task_assignment.md`) get a **to-do activity** instead of a chatter subscription; `mail_activity_quick_update` suppresses Odoo's own "X assigned you an activity" email (would otherwise read as if the submitting family were assigning work to the office), and `_unsubscribe_reviewers` keeps them off `message_partner_ids` so the later approve/reject comment doesn't double-notify them either.

---

## Approval side effects

### `_apply_bank_account()` — `doc_type == 'iban'`

```mermaid
flowchart TD
    A["action_approve() on an iban document"] --> B{"res.partner.bank with the\nsame acc_number already exists\nfor this student?"}
    B -- yes --> C["reactivate it, refresh holder name,\nallow_out_payment=True"]
    B -- no --> D["deactivate every other bank account\nof this student"]
    D --> E["create a new res.partner.bank,\nallow_out_payment=True"]
    C --> F["deactivate every OTHER bank account\nof this student"]
```

Only one bank account stays `active` per student at a time — approving a new IBAN always deactivates any other. `allow_out_payment=True` is set explicitly: the secretary has just validated the IBAN by approving it, and without this flag a direct-debit invoice referencing the account would be blocked (or silently drop the bank reference). `_check_single_pending_iban` (`@api.constrains`) additionally blocks a **second pending** IBAN submission for the same student — one at a time in the queue, though any number can be `approved`/`rejected`/`cancelled` historically.

### `_apply_benefit()` — `doc_type == 'benefit'`

Removes any existing `ems.student.benefit` of the **same** `benefit_type` for this student (not all benefits — a student can hold several different benefit types at once, see [`contact.md`](contact.md#emsstudentbenefit)), computes `renewal_date` by replaying `ems.student.benefit`'s own `_onchange_benefit_type` on a virtual (`.new()`) record rather than duplicating that date logic here, then creates the new benefit line carrying over the uploaded file as its supporting document.

### `action_approve()`'s own document-level dedup

Independently of the two side effects above, approving a document also deletes any **other already-approved** `ems.student.document` of the same `doc_type` (+ `benefit_type` too, for benefit documents) for this student — e.g. approving a new DNI scan removes the previously-approved one, so the review queue/history doesn't accumulate stale approved duplicates.

---

## `_compute_doc_file_link`

A non-stored `Html` field building a download link (`/web/content/<attachment_id>?download=false`) from the `doc_file` attachment, used in the read-only embed on the student's own form (list columns can't render a `Binary` field as a clickable link directly). Looks up the `ir.attachment` by `(res_model, res_field, res_id)` rather than reading `doc_file`'s own implicit attachment id, since the field itself only exposes the base64 content, not the attachment record.

---

## `_doc_label()`

Small shared helper (`dict(self._fields['doc_type'].selection).get(self.doc_type, ...)`) — the human-readable, current-language label for a document's type. Used by `_compute_name`, every chatter message, and `_schedule_review_activities`'s task summary, so the six near-identical message bodies across `create()`/`action_approve()`/`action_reject()`/`action_cancel()`/`action_reset_to_pending()` don't each re-derive it.

---

## Access Control

### `ir.model.access.csv`

| Role | Create | Read | Write | Delete |
|------|:------:|:----:|:-----:|:------:|
| Academic admin | ✓ | ✓ | ✓ | ✓ |
| Secretary | ✓ | ✓ | ✓ | ✓ |
| Portal (`base.group_portal`) | — | ✓ | — | — |

### `security/rules/portal.xml` — `rule_ems_student_document_portal`

Domain: `partner_id in [self, parent, children]` — a portal user can only ever *read* their own, or their family's, document submissions.

**Fixed during this DTON pass (2026-07-28):** the portal `ir.model.access.csv` row previously granted `perm_write=1` with **no** matching `ir.rule` restriction on write (the rule explicitly had `perm_write=False`, meaning its domain never applied to write at all) — so, in principle, any authenticated portal user could have written to **any** student's document record via a direct RPC call, not just their own. Not exploitable through the normal app (every real mutation for the portal flow goes through `sudo()` in `controllers/portal_enrollment.py`, which never relies on the portal user's own ORM permissions), but a live, unused permission gap regardless — closed by setting `perm_write=0` on the access row (create was already `0`, matching the fact that the portal flow only ever creates via `sudo()`). The `ir.model.access.csv` fix propagates on a normal upgrade (not a `noupdate` file); the companion `ir.rule` cleanup (aligning its `perm_create` flag, itself already inert since ACL blocked create either way) lives in a `noupdate="1"` data file and therefore only takes effect on fresh installs — harmless, since the ACL row alone is what enforces the restriction on any already-upgraded environment.

---

## Fixed (2026-07-30): portal IBAN renewal now always trusts the bank account

**Root cause, confirmed against a real production backup** (see `plans/student_document_iban_renewal_allow_out_payment.md` for the full investigation — plan file kept until the migration has run in production): `controllers/portal_enrollment.py`'s `/my/documentacion/renew-iban` route could create/renew an **already-`approved`** `ems.student.document` without ever calling `_apply_bank_account()` — unlike `action_approve()` (the review-queue path), which always sets `allow_out_payment=True` on the resulting `res.partner.bank`. The confirm-matrícula portal gate only checks the *document's* `status == 'approved'`, not the bank's trust flag, so a family could satisfy "IBAN vàlid registrat" and confirm their enrollment while the bank stayed untrusted underneath. 100% of the 332 already-posted direct-debit invoices found affected in production went through this exact renewal path, never through `action_approve()`.

A second, independent attempt (`enrollment.py`'s invoicing-time fallback, force-setting `allow_out_payment=True` right before posting) does not reliably work — Odoo's own `account_move` validation (an anti-fraud check, `res.partner.bank._user_can_trust()`) strips an untrusted bank reference from the invoice under certain sudo/portal contexts regardless. Relying on it was fighting against a deliberate Odoo security check rather than a real fix.

**Three-part fix:**
1. `portal_documentation_renew_iban` now calls `_apply_bank_account()` in both branches (new document, and bumping the expiry of an existing one) — an approved IBAN document via the portal now always trusts its bank, exactly like the review-queue path. Tested in `tests/test_portal_enrollment.py` (a genuine `HttpCase` hitting the real route).
2. `migrations/18.0.0.22.0/post-migrate.py::_backfill_iban_trust` re-applies `_apply_bank_account()` for every already-approved IBAN document, fixing the historical gap (408 students in production were in this inconsistent state). Tested in `tests/test_student_document.py`.
3. `enrollment.py`'s invoicing-time fallback no longer attempts to silently self-grant trust — it now raises a clear `ValidationError` if the bank isn't approved yet, since points 1-2 mean this should no longer be reachable through normal use; if it is, the actual approval step was skipped and that should be surfaced, not papered over. See the "Billing" section of `enrollment.md`.

---

## Views

| View | File | Notes |
|------|------|-------|
| List/Form/Search | `views/community/contact/student_document.xml` | `view_student_document_list/_form/_search` — the **only** place Approve/Reject/Reset are reachable; header statusbar + buttons |
| Action | same file | `action_student_document`, `context: {'search_default_pending': 1}` |
| Menu | `views/academic_management/enrollment_configuration/menu.xml` | `menu_student_documents`, under *Academic Management* (not under the Educational Community / Students menu tree — easy to miss when looking for it there) |
| Read-only embed | `views/community/contact/form.xml`, "Documentation" page | `document_ids` one2many, `create="0" delete="0"`, no action buttons — review only happens from the standalone screen above |
