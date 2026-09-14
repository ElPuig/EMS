# Technical Reference: `res.partner` (EMS contact) / `ems.student.benefit` / `ems.contact.relation.wizard`

## Overview

EMS does not define its own "contact" model: every student, family member, applicant, alumnus, withdrawal and external provider is a `res.partner` record, distinguished by `contact_type`. `models/contacts/contact.py` extends `res.partner` (`_inherit`) with the whole EMS-specific surface: lifecycle, academic placement, benefits/exemptions, authorizations, portal-access side effects and Google Workspace triggers. The same file also defines `ems.student.benefit`, a satellite one2many owned by a student.

**Module files:**
- `models/contacts/contact.py` — `ResPartner` (`_inherit = 'res.partner'`), `EmsStudentBenefit`
- `models/contacts/contact_relation.py` — `EmsContactRelationWizard`, `ResPartnerRelationAll` (`_inherit = 'res.partner.relation.all'`, from the `partner_multi_relation` OCA module)
- `models/contacts/google_workspace_integration.py` — `ResPartnerGoogleWorkspace`, the corporate-account side of the lifecycle (not covered here — see [Google Workspace student integration](google_workspace_student.md))

Related docs: [`ems.group`](group.md) (`main_group_id`), [Enrollment benefits](../enrollment/enrollment_benefits.md) (`ems.student.benefit` vs `sale.order`/invoice interaction), [Graduation & withdrawal wizards](exit_wizards.md) (deferred graduation mark vs immediate withdrawal cascade).

---

## Contact lifecycle

```mermaid
stateDiagram-v2
    [*] --> applicant: preinscription (GEDAC import)
    applicant --> student: admission (sale.order confirmed)
    student --> alumni: graduation (has_graduated=True)
    student --> withdrawal: withdrawal wizard, exit_kind='withdrawal'
    student --> expelled: withdrawal wizard, exit_kind='expulsion'
    alumni --> student: re-enrolment (_ems_convert_to_student)
    withdrawal --> student: re-enrolment (_ems_convert_to_student)
    expelled --> student: re-enrolment (_ems_convert_to_student)
    [*] --> family: parent_id of a student
    [*] --> provider: parent_id of a provider
```

`contact_type` also has two lifecycle-independent values not shown above: `family` and `provider`, auto-assigned in `create()` from the parent contact's own `contact_type` whenever `parent_id` is set (a child contact of a student becomes `family`; of a provider, `provider` — see `create()`'s inline note on why this can't rely on the value arriving from the popup form).

`has_graduated` is a **permanent** mark, set once by the graduation wizard and never cleared — it is what `_ems_convert_to_ex_student()` uses to decide `alumni` vs `withdrawal` on exit, even after a later re-enrolment. **`expelled` (added 2026-08-01) overrides this entirely**: `_ems_convert_to_ex_student(kind='expulsion')`, called only by the withdrawal wizard when the admin picks "Expulsion", always produces `contact_type = 'expelled'` regardless of `has_graduated` — see [Graduation & withdrawal wizards](exit_wizards.md#exit_kind--withdrawal-vs-expulsion-added-2026-08-01) for the full `exit_kind` design (and why it required a full audit of every place `contact_type` was filtered/branched on before adding the new value).

### `_sync_category()`

Every lifecycle transition re-tags `category_id` via a fixed map (`contact_type` → `res.partner.category` XML ID). `student`, `applicant`, `alumni`, `withdrawal` and `expelled` all additionally carry the shared `ems.partner_category_student` marker — this is what keeps family-relation domains (which pin the right-hand side to `partner_category_student`) valid across the whole lifecycle, not just while `contact_type == 'student'`. `_ems_resync_lifecycle_categories()` is a `@api.model` idempotent heal, invoked from a data `<function>` on upgrade, for partners created before this shared marker existed.

### `archived_reason_label` / `archived_reason_color`

Feed the shared `ems_archived_reason_ribbon` field widget (`static/src/js/backend/archived_reason_ribbon_field.js`, also used by `hr.employee` — see [`employee.md`](../employees/employee.md)) on both `views/community/contact/{form,kanban}.xml`: `_compute_archived_reason()` (`@api.depends('contact_type')`) returns `(_("Alumni"), '#4C7A5D')` / `(_("Withdrawal"), '#C97B3D')` / `(_("Expelled"), False)` for the three lifecycle-exit values, `(False, False)` for anything else (`student`/`family`/`provider`/`applicant`) — the native "Archived" ribbon (`base.view_partner_form`) is adjusted, not replaced, to only show for that last group (`invisible="active or archived_reason_label"`).

This **must be a real compute, not a plain `related=`**, unlike `hr.employee`'s equivalent (see [`employee.md`](../employees/employee.md)): `contact_type` has six possible values and only three are ribbon-worthy, so something has to decide which — a `related=` field always mirrors its target 1:1, with no way to express "but only for these values, otherwise nothing." `expelled`'s color is deliberately `False` (falls back to the widget's own default red, `#dc3545`) — same reasoning as leaving `hr.departure.reason`'s "Fired" record uncolored: severity that's already self-evident doesn't need a bespoke color to make the point.

---

## `ems.student.benefit`

| Field | Type | Notes |
|-------|------|-------|
| `student_id` | `Many2one → res.partner` | required, `ondelete='cascade'` |
| `benefit_type` | `Selection` (7 values) | required |
| `category` | `Selection` (`bonification`/`exemption`), computed, stored | `@api.depends('benefit_type')` — see mapping in `_compute_category` |
| `document` | `Binary` | required (supporting document) |
| `renewal_date` | `Date` | defaulted by `_onchange_benefit_type` (9 months for `scholarship`, 2 years otherwise) — a one-time UI convenience, not a stored compute, so it stays user-editable afterwards |

`res.partner.benefit_status` aggregates a student's `benefit_ids` into `none`/`bonification`/`exemption` (exemption wins if both are present). **The interaction between a benefit and an already-confirmed enrollment's invoice — draft orders react live, confirmed orders freeze — is documented in full in [Enrollment benefits](../enrollment/enrollment_benefits.md); `tests/test_enrollment_benefit.py` is the authoritative test coverage for that interaction**, not `tests/test_contact.py`.

---

## Key computed/derived fields on `res.partner`

| Field | Depends on | Notes |
|-------|-----------|-------|
| `is_adult` | `birth_date` | `>= 18` years via `relativedelta`; `False` if no birth date |
| `strike_count` | `strike_ids` | `len()` of `ems.strike` records |
| `transition_status` | `contact_type`, `exit_type`, next-course `sale_order_ids` | `enrolled` / `unplaced` / `graduated` / `former` / `missing`; searchable via `_search_transition_status` (evaluates in Python then converts to an `id in/not in` domain — not SQL-pushable). Full branch coverage in `tests/test_exit_management.py`. |
| `is_my_student` | (not stored) | `True` when the student belongs to one of the current user's own groups. Searchable via `_search_is_my_student`; backs the "My students" search filter that the Students action applies by default. See below. |
| `auth_image` / `auth_trip` / `auth_healt` / `auth_share` | current-course `sale_order_ids.ems_authorization_ids` | One `ems.authorization` per template per order; `True` only if `status == 'yes'` for that `auth_type` in the **current** course |
| `ems_authorization_ids` | (not stored) | Current-course authorizations across the student's `sale.order`s — feeds the badges above |
| `ems_current_enrollment_id` | (not stored) | The student's `sale.order` for the enrollment-default (or else current) course, in `draft/sent/sale` state |
| `benefit_status` | `benefit_ids`, `benefit_ids.category` | See `ems.student.benefit` above |
| `archived_reason_label` / `archived_reason_color` | `contact_type` | Feeds the `ems_archived_reason_ribbon` field widget (form + kanban) — see "Contact lifecycle" above |

> `ems_authorization_ids`/`ems_current_enrollment_id`/`auth_*` sit at the boundary with [`ems.authorization*`](../enrollment/authorization.md) (`models/enrollment/authorization.py`). `_compute_ems_authorization_ids` was missing its `@api.depends` entirely (a real bug — a non-stored compute field with no dependencies never gets invalidated by later writes in the same transaction) — found and fixed during that model group's own DTON pass, not this one; see that doc's "res.partner auth booleans" section.

### `is_my_student` / `_search_is_my_student` — the teacher's own students (issue #421)

The Students action (`ems.action_student_kanban`) used to open on every student in the centre.
It now applies a second default facet, `search_default_my_students`, so a teacher lands on the
students of the groups they actually work with.

**What counts as "one of my groups"** is the union of two sources, resolved by
`hr.employee._get_own_groups()` (`models/employees/employee.py`) so the compute and the search
cannot drift apart:

```mermaid
flowchart LR
    U["res.users<br/>(current user)"] --> E["hr.employee"]
    E -->|"teaching_ids.group_id"| G["ems.group"]
    E -->|"tutorship_ids"| G
    G -->|"main_student_ids<br/>(main_group_id)"| S["res.partner<br/>(student)"]
    G -->|"ems.enrollment<br/>(group + subject)"| S
```

- `teaching_ids.group_id` — every group the employee teaches, main **or** reinforcement.
  A tutoring assignment is normally already in here, as an ordinary `ems.teaching` row on the
  group's tutorship subject (`ems.subject.is_tutorship`).
- `tutorship_ids` — the already-existing `One2many` inverse of `ems.group.tutor_id`. Needed on
  top of the above because a tutor set **by hand** on the group form has no matching
  `ems.teaching` row. Not hypothetical: 6 groups were in exactly that state when this was
  written, 2 of them with students.

**The two student-membership branches are deliberately of different width.**

`main_group_id` covers the groups themselves: everyone whose main group is one of mine,
whatever they happen to be enrolled in there. It is a plain many2one, pushed straight into the
domain.

`ems.enrollment` covers the students who reach one of my groups **without** it being their main
one — a **reinforcement** group (nobody's main group is a reinforcement one, and its students
are attached through `ems.enrollment` only: 17 students in this centre's only such group at the
time of writing, 0 via `main_group_id`) and a **repeater** carrying a failed subject down into a
lower course's group. This branch matches the exact `(group_id, subject_id)` pairs the employee
teaches — the ternary `ems.enrollment` mirrors from `ems.teaching` — and resolves the student
ids in Python.

> Matching that second branch on the **group alone** was the shipped behaviour for about an
> hour, and it was too wide: a teacher of SMX1A/SMX1B was shown 19 students of SMX2A/SMX2B whose
> only link to them was some *other* teacher's subject taught in SMX1A/SMX1B. Only 4 of those 19
> survive the pair match, and they are exactly the repeaters sitting in one of this teacher's
> own classes. Nobody is lost to the tightening: an SMX1A student enrolled in none of that
> teacher's subjects is still matched by `main_group_id`.

The pairs come from `teaching_ids` alone, not from `_get_own_groups()`: a group that is only in
scope because the employee **tutors** it contributes no subject of theirs, and its tutorands are
already covered by the `main_group_id` branch.

Reading enrolments needs `active_test=False`, since the action itself runs with
`active_test: False` so archived alumni/withdrawals stay reachable once the `students_only`
facet is removed.

**A user with no groups at all is not filtered.** `_search_is_my_student` returns an **empty
domain** (not `[('id', 'in', [])]`) when the employee teaches and tutors nothing, so
administration and secretariat keep seeing every student even though the default facet is
applied to them too. This is deliberate: an `ir.actions.act_window`'s `context` is a string
evaluated **client-side** and has no ORM access, so it cannot decide per user whether to add
`search_default_my_students`. Making the *search* inert for those users is what keeps the action
a plain `act_window` — the alternative (an `ir.actions.server` building the context in Python)
would have had to be threaded through both menu items and would diverge from the
`/odoo/action-ems.action_student_kanban` URL that nine browser tours navigate to.

Accepted trade-off: those users do see an inert "My students" facet in the search bar. Head of
studies and Orientation get no exemption either — if they also teach, they open on their own
groups and clear the facet when they need the whole cohort.

**The filter must sit in its own group in the search view** (wrapped in `<separator/>`).
Adjacent `<filter>` elements are ORed together, so placing it next to `students_only` /
`former_students` would have widened the result set instead of narrowing it.

Rejected alternative: filtering **only** through `ems.enrollment`. Enrolment coverage is uneven
— FP has rows, ESO/BTX/PFI largely do not — so ESO/BTX teachers would have seen nothing. As the
*second* branch of an `OR` it is safe: it only ever adds students on top of the `main_group_id`
one, never takes any away.

### `_compute_group_data(values)`

Not a `@api.depends` compute — a **vals-mutation helper** called from both `create()` and `write()` before the actual `super()` call: if `main_group_id` is present in the incoming vals, it derives and injects `level_id`/`study_id` from that group; if only `study_id` is present, it derives `level_id`. Keeps the three fields from ever disagreeing regardless of which one the caller set. The client-side `_onchange_level_id`/`_onchange_study_id` mirror this in the form (clearing the now-stale child field the moment a parent field changes) but are pure UI convenience — `_compute_group_data` is what makes the guarantee hold for any programmatic write (RPC, import, wizard).

```mermaid
flowchart LR
    A["create()/write() vals"] --> B{"main_group_id in vals?"}
    B -- yes --> C["vals.level_id = group.level_id\nvals.study_id = group.study_id"]
    B -- no --> D{"study_id in vals?"}
    D -- yes --> E["vals.level_id = study.level_id"]
```

### `_migrate_enrollments_on_group_change(old_main_groups)` — a tutor moving a student between groups (issue #395)

A tutor's own tutorands' `main_group_id` field is no longer locked by `is_tutor_readonly` on the form (see "Access Control" below) — a tutor can move a student from one group to another (e.g. group A to group B, within the same study/level; `study_id` stays tutor-locked so the study itself can never change this way). `write()` reacts to that change: **before** calling `super().write()` it captures `{partner.id: partner.main_group_id}` for every partner about to have `main_group_id` written (skipped entirely if `env.su`, see below); **after** the write, `_migrate_enrollments_on_group_change()` compares each partner's captured old value against its new one and, for every real A→B change, calls [`ems.enrollment._ems_move_group(partner, old_group, new_group)`](enrollment.md#_ems_move_groupstudent-old_group-new_group--following-a-students-group-change-issue-395) — which repoints that student's subject enrollments (and, through its own reused `create()`/`unlink()`, their attendance-schedule rosters and open grade-session lines) from the old group to the new one. A partner with no previous group (a first placement) or whose group ends up unchanged is skipped — see `_ems_refresh_enrollments_from_template()` below for what happens instead when `study_id` is also being set on that same first placement.

**`env.su` is what keeps this from firing on `sale.order._ems_apply_destination_placement()`** (course transition / enrollment-placement confirmation), which also writes `main_group_id` but deliberately does *not* want the outgoing group's enrollments touched (they are the ending year's history) — that flow always writes via `sudo()`. See `_ems_move_group`'s own doc for the full reasoning and the mirrored `env.su` check `ems.enrollment.default_get()` already uses for the same purpose.

Applies to **any** interactive change of `main_group_id`, not only when a tutor does it — admin/secretary editing the same field, or a bulk student CSV re-import updating an existing student's group, are the same real-world event ("this student's group changed") and get the same cascade; this is what closes a pre-existing gap where changing `main_group_id` never used to move a student's subject enrollments at all, regardless of who changed it.

**`main_group_pending_change` — pre-save warning (issue #395).** A `compute='_compute_main_group_pending_change'`, `@api.depends('main_group_id')` boolean, `store=False`, feeding a yellow `alert alert-warning` banner at the top of the Studies tab's "Enrollment Data" section (`views/community/contact/form.xml`). Compares `partner.main_group_id` (the live, possibly-unsaved on-screen value) against `partner._origin.main_group_id` (the actually-persisted one): `_origin` is what keeps this reactive to an in-progress form edit *before* Save, rather than only reflecting the outcome after the fact like `_migrate_enrollments_on_group_change` itself does — the same distinction `docs/en/developers/enrollment/enrollment.md`'s `NewId(origin=...)` note describes for onchange-time virtual records. `False` whenever there is no real old group (first placement) or the edited value matches the persisted one (including "changed then changed back" within the same edit session). Covered by `tests/test_contact.py`'s `test_main_group_pending_change_*` (built via `self.env['res.partner'].new({}, origin=student)`, the lower-level equivalent of editing the field in a `Form()`/browser without saving) and exercised visually by `tests/test_contact_group_change_tour.py`.

### `_ems_refresh_enrollments_from_template()` — regenerating subject enrollments on a study change (also fires at creation time)

Secretary report: changing a student's `study_id` left `ems.enrollment` untouched — the student kept the old study's subject rows (or none at all) instead of picking up the new study's curriculum. `write()` reacts to an interactive `study_id` change the same way it already reacts to a `main_group_id` change above, but resolves the destination itself instead of only migrating what already exists:

```mermaid
flowchart TD
    A["write(values)"] --> B{"'study_id' in values,\nnot env.su,\nstudy_id actually changes,\neffective contact_type == 'student'?"}
    B -- no --> Z["unchanged: derive level_id only\n(_compute_group_data)"]
    B -- yes --> C{"main_group_id given\nAND partner already\nhad a group?"}
    C -- yes --> Y["excluded here - handled by\n_migrate_enrollments_on_group_change\ninstead (repoints OLD enrollments)"]
    C -- no --> D{"main_group_id\ngiven explicitly?"}
    D -- yes --> F
    D -- no --> E["values['main_group_id'] =\n_ems_auto_group_for_study(study_id).id"]
    E --> F["super().write(values)"]
    F --> G["candidate._ems_refresh_enrollments_from_template()"]
```

- **Group resolution:** if the caller didn't give `main_group_id` explicitly, the first `ems.group` alphabetically for the new study is auto-picked (`_ems_auto_group_for_study(study_id)`, shared with `create()` below) — no course filter needed, since a main group's own `name` is built as `study.acronym + course + acronym` (see [`group.md`](group.md)), so ordering by `name` within the study already lands on its lowest course first. Resolved explicitly either way (a found group, or `False`) rather than left as whatever it already was: a direct `write()` bypassing the form's own `_onchange_study_id` (client-side only) would otherwise leave `main_group_id` stuck on a group belonging to the *old* study — the same "incongruence between main_group, level and studies" `_compute_group_data` already guards against for every other path. If the caller *did* give `main_group_id` explicitly, it's used as-is — see the next point for when that still triggers a template refresh.
- **Template lookup:** [`sale.order.template._ems_find_for(study, course)`](../enrollment/enrollment_template.md#_ems_find_forstudy-course) — an exact `(ems_study_id, study_year)` match, unlike `enrollment_proposal_wizard._ems_templates_for()`'s multi-student/course-floor candidate list for a human to pick from in a dropdown. Nothing enforces a single template per study+course; the first one found is used if more than one matches.
- **Subject/group resolution mirrors `sale.order._ems_apply_destination_placement()`** ([`../enrollment/enrollment.md`](../enrollment/enrollment.md)): each template line's product is resolved back to its `ems.subject`, and `ems.study._ems_subject_course()` + `ems.group._ems_equivalent_for_course()` place a subject taught in a different course into that course's equivalent group instead of the main one. Idempotent — an existing `(student, group, subject)` triple already matching the template is left untouched.
- **Stale enrollments:** any of the student's existing rows not part of the new template's set are removed, *unless* the student already has scored grades on that row (`ems.grade_session._ems_has_scored_grades`), in which case it is left alone and a chatter note lists which subjects were kept as-is.
- **Scoped narrowly, on purpose:**
  - *An explicit `main_group_id` in the same write is excluded only when the partner already had a group before this write* — a genuine group change (not a first placement). That case goes through the pre-existing `_migrate_enrollments_on_group_change` cascade above instead, which repoints the *old* (same-study) enrollments into the new group; mixing that with a template-driven refresh for a different study would create rows for subjects belonging to neither curriculum. **A partner with no previous group has nothing to migrate FROM, so the template refresh still runs, using the explicitly given group instead of auto-picking one.** Bug fixed 2026-09-13 (issue #455 follow-up): filling **Studies** then **Main Group** before the very first save is the normal way to place a new/unplaced student — the original version of this feature treated *any* explicit `main_group_id` as reason to skip the refresh, which silently produced zero enrollments for exactly that everyday case.
  - *`not env.su`* — excludes system flows resolving their own group/subjects on the student's behalf, chiefly `_ems_apply_destination_placement()` (which always writes `main_group_id` and `study_id` together anyway — but see above, this alone is no longer sufficient to exclude it; it stays excluded because it always runs under `sudo()`). Same signal `_migrate_enrollments_on_group_change`/`ems.enrollment.default_get()` already use.
  - *Effective `contact_type == 'student'`* — excludes applicants (`applicant_import_wizard`, the course transition wizard's pending graduates), which also write `study_id` without a group on purpose: they are not placed yet, so there is nothing to enroll them into.

Covered by `tests/test_contact.py::TestContactStudyChange` (auto-pick, template-driven creation, stale-row removal with/without scored grades, the empty-destination-study case, the existing-placement group-change exclusion, the first-placement explicit-group case, the `env.su` exclusion, the non-student exclusion, and the translated chatter note).

**Same mechanism also runs from `create()` (bug fix: a brand-new student created with `study_id` already set never got placed or enrolled at all).** `create()` never has a "previous study" *or* a "previous group" to compare against — every `study_id` given at create time is by definition a first placement — so its own gate is a per-entry version of `write()`'s, without the "study actually changing" condition, and **without the group-change exclusion either**: there is never a previous group for a brand-new record to migrate enrollments away from, so an explicit `main_group_id` given alongside `study_id` at create time never skips the refresh, unlike a `write()` on an already-placed student.

```mermaid
flowchart TD
    A["create(values) - one dict per new record"] --> B{"'study_id' in entry,\nnot env.su,\neffective contact_type == 'student'?"}
    B -- no --> Z["entry unchanged\n(_compute_group_data still runs)"]
    B -- yes --> C{"main_group_id\ngiven explicitly?"}
    C -- yes --> E
    C -- no --> D["entry['main_group_id'] =\n_ems_auto_group_for_study(study_id).id"]
    D --> E["_compute_group_data(entry)"]
    E --> F["super().create(values)"]
    F --> G["zip(contact, flags) ->\nstudy_refresh_candidates"]
    G --> H["_ems_refresh_enrollments_from_template()"]
```

The group lookup itself (`_ems_auto_group_for_study(study_id)`) is a small shared helper used by both `create()` and `write()` — see its own docstring next to `_compute_group_data` below.

One thing this reuses **unchanged**, worth calling out explicitly since it's pre-existing behaviour rather than something introduced for `create()`: **a later-confirmed `sale.order` with different subjects than the template guessed never removes the stale template-provisioned rows** (`_ems_apply_destination_placement()` in `../enrollment/enrollment.md` only adds from the order's own lines, it has no cleanup step). This divergence risk already existed for the `write()` path; reaching it from `create()` too does not make it worse, just reachable from one more entry point.

Covered by `tests/test_contact.py::TestContactCreateWithStudy` (auto-pick, template-driven creation, the explicit-group-given parity no-op, the applicant/bulk-import exclusions, the `env.su` exclusion, and the no-group/no-template no-op cases).

**`tutor_id` is now `readonly=True` at the field level (bug found 2026-09-06, same testing pass).** `related="main_group_id.tutor_id"` had no explicit `readonly`; per Odoo's `Field.setup_related()`, a related field only skips auto-generating a write-through inverse when *it or its target* is already readonly — neither was true here, so Odoo silently wired one up. Without the fix, editing "Tutor" from a **student's own form** would not merely have updated a display value for that one student: it would have reassigned `main_group_id.tutor_id` on the underlying `ems.group` record itself, changing the tutor for *every* student in that group. `readonly=True` removes the inverse entirely (a `write()` including `tutor_id` is now silently ignored — Odoo does not raise for a compute field with no inverse, it just cannot persist the value; only the calling recordset's own in-memory cache reflects it until next recompute). The view's own conditional `readonly="is_tutor_readonly"` on this field was dropped as redundant. Covered by `tests/test_contact.py::test_tutor_id_write_does_not_reassign_the_group_tutor`.

### `_check_nuss` (`@api.constrains('nuss')`)

The Spanish Social Security number (NUSS) must be exactly 12 numeric digits (`re.fullmatch(r'\d{12}', nuss)`) when set.

### Student ID (IDALU): unique, and required for new students (issue #460)

`student_id` is what identifies a student-lifecycle contact (`STUDENT_LIFECYCLE_TYPES` in
`contact.py`: student, applicant, alumni, withdrawal, expelled), and the key the Esfer@
(`student_import_wizard`) and GEDAC (`applicant_import_wizard`) importers match rows on. While it
was optional, returning former students got registered again as brand-new contacts, producing
duplicates that had to be merged by hand.

```mermaid
flowchart TD
    A["create() / write()"] --> N["_ems_normalize_student_id: strip, blank -> False"]
    N --> U{"IDALU given and held by<br/>another contact?<br/>(archived included)"}
    U -- yes --> E1["ValidationError naming the holder"]
    U -- no --> R{"Result has no IDALU and<br/>is a student-lifecycle type?"}
    R -- no --> OK["saved"]
    R -- "create()" --> E2["ValidationError: IDALU required"]
    R -- "write(): had an IDALU" --> E3["ValidationError: cannot be removed"]
    R -- "write(): was not a student type" --> E2
    R -- "write(): student without IDALU from before the rule" --> OK
```

- **Unique, across every contact, archived ones included.** `_ems_check_student_id_available()`
  runs from `create()`/`write()` *before* the INSERT/UPDATE (as `sudo()`, `active_test=False`) and
  raises a message naming the contact that already holds it, so a returning former student is
  reopened instead of duplicated. `student_id_unique` (`UNIQUE(student_id)`) is the database
  backstop; NULLs never collide, so families, providers and legacy students without an IDALU are
  unaffected. It is not an `@api.constrains` because that runs after the INSERT, when the database
  constraint has already refused the row with a message that cannot name the holder.
- **Required, going forward only.** Production still had students without an IDALU when the rule
  shipped, so it is enforced on the operations that would create a new one, not retroactively:

  | Operation | Result without an IDALU |
  |---|---|
  | `create()` with a student-lifecycle type (explicit, or `default_contact_type` from context) | refused |
  | `write()` turning a non-student contact (family, provider, none) into a student-lifecycle type | refused |
  | `write()` clearing the IDALU of a student-lifecycle contact | refused |
  | any other `write()` on a student-lifecycle contact created without one (course transition, withdrawal, graduation...) | allowed |

  A contact created under a student (the "Contacts & Addresses" tab) keeps the Students action's
  `default_contact_type='student'` in context, but `create()` turns it into `family` first, so it
  needs no IDALU.
- **Normalization:** `_ems_normalize_student_id()` strips the value and stores a blank one as
  `False`, in both `create()` and `write()`.
- **View:** the "Student data" page marks it `required="not id and contact_type == 'student'"`
  (new records only, matching the server rule); the "Applicant data" page already required it.
- **`copy=False`**, so duplicating a contact never duplicates its IDALU.
- **Merging a duplicate** (`models/contacts/partner_merge_wizard.py`): the base
  `base.partner.merge.automatic.wizard._update_values()` writes the source's IDALU onto the
  destination while the source still holds it, which `student_id_unique` refuses. The override
  releases the sources' IDALU with plain SQL first (they are deleted right after; an ORM write
  would be refused as a removal) and then writes it onto the destination if it has none.

Covered by `tests/test_contact.py::TestContactStudentId`. Test fixtures get a unique IDALU from
`tests/common.py::next_student_id()` (`TEST000001`...), which can never match a real, digits-only
IDALU in the development database the test shards are cloned from.

---

## Portal email change

`write()` detects, **before** calling `super()`, any student/family partner whose `email` is about to change while holding active portal access (`_has_active_portal_user`), then **after** the write calls `_apply_portal_email_change()` for each: revokes portal access at the old email and re-grants it at the new one via `ems.portal.access.wizard` (sudo — tutors lack `res.users` rights), and posts a portal-visible message on the related student(s) explaining what happened. `_onchange_email_portal_warning` gives the same heads-up client-side, before Save, via a non-blocking `warning`.

---

## `toggle_active()` — archiving is the withdrawal flow

Archiving one or more **active students** does not flip `active` directly: it opens the withdrawal wizard instead (mirroring `hr.employee`'s departure-reason flow), because withdrawal changes more state atomically (`contact_type`, operational-record cleanup, portal) than a bare `active` flip — none of it may run before a reason is captured, and nothing should happen if the wizard is cancelled. Non-student contacts in the same recordset are archived directly; reactivating never opens the wizard. See [Graduation & withdrawal wizards](exit_wizards.md) for the full withdrawal cascade this triggers. Full coverage (including the generic Archive action from list/form, mixed recordsets, and the "still shows under Former students" edge case the tour catches) lives in `tests/test_exit_management.py` and `tests/test_withdrawal_tour.py`.

---

## `ems.contact.relation.wizard` — adding a family contact

`res.partner.relation.all` (from the third-party `partner_multi_relation` module) is extended (`ResPartnerRelationAll`) with read-only related columns (`other_partner_phone/mobile/email`, relation labels) purely for display in the student/family form's relation list — no new logic.

`ems.contact.relation.wizard` (`action_open_relation_wizard`, opened from the student's "Contacts & Addresses" tab) either links an **existing** `family`-typed partner or creates a **new** one, then always creates one `res.partner.relation` between it and the student:

```mermaid
flowchart TD
    A["action_save()"] --> B{"type_selection_id set?"}
    B -- no --> X1["ValidationError"]
    B -- yes --> C{"partner_id (existing) set?"}
    C -- yes --> F["res.partner.relation.create(left=partner_id, right=student_id)"]
    C -- no --> D{"firstname or lastname?"}
    D -- no --> X2["ValidationError"]
    D -- yes --> E{"document_id/passport_id AND\nphone/mobile/email present?"}
    E -- no --> X3["ValidationError"]
    E -- yes --> G["res.partner.create(contact_type='family', ...)"] --> F
```

The three roles `action_save()`'s own guard clears (`_get_read_only_user()`: academic admin, secretary, or a tutor of that student) must each hold create rights on the wizard model too — the guard runs *inside* the wizard, so a role missing from `ir.model.access.csv` fails earlier, on opening it. That mismatch was issue #423: secretary cleared the guard and saw the "Add contact" button, but the wizard granted access to academic admin and teacher only, so only the one secretary who also happens to be a teacher could use it.

`_onchange_student_id` pre-fills the address fields from the student (client-side convenience only — `action_open_relation_wizard` already seeds them server-side when the wizard is created, since it's opened with `target: 'new'` on an already-saved record, not a blank `new()` form).

---

## Google Workspace

`models/contacts/google_workspace_integration.py` (`ResPartnerGoogleWorkspace`) manages the student corporate-account lifecycle (creation eligibility, OU relocation on adult/minor transition, suspend/reactivate) via `with_delay()`-queued jobs, invoked from `ResPartner.create()`/`write()`/`_ems_convert_to_ex_student()`. Fully DTON'd separately — see [Google Workspace student integration](google_workspace_student.md) for the full technical reference, and [Google Workspace staff](../employees/google_workspace_staff.md) for the equivalent pattern on the employee side.

---

## Access Control

### `ir.model.access.csv`

| Model | Role | Create | Read | Write | Delete |
|-------|------|:------:|:----:|:-----:|:------:|
| `res.partner` | Academic admin | ✓ | ✓ | ✓ | ✓ |
| `res.partner` | Secretary | ✓ | ✓ | ✓ | ✓ |
| `res.partner` | Teacher | — | ✓ | — | — |
| `ems.student.benefit` | Academic admin | ✓ | ✓ | ✓ | ✓ |
| `ems.student.benefit` | Secretary | ✓ | ✓ | ✓ | ✓ |
| `ems.student.benefit` | Teacher | ✓ | — | — | — |
| `ems.contact.relation.wizard` | Academic admin | ✓ | ✓ | ✓ | ✓ |
| `ems.contact.relation.wizard` | Secretary | ✓ | ✓ | ✓ | ✓ |
| `ems.contact.relation.wizard` | Teacher | ✓ | ✓ | ✓ | ✓ |

### `security/rules/contacts.xml` (record rules, `res.partner`)

| Rule | Groups | Domain | Write |
|------|--------|--------|:-----:|
| `rule_contact_admin` | Academic admin | `[]` (unrestricted) | ✓ |
| `rule_contact_secretary` | Secretary | `[]` (unrestricted) | ✓ |
| `rule_contact_teacher` | Teacher | `[]` (read-only, no write/create/unlink) | — |
| `rule_contact_tutor` | Teacher (tutor subset) | Own tutorands **or** their family (`relation_all_ids.other_partner_id.tutor_id`) | ✓ (no create/unlink) |

The **field-level** editing surface for tutors is narrower than the record rule allows: `read_only_user`/`is_tutor_readonly` (computed on load, not stored) drive `readonly=`/`invisible=` attributes across the view, so a tutor's ORM write access to their own tutorands is real but the form only exposes a subset of fields as actually editable (`_get_read_only_user`/`_get_is_tutor_readonly`, `_user_is_tutor_of_record`). **`main_group_id` is the one exception (issue #395):** every other tutor-locked field on the "Studies"/"Secretary" pages stays behind `is_tutor_readonly`, but `main_group_id` deliberately excludes it — a tutor can move their own tutorand to another group of the same study (`study_id`'s own domain still scopes the choice, and `study_id` itself stays locked) — see `_migrate_enrollments_on_group_change` above for what happens to the student's subject enrollments when they do.

---

## Views

| View | File | Notes |
|------|------|-------|
| List | `views/community/contact/list.xml` | `js_class="student_list"`; columns conditional on `default_contact_type` context |
| Kanban | `views/community/contact/kanban.xml` | Default view for the Students menu |
| Form | `views/community/contact/form.xml` | Inherits `base.view_partner_form`; `js_class="studentpopup_expand_button"`; conditional pages per `contact_type` (`student`, `applicant`, `former_student`, `academic_history`, base `contact_addresses`) |
| Search | `views/community/contact/search.xml` | `view_student_search` carries the `students_only` default facet and the `my_students` one (issue #421, see above) |
| Relation wizard | `views/community/contact/relation_wizard.xml` | `action_contact_relation_wizard` |
| Menu | `views/community/contact/menu.xml` + `views/community/menu.xml` | `action_student_kanban` (top-level "Educational Community" entry), `action_family_list`, `action_provider_kanban` |

Other student-related popups — [portal access](portal_access_wizard.md), [documents](student_document.md), [graduation/withdrawal](exit_wizards.md) — live in the same `views/community/contact/` folder but are documented separately. The import wizards (`student_import`, `student_update`, `applicant_import`) are not yet DTON'd (see the roadmap). The Form's own `schedule` page (a student's read-only weekly timetable) is likewise documented separately — see [Student schedule](student_schedule.md).

### List view columns (2026-09-03)

`views/community/contact/list.xml`'s student-only columns (`document_id`, `birth_date`, `is_adult`, `nuss`, `citizenship_id`, `street`, `zip`, `city`, `main_group_id`, `tutor_id`, `special_needs`, `auth_image`/`auth_trip`/`auth_healt`/`auth_share`) were chosen to mirror, as closely as EMS's data model allows, the centre's own official Esfera student data export ("DADES ALUMNAT" CSV) — the fields that don't have a stored equivalent (a split second surname, sex, age as a column) were deliberately left out rather than added as new fields. `exit_type`/`exit_course_id` stay fully removed for students (`column_invisible="1"`) since they aren't part of that reference sheet. All optional columns default to `optional="show"` (visible unless a user hides them via the column selector) except `state_id`/`vat`/`invoice_sending_method`/`invoice_edi_format`/`category_id`, forced `column_invisible="True"` — not useful on a student record.

**Gotcha: `<field name="priority">99</field>` is load-bearing.** `invoice_sending_method`/`invoice_edi_format` aren't part of `base.view_partner_tree` itself — a separate `account` module view (`account.res_partner_view_tree`) adds them via its own inherit of the same parent. Odoo composes every view inheriting the same parent in priority order (default 16), applying each one's xpath modifications to the accumulating arch in turn; at default priority, this view's own xpaths run *before* `account`'s addition lands, so `//field[@name='invoice_sending_method']` can't be located and the whole view fails to load (`ParseError`). Raising this view's `priority` to 99 forces it to compose after `account`'s (and any other default-priority) inherit — remove it and the view breaks again the moment any xpath here targets a field added by another module's same-parent inherit, not one from `base.view_partner_tree` directly.

Deferred to a future iteration: **family contact** (phone/email) has no ready field on `res.partner` — the data lives on the related `family`-typed partner(s) via `relation_all_ids`, and a student can have more than one. Adding it as a list column would need a new non-stored compute field aggregating across them (see "Key computed/derived fields" above for the `auth_*`/`is_adult` pattern to follow) — not done here.
