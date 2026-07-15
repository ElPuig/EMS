# Photo visibility

Lets a teacher (or any employee with a linked user account) decide who else can see
their profile photo: everyone, only teachers and roles above them, or only directive
staff (Head of Studies and above). It's set from **"My Profile"**, not from the
employee's own form — teachers have read-only access to `hr.employee` and that
doesn't change for this feature.

Implemented in `models/employees/user.py` (`ems_users`, `_inherit = "res.users"`) and
`models/employees/employee.py` (`ems_employee`, `_inherit = ["hr.employee"]`).

## Field layout

The setting (`image_visibility`) and the real photo bytes (`image_private`) don't live
on the same model, for two independent reasons:

- **`image_visibility`** is only ever edited via "My Profile" (`res.users`), so it's a
  plain, real field there (`default='all'`). `hr.employee.image_visibility` is a
  derived, `store=True` mirror of `user_id.image_visibility` (falls back to `'all'`
  when the employee has no linked user) — nothing writes to it directly.
- **`image_private`** is the real photo storage on `hr.employee`, not `res.users`,
  because not every employee has a login (e.g. ASP/support staff) — an admin can still
  set their photo from the employee form. `res.users.image_private` is a thin
  `compute`+`inverse` mirror of `employee_id.image_private`, used only when editing
  from "My Profile".

`hr.employee.image_1920` (native, from `image.mixin`) becomes derived too: it equals
`image_private` when `image_visibility == 'all'`, and `False` otherwise. Every
`avatar_*`/`image_*` field and every `many2one_avatar(_employee)` widget across the app
reads from `image_1920`, so blanking it here is what makes the restriction apply
app-wide with no changes needed in attendance, grading, group or notice views — an
unauthorized viewer simply sees no photo there. The trade-off: those secondary views
don't restore the photo for an *authorized* viewer either (see below) — only the
"Teachers" kanban and the employee form do that swap, by design (kept intentionally
minimal; see "Known limitations").

```mermaid
flowchart LR
    subgraph "res.users (My Profile)"
        UV[image_visibility real field]
        UP[image_private compute+inverse]
    end
    subgraph "hr.employee"
        EV[image_visibility<br/>compute, store=True]
        EP[image_private<br/>real field]
        E1920[image_1920<br/>compute, store=True, inverse]
        PV[photo_visible_to_current_user<br/>compute, depends_context uid]
    end
    subgraph "core Odoo"
        AV[avatar_128 / avatar_1024 / ...]
        WIDGETS[many2one_avatar(_employee) widgets<br/>across attendance / grading / group / notice]
    end

    UV -- mirrors --> EV
    UP <-- sudo write / read --> EP
    EP --> E1920
    EV --> E1920
    E1920 --> AV --> WIDGETS
    EV --> PV
    EP -. shown instead of image_1920 when authorized .-> KanbanForm[Teachers kanban / employee form]
    PV -. gates the swap .-> KanbanForm
```

## Sync to the linked user's account avatar

`res.users._inverse_image_private` also writes the **real, unfiltered** photo to
`user.partner_id.image_1920` whenever the profile photo is updated — this keeps the
account avatar (top bar, Discuss, chatter, which read `res.partner.image_1920`, a
field completely separate from `hr.employee.image_1920`) equal to the real photo, the
same way it behaved before this feature. The visibility restriction is scoped to
`hr.employee.image_1920` only; it does not extend to Discuss/the top bar — out of
scope by design (see "Known limitations").

The write goes straight to `partner_id`, not through `res.users.image_1920`, to avoid
a second full pass through `res.users`' write MRO (gamification/mail/resource/base
overrides) within the same write — routing it through `res.users.image_1920` first
caused deep, nested `write()` chains within a single call in testing.

## Access control

| Viewer | `image_visibility = all` | `= teachers` | `= directive` |
|---|---|---|---|
| The employee themselves | sees it | sees it | sees it |
| `ems.group_academic_admin` | sees it | sees it | sees it |
| `ems.group_teacher` and above (tutor, dept. chief, HoS, director, admin) | sees it | sees it | only HoS and above |
| `ems.group_head_of_studies` and above (director, admin) | sees it | sees it | sees it |
| Anyone else (no `hr.employee` ACL, portal/family users) | no `hr.employee` read access at all — moot | — | — |

`photo_visible_to_current_user` (on `hr.employee`, `@api.depends_context('uid')`)
implements this table. It must **not** use `compute_sudo` — that would elevate
`self.env.user` to the superuser while computing, defeating the `has_group()` checks
for the actual viewer. `group_teacher`/`group_head_of_studies` already form a strict
implication chain (see `security/groups.xml`), so "teacher and above" /
"directive staff and above" need no new groups — a plain `has_group()` check on the
lowest tier in each chain covers it.

No new `ir.model.access.csv`/`ir.rule` entries were added: teachers keep their
existing read-only access to `hr.employee`, unchanged.

## Known limitations

- **View-level only.** The restriction hides the photo in the UI (kanban/form
  `invisible`, and everywhere else via the blanked `image_1920`); it does not block
  ORM/RPC-level reads of `image_private` for someone who already has model read access
  (teachers do, for all of `hr.employee`). This matches the existing rigor level used
  elsewhere in this module (e.g. the "special educational needs" field), not a new,
  weaker standard.
- **Only two views restore the real photo for an authorized viewer**: the "Teachers"
  kanban (`views/community/employee/kanban.xml`) and the employee form. Every other
  `many2one_avatar(_employee)` widget in the app (attendance sessions, corrections,
  justifications, templates, grading, groups, notices) shows no photo at all whenever
  `image_visibility != 'all'`, even for a viewer who would otherwise be authorized —
  intentional, since making every individual avatar in a `many2many_avatar_employee`
  badge list respect a per-teacher setting would need a custom OWL widget.
- **Discuss/top bar avatar is out of scope.** It's sourced from
  `res.partner.image_1920` (via `res.users`), a field this feature keeps in sync with
  the *real* photo, not the filtered one.
