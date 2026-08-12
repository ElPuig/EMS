# Technical Reference: Enrollment authorizations (`ems.authorization*`)

## Overview

Four models cover the "the family must accept/reject this before the
enrollment can be confirmed" flow — image rights, school trips, health data,
sharing information with family, etc:

- **`ems.authorization.template`** — the reusable definition (legal text,
  whether it's mandatory, whether it can only be accepted, which
  level/study it applies to, optional extra data fields to collect).
- **`ems.authorization.field`** — an extra data field a template can ask
  for on acceptance (e.g. "passport number" for a trip authorization).
- **`ems.authorization`** — one row per (enrollment, template): the actual
  pending/accepted/rejected response, on [`sale.order`](enrollment.md)'s
  `ems_authorization_ids`.
- **`ems.authorization.response`** — one row per (`ems.authorization`,
  `ems.authorization.field`): the family's answer to an extra data field.

**Module file:** `models/enrollment/authorization.py`

---

## Fields

| Model | Field | Notes |
|-------|-------|-------|
| `ems.authorization.template` | `is_required` | If pending and required, blocks `sale.order.action_confirm()` (see [`enrollment.md`](enrollment.md#authorization-sync)). |
| | `acceptance_only` | If set, `ems.authorization.write()` rejects any attempt to set `status='no'` on its responses. |
| | `auth_type` | `image`/`trip`/`health`/`share`/`other` — drives `res.partner.auth_image`/`auth_trip`/`auth_healt`/`auth_share` (see below), not read anywhere else. |
| | `ems_level_ids` / `ems_study_ids` | Scope. Empty on both = applies to every enrollment; when both are set, an enrollment must match **both** (AND-of-scopes — see [`_matches_scope()`](#keeping-authorizations-in-sync-with-open-enrollments) below). |
| `ems.authorization` | `status` | `pending` → `yes`/`no`. Drives the confirm-blocking check and `res.partner`'s auth booleans. |
| | `legal_text_rendered` | Computed, `sanitize=False` — `template_id.legal_text` with `{{student_name}}`/`{{academic_year}}`/`{{study_name}}` placeholders substituted. Feeds both the portal response page and `report_authorization_certificate`. |
| | `signed_document` / `signed_document_name` | For an internal (staff) response, required before the status can leave `pending` (enforced in `write()`). For a portal response, the controller generates and attaches the certificate PDF itself right after the write — see [Portal response flow](#portal-response-flow) below. |
| | `response_date` / `response_uid` | Set automatically by `write()` whenever `status` leaves `pending` — never set directly by a caller. |
| `ems.authorization` | `_sql_constraints: unique_enrollment_template` | One row per (enrollment, template) — this is what `action_apply_to_open_enrollments`'s "already has this template" check exists to avoid violating. |

---

## Keeping authorizations in sync with open enrollments

Two entry points keep `ems.authorization` rows in step with which templates
apply to which enrollment, and they run at different times — both now share
the same matching rule via `ems.authorization.template._matches_scope(level,
study)`:

```mermaid
flowchart TD
    subgraph "Template-driven (this file)"
        A["ems.authorization.template.create()"] --> B["action_apply_to_open_enrollments()"]
        C["action_remove_from_open_enrollments()\n(called manually, e.g. template\nretired/rescoped)"] --> D["delete pending rows on\ndraft/sent enrollments only\n— answered rows always protected"]
    end
    subgraph "Enrollment-driven (enrollment.py)"
        E["sale.order onchange\nems_level_id / ems_study_id\nor apply_authorizations()"] --> F["_get_authorization_commands()"]
    end
    B --> G["_matches_scope(level, study)\nAND-of-scopes: an empty ems_level_ids/\nems_study_ids applies to everything;\na set one requires the given value\nto be among it"]
    F --> G
```

### Fixed (2026-07-30): unified AND-of-scopes matching

Previously, `action_apply_to_open_enrollments` (this file) used an AND-of-scopes
(level *and* study must both match, when both are set on the template), while
`sale.order._get_authorization_commands()` (`enrollment.py`, driving the live
onchange sync and `apply_authorizations()`) used an OR-of-scopes instead — the
same template, applied to the same enrollment, could gain or lose the
authorization depending purely on which code path last touched it. Confirmed
against production data that no existing template used both scoping
dimensions at once, so this was a latent inconsistency, not an active bug —
but the developer decided both paths should use AND, matching the
template-driven side, ahead of ever needing a template scoped to both a level
and a specific study within it.

Fixed by extracting the shared `_matches_scope(level, study)` predicate onto
`ems.authorization.template` (see the diagram above) — both directions now
call it instead of hand-rolling their own domain, so they can't drift apart
again. Tested in `tests/test_authorization.py` (template → matching
enrollments) and `tests/test_enrollment_header.py` (enrollment → matching
templates), both exercising the same both-scopes-set case. See also the
[`enrollment.md`](enrollment.md#authorization-sync) side of this coupling.

---

## `res.partner` auth booleans

`ems.contact` (`models/contacts/contact.py`) exposes four derived flags —
`auth_image`, `auth_trip`, `auth_healt`, `auth_share` — computed from every
`ems.authorization` with `status == 'yes'` on the student's **current
course** enrollments, grouped by `template_id.auth_type`:

```mermaid
flowchart LR
    A["res.partner._compute_auth_booleans()"] --> B["for each sale_order where\nems_course_id = current course"]
    B --> C["for each ems_authorization\nwith status = 'yes'"]
    C --> D["auth_image / auth_trip /\nauth_healt / auth_share = True\naccording to template auth_type"]
```

`ems.contact.ems_authorization_ids` (a plain read-through, all of the
student's current-course authorizations, not filtered by status) is a
separate computed field, used e.g. by the contact form's read-only
authorizations tab (`views/community/contact/form.xml`).

**Bug fixed in this pass:** `_compute_ems_authorization_ids` had no
`@api.depends` at all — a non-stored compute field with no dependencies is
never invalidated by a later write within the same transaction/environment,
so a form or test that read `ems_authorization_ids` once and then created a
new enrollment/authorization for that same student in the same transaction
would keep seeing the stale (pre-creation) value until a fresh
environment/request came along. Fixed with
`@api.depends('sale_order_ids.ems_authorization_ids', 'sale_order_ids.ems_course_id')`,
mirroring the depends already correctly declared on the neighboring
`_compute_auth_booleans`. Regression test:
`tests/test_contact.py::TestContactFields::test_ems_authorization_ids_recomputes_within_same_transaction`.
`strike.py`'s minor-notification logic reads `student.auth_share` directly
(see [`strike.md`](../coexistence/strike.md)) — not affected by this bug
since it doesn't chain through `ems_authorization_ids`.

---

## Response rules (`ems.authorization.write()`)

```mermaid
flowchart TD
    A["write(vals)"] --> B{"status in vals\nAND status != pending?"}
    B -- no --> H{"signed_document\ncleared?"}
    B -- yes --> C{"status == 'no' AND\ntemplate.acceptance_only?"}
    C -- yes --> X["ValidationError"]
    C -- no --> D{"no document attached\n(vals or existing)\nAND caller is internal\n(base.group_user)?"}
    D -- yes --> Y["ValidationError"]
    D -- no --> E["response_date = now()\nresponse_uid = caller"]
    E --> H
    H -- yes --> I["response_date = False\nresponse_uid = False"]
    H -- no --> F["super().write(vals)"]
    I --> F
```

Portal users (`base.group_portal`, never `base.group_user`) are exempt from
the document requirement — the portal controller attaches the generated
certificate right after this write succeeds, so requiring one *before* the
write would make the portal flow impossible.

---

## Portal response flow

`controllers/portal_enrollment.py` (not part of `models/enrollment/`, so
out of this pass's direct scope, but the primary consumer of this file's
models — documented here for the coupling, not re-tested):

```mermaid
flowchart TD
    A["POST /my/gestion-matriculas/authorize/&lt;auth_id&gt;"] --> B{"auth belongs to the\nlogged-in portal student?"}
    B -- no --> Z["redirect, log warning"]
    B -- yes --> C{"acceptance_only AND\ndecision == 'no'?"}
    C -- yes --> Z
    C -- no --> D["validate required\nems.authorization.field responses"]
    D --> E["auth.write({status, response_date, response_uid})\n— response_date/uid re-set by the\nmodel's own write() regardless"]
    E --> F["replace ems.authorization.response rows"]
    F --> G["render report_authorization_certificate\n→ attach as signed_document"]
    G --> H["redirect back to /my/gestion-matriculas"]
```

`/my/gestion-matriculas/authorization/<auth_id>/document` serves the
attached `signed_document` back (inline PDF), same ownership check as
above. Neither portal route has automated test coverage today — flagged as
a gap, not filled in this pass (see "Not covered by this pass" below).

---

## Views

| View | File | Notes |
|------|------|-------|
| List/Search/Form | `views/academic_management/enrollment_configuration/enrollment_authorization_{view,search,form}.xml` | Configuring `ems.authorization.template`; `action_ems_authorization_template`, under Academic Management → Configuration (admin + secretary, both full CRUD — see `security/ir.model.access.csv`). |
| Enrollment form | `views/academic_management/enrollment/enrollment_form.xml` | `ems_authorization_ids` embedded on the enrollment itself. |
| Contact form | `views/community/contact/form.xml` | Read-only `ems_authorization_ids` tab on the student. |
| Portal | `views/portal/portal_enrollment_draft.xml` | The family-facing accept/reject UI — already documented from the user side in `docs/en/families/manual-confirmacio-matricula.md`, "Step 2 — Responding to the authorizations". |
| Report | `reports/authorizations/report_authorization_certificate.xml` | The signed-response certificate PDF, rendered by the portal controller and attached as `signed_document`. |

## Data

Seed templates: `data/custom/ems_authorization_template_data.xml`
(`__import__.`-prefixed, centre-owned).

## Access control

Admin and secretary both get unrestricted CRUD on all four models
(`security/ir.model.access.csv` + `security/rules/contacts.xml`). Teachers
get read-only on `ems.authorization`; tutors get create/write (not unlink)
restricted to `enrollment_id.partner_id.tutor_id.user_id = user.id` — the
same OR-combination and tutor-identity pattern documented for `sale.order`
in [`enrollment.md`](enrollment.md#tutor-blocking-guards). Portal users get
read/write (no create/unlink) on `ems.authorization`, scoped to their own
or their child's enrollments (`security/rules/portal.xml`).

## Not covered by this pass

- `controllers/portal_enrollment.py`'s authorize/document routes have zero
  automated test coverage (no `HttpCase`) — flagged, not filled here; this
  pass's scope was the `ems.authorization*` models themselves.
- No dedicated secretary/admin user doc for *configuring* templates was
  written — same reasoning as `enrollment_template.md`: it's a small,
  self-explanatory backend config screen with no complex workflow of its
  own. The family-facing *response* flow already has a thorough manual
  (`docs/en/families/manual-confirmacio-matricula.md`).
- The AND-vs-OR matching-semantics gap above.

## Fixed in this pass (2026-07-28)

`ems.authorization.write()`'s three separate `if 'status' in vals and
vals['status'] != 'pending':` blocks merged into one pass over `self`
(same condition checked three times before). Two previously-untranslated
`ValidationError` strings wrapped in `_()`, with new `ca_ES`/`es_ES` `.po`
blocks. Spanish inline comments translated to English throughout. Decorative
step-numbering comments ("1. Create the templates...", "2. Apply
retroactive logic...") trimmed in favor of docstrings, per the project's
"don't explain WHAT" comment convention. `_order` added to
`ems.authorization.template` (`name`) and `ems.authorization` (`id`) — no
default order existed before. `contact.py`'s missing `@api.depends` bug
(above) fixed as part of this pass since it's this file's primary
consumer, not deferred to a future `ems.contact` revisit.
