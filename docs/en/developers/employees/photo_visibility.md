# Photo visibility

Lets a teacher (or any employee with a linked user account) decide who else can see
their profile photo, with three levels: `public` (everyone), `private` (only Head of
Studies and above), and `no_photo` (permanently erased — GDPR/right-to-erasure). It's
set from **"My Profile"**, not from the employee's own form — teachers have read-only
access to `hr.employee` and that doesn't change for this feature.

Implemented in `models/employees/user.py` (`ems_users`, `_inherit = "res.users"`),
`models/employees/employee.py` (`ems_employee`, `_inherit = ["hr.employee"]`), and
`models/contacts/contact.py` (`ems_contact`, `_inherit = ["res.partner"]`).

## Why the linked contact needs its own copy too

The first iteration of this feature only gated `hr.employee.image_1920`. That looked
sufficient — every `many2one_avatar_employee` widget in the app reads from it — but it
missed every place that shows a **user's own** avatar instead of the employee's: the org
chart (`hr_org_chart`, which falls back to `employee.user_id`'s avatar whenever the
employee's own is empty — a fallback `hr.employee._compute_avatar` already provides
natively), `ems.notice.sent_by` (a plain `res.users` field), and — because `res.users`
delegates its image fields to `res.partner` via `_inherits` — Discuss, the chatter, and
the top bar, none of which go through `hr.employee` at all.

Rather than turning `res.partner.image_1920` into a conditional compute field (which
would touch every contact in the database — students, families, companies — for a
restriction that only ever applies to employee-linked users), this feature just writes
the *already-decided* image (real photo, or the initials placeholder) into
`res.partner.image_1920` directly, the same way an admin or the person themselves could
always have done by hand. `res.partner.image_1920` itself stays a completely ordinary
field.

## The placeholder, not a blank

When visibility isn't `public`, the field doesn't go blank — it's set to Odoo's own
initials-avatar SVG (`avatar.mixin._avatar_generate_svg()`, already inherited by both
`hr.employee` and `res.partner`/`avatar.mixin`). Storing the placeholder as the actual
image, rather than leaving the field empty, is what makes this genuinely global for free:
every consumer (avatar widgets, the org chart's employee-fallback, Discuss, the top bar)
already renders *whatever `image_1920` holds* — there's no separate "no image, draw a
generic icon" code path to special-case per consumer.

## Field layout

- **`res.users.image_visibility`** (`public`/`private`/`no_photo`, default `public`) is
  the only place this is actually set — from "My Profile". `hr.employee.image_visibility`
  is a derived, `store=True` mirror of `user_id.image_visibility` (falls back to
  `'public'` when the employee has no linked user) — nothing writes to it directly.
- **`hr.employee.image_private`** is the real photo storage, not `res.users`, because not
  every employee has a login (e.g. ASP/support staff) — an admin can still set their
  photo from the employee form. `res.users.image_private` is a thin `compute`+`inverse`
  mirror of `employee_id.image_private`, used only when editing from "My Profile".
- **`res.partner.image_private`** is a *separate* real field, only ever populated for the
  contact behind an employee-linked user (`models/employees/user.py`'s
  `_sync_partner_photo`) — empty and unused for every other kind of contact. It exists so
  the contact's pre-existing real photo (if it had one independently of
  `hr.employee.image_private` — e.g. uploaded via Settings > Users) is never lost once
  this feature starts overwriting `image_1920` with the placeholder.
- **`hr.employee.effective_photo`** is the real photo regardless of visibility: the
  employee's own `image_private`, or — if empty — the linked user's contact's own
  `image_private` (mirrors core Odoo's existing employee → user avatar fallback, so an
  employee who never had their own `hr.employee` photo, only ever one on their account,
  keeps working exactly as before).
- **`hr.employee.image_1920`** (`compute`, `store=True`, `inverse`) is `effective_photo`
  when `public`, otherwise the initials placeholder generated from the employee's own
  name.

```mermaid
flowchart LR
    subgraph "res.users (My Profile)"
        UV[image_visibility real field]
        UP[image_private compute+inverse]
    end
    subgraph "hr.employee"
        EV[image_visibility<br/>compute, store=True]
        EP[image_private<br/>real field]
        EFP[effective_photo<br/>compute, compute_sudo]
        E1920[image_1920<br/>compute, store=True, inverse<br/>real photo or initials placeholder]
        PV[photo_visible_to_current_user<br/>compute, depends_context uid]
    end
    subgraph "res.partner (linked contact)"
        PP[image_private<br/>real field, backfilled on first sync]
        P1920[image_1920<br/>plain field, pushed by res.users.write]
    end
    subgraph "consumers"
        WIDGETS[many2one_avatar(_employee) widgets<br/>attendance / grading / group / notice]
        ORGCHART[hr_org_chart<br/>via employee's own avatar_* fallback]
        GLOBAL[Discuss / top bar / ems.notice.sent_by<br/>read res.partner/res.users directly]
    end

    UV -- mirrors --> EV
    UP <-- sudo write / read --> EP
    EP --> EFP
    PP -. fallback when EP is empty .-> EFP
    EFP --> E1920
    EV --> E1920
    E1920 --> WIDGETS
    E1920 -. fallback when own avatar is empty .-> ORGCHART
    EV --> PV
    EP -. shown instead of image_1920 when authorized .-> Kanban[Teachers kanban / employee form]
    PV -. gates the swap .-> Kanban
    E1920 -- res.users.write pushes it --> P1920
    P1920 --> GLOBAL
```

## Sync to the linked contact (`res.users.write`/`_sync_partner_photo`)

Every write touching `image_visibility` or `image_private` on `res.users` triggers
`_sync_partner_photo`:

- **`no_photo`**: erases the real bytes for good — `employee.image_private` and
  `partner.image_private` both set to `False`. This is deliberately irreversible
  (GDPR/right-to-erasure): switching back to `public` afterwards just shows nothing until
  a new photo is uploaded, since there is nothing left to restore.
- **Otherwise**: if the contact doesn't have its own `image_private` yet, back up
  whatever `image_1920` currently holds into it — but only if that's a real photo, not
  Odoo's own auto-generated initials placeholder (checked by decoding the bytes and
  looking for the SVG signature, not by trusting `ir_attachment.mimetype` — overwriting an
  attachment's content in place does not necessarily re-detect its mimetype, so that
  column can go stale). Then push `employee.image_1920` (already correctly resolved —
  real photo or placeholder) into `partner.image_1920`.

## Access control

| Viewer | `public` | `private` | `no_photo` |
|---|---|---|---|
| The employee themselves | sees it | sees it | nothing to see |
| `ems.group_academic_admin` | sees it | sees it | nothing to see |
| `ems.group_head_of_studies` and above (director, admin) | sees it | sees it | nothing to see |
| Anyone else with `hr.employee` read access | sees it | placeholder | placeholder |
| Anyone reading `res.users`/`res.partner` (Discuss, top bar, org chart, `ems.notice.sent_by`) | sees it | placeholder, **always** — no authorized-viewer exception | placeholder, always |

`photo_visible_to_current_user` (on `hr.employee`, `@api.depends_context('uid')`)
implements the employee-side half of this table (self/admin/directive vs. everyone else).
It must **not** use `compute_sudo` — that would elevate `self.env.user` to the superuser
while computing, defeating the `has_group()` checks for the actual viewer.
`ems.group_head_of_studies` already implies director/admin (see `security/groups.xml`),
so "directive staff and above" needs no new group — a plain `has_group()` check covers
it.

No new `ir.model.access.csv`/`ir.rule` entries were added: teachers keep their existing
read-only access to `hr.employee`, unchanged.

## Known limitations

- **View-level only.** The restriction hides the photo in the UI; it does not block
  ORM/RPC-level reads of `image_private` for someone who already has model read access
  (teachers do, for all of `hr.employee`). This matches the existing rigor level used
  elsewhere in this module (e.g. the "special educational needs" field), not a new,
  weaker standard. `no_photo` is the exception: that one actually deletes the bytes, so
  there is nothing left to read regardless of access level.
- **The real photo is only ever restored to an authorized viewer in the "Teachers"
  kanban and the employee form** (`views/community/employee/{kanban,form}.xml`). Every
  `res.users`/`res.partner` consumer (Discuss, the top bar, the org chart,
  `ems.notice.sent_by`) shows the placeholder to *everyone*, including a Head of Studies
  or admin who would be authorized to see it on the employee's own kanban/form — building
  a per-viewer swap into core Odoo chrome (Discuss, the org chart's OWL component) is out
  of scope.
