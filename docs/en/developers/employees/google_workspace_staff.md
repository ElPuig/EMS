# Google Workspace staff integration & EMS user auto-creation

Automates the two accounts every staff member (teacher / ASP) needs:

1. **Corporate Google Workspace account** (issue 304) — created through the Admin SDK
   Directory API; the resulting address is stored in `work_email`.
2. **EMS user** (`res.users`, issue 342) — created right after the Google account, with
   login = corporate email and Google OAuth **pre-linked** (`oauth_uid` = the numeric
   Google user id returned by the Directory API), so staff sign in with the
   *Sign in with Google* button without ever receiving a password email.

Both live in `models/employees/google_workspace_integration.py`
(`HrEmployeeGoogleWorkspace`, `_inherit = 'hr.employee'`), with shared helpers in
[`google.workspace.mixin`](../shared/google_workspace_mixin.md).

## Flow

```mermaid
sequenceDiagram
    autonumber
    participant HR as HR user / Admin
    participant EMP as hr.employee
    participant Q as queue_job
    participant G as Google Directory API
    participant U as res.users

    HR->>EMP: create() / write() (teacher or ASP)
    EMP->>EMP: _gw_enqueue_if_ready()
    alt missing name / personal email
        EMP-->>HR: one-off chatter note (missing data)
    else ready
        EMP->>Q: with_delay(action_create_google_account)
        Q->>G: users().insert(primaryEmail=candidate)
        G-->>Q: 200 {id: <google_id>} (409 → next candidate)
        Q->>EMP: work_email = chosen address
        Q->>U: _ems_create_user(google_id)
        Note over U: login/email = work_email<br/>groups: internal (+ Teacher if teacher)<br/>oauth_uid = google_id, provider = Google
        U-->>EMP: user_id linked + _sync_security_groups()
        Q->>EMP: _gw_deliver_credentials() (PDF + welcome mail)
    end
```

### `_ems_create_user(google_id=False)`

Idempotent; everything runs `sudo()` (callers are queue jobs or buttons limited to
`ems.group_academic_admin` / `hr.group_hr_user`). In order:

1. Guard: `employee_type in ('teacher', 'asp')` and `work_email` ends with the
   corporate domain — otherwise no-op.
2. Employee already has `user_id` → only backfill the OAuth fields if empty
   (and the `(provider, oauth_uid)` pair is free).
3. A `res.users` with `login = work_email` exists (archived included) and is not
   linked to another employee → re-link: unarchive, realign `login`/`email` to the
   corporate address, add missing groups, backfill OAuth. Linked to another
   employee → skip with a chatter note.
4. Otherwise create the user: `login`/`email` = corporate address (load-bearing —
   see *pitfalls*), `firstname`/`lastname` from `_gw_split_name()` (res.users
   inherits res.partner, which uses OCA `partner_firstname`), `mobile`, `tz`,
   explicit `company_id`/`company_ids` and groups, all under
   `no_reset_password=True`.
5. `_ems_link_google_signin(user, google_id)` sets `oauth_uid` + `oauth_provider_id`
   when the id is known and not taken by another user (auth_oauth unique constraint).
6. Link `employee.user_id`, call `_sync_security_groups()` so role/job-mapped
   groups apply immediately (the `write()` trigger only fires on
   `role_ids`/`job_id`/`tutorship_ids`), and post a chatter summary
   (created/re-linked + whether Google sign-in was pre-linked).

Call sites inside `action_create_google_account()`:

- **Success path** — right after `work_email` is written, before
  `_gw_deliver_credentials()`, with the `id` from the `users().insert` response.
- **Adopt path** (employee already had a corporate `work_email`, e.g. manual email or
  data migrated from before the integration) — delegates to `action_create_ems_user()`
  (below) instead of calling `_ems_create_user` inline, so the same code runs whether
  it is reached automatically or by the user pressing the dedicated button.

### `action_create_ems_user()`

Public action (no Google API call): `_ems_create_user(google_id=self._gw_google_user_id())`,
guarded by the same `employee_type`/`work_email` checks. This is the header button shown
in the `pending_user` state (below) — a corporate account already exists but no `res.users`
is linked yet — and it is what `action_create_google_account()`'s adopt path now calls
internally, so there is a single implementation either way.

In **dry-run** (`company.google_ws_dry_run`) no API call is made, so there is no
Google id: the EMS user is created without OAuth fields.

## Lifecycle

| Employee event | Google account | EMS user (`res.users`) |
|---|---|---|
| Created / completed (ready) | created (queued) | created + OAuth pre-linked |
| Archived (`active = False`) | suspended, moved to suspended OU (queued) | archived immediately (`_ems_sync_user_active`) |
| Unarchived | reactivated (queued) | unarchived |
| Deleted (`unlink`) | suspended synchronously | archived |

The user archiving is deliberately **synchronous and independent** of
`google_ws_enabled` and of the job queue: a former employee must lose Odoo access
immediately even if the Google integration is disabled or the queue is down.
`_ems_sync_user_active` skips `self.env.user` and the superuser.

## Header button state (`google_ws_state`)

The employee form (`views/community/employee/form.xml`) shows at most **one** of four
mutually-exclusive header buttons, driven entirely by one computed, stored `Selection`
field — `google_ws_state` — instead of each button evaluating its own combination of
`work_email`/`user_id`/`google_ws_suspended`/`google_ws_manual_email`. This replaced an
earlier version where two independently-computed `invisible` expressions could disagree
and show two buttons at once for a teacher whose account was adopted from
pre-integration/migrated data (`work_email` set, `user_id` not yet linked) — the bug that
motivated the consolidation.

```mermaid
stateDiagram-v2
    [*] --> none: not teacher/asp
    none --> manual_pending: google_ws_manual_email ticked
    none --> pending_user: work_email set, no user_id\n(adopt / migration gap)
    manual_pending --> pending_user: work_email filled in manually
    none --> active: action_create_google_account()\n(work_email + user_id both set)
    pending_user --> active: action_create_ems_user()
    active --> suspended: action_suspend_google_account()
    suspended --> active: action_reactivate_google_account()
```

| `google_ws_state` | Header button shown | Meaning |
|---|---|---|
| `none` | Create Google account | No corporate email yet |
| `manual_pending` | *(none)* | `google_ws_manual_email` ticked, waiting for the email to be typed in |
| `pending_user` | Create EMS User | Corporate email exists, no `res.users` linked (adopt / migration gap) |
| `active` | Suspend Google account | Fully set up |
| `suspended` | Reactivate Google account | `google_ws_suspended = True` |

`res.partner` (students) has the analogous `google_ws_state` in
`models/contacts/google_workspace_integration.py` — see
[Google Workspace student integration](../contacts/google_workspace_student.md) — with
only three values (`none` / `active` / `suspended` — students never get a `pending_user`
state since account creation there never involves a separate `res.users`).

A one-off migration (`migrations/18.0.0.22.0/post-migrate.py`,
`_backfill_google_ws_suspended`) marks `google_ws_suspended = True` for employees/students
that were already archived/withdrawn before the field existed (added in 18.0.0.19.0 /
18.0.0.19.2), so they land in `suspended` instead of the wrong `active` state.

## Access control

| Action | Who |
|---|---|
| Create employee / trigger account creation (buttons, incl. `action_create_ems_user`) | `ems.group_academic_admin`, `hr.group_hr_user` |
| Auto-created user groups (teacher) | `base.group_user` + `ems.group_teacher` |
| Auto-created user groups (ASP) | `base.group_user` only (role/job sync adds the rest) |
| res.users creation itself | `sudo()` inside the flow |

`ems.group_teacher` does **not** imply `base.group_user`, so the internal-user group
is granted explicitly.

## Required fields

| Step | Required data |
|---|---|
| Plain employee creation | `name` (plus `private_email` at view level for **new** teacher/ASP records) |
| Google account creation | `name`, `private_email` (recovery + credentials email); phone/NIF optional |
| EMS user creation | corporate `work_email` (produced by the previous step) |

## Interplay with pending-identification placeholders

A teacher created by the working-schedule importer from a not-yet-staffed post's code
(`hr.employee.schedule_import_code` set, `pending_identification` computed `True` — see
`docs/en/developers/employees/working_schedule.md`'s "Pending-identification teachers"
section) is just a normal `employee_type='teacher'` record with `name`/`private_email`
still blank. `_gw_missing_fields()` already requires both, so `action_create_google_account()`
raises its existing `UserError` for a still-unidentified placeholder exactly like it would
for any other incomplete employee — **no special-casing was needed for this integration
itself.**

The only addition, at the very end of `action_create_google_account()`'s success path: if
`schedule_import_code` is set, post a chatter note naming the original code, then clear it
(`emp.write({'schedule_import_code': False})`). This is what lets an admin's normal flow —
open the placeholder record, fill in the real `name` + `private_email`, click **Generate
Google account** — double as the "confirm this teacher's real identity" step, with no
separate action needed. The schedule/`ems.teaching`/`ems.attendance_template` rows created
at import time are untouched; they were already attached to this same `hr.employee` id.

## Pitfalls (native hr v18)

- `work_email` is a stored compute on `work_contact_id.email`, and writing
  `user_id` swaps `work_contact_id` to the user's partner (`_sync_user`). Creating
  the user **without `email`** would wipe the just-written corporate address.
  Same for `mobile_phone` → pass `mobile` in the create values.
- With `email` set, `auth_signup` sends the invitation mail on user creation unless
  `no_reset_password=True` is in the context.
- Re-entrancy is safe: linking `user_id` re-enters `write()` but `_gw_ready()` is
  `False` once `work_email` is set.

## Tests

`tests/test_employee_ems_user.py` (`TestEmployeeEmsUser`) — user creation, groups per
type, OAuth capture/backfill, idempotence, re-link of archived users, `work_email`
survival regression, lifecycle sync, no invitation mail, and `action_create_ems_user`
(links the user without touching the Google API, idempotent, no-op without
`work_email`). The SMTP transport is patched class-wide (see `tests/test_strike.py`
pattern). Google-side behaviour, the `google_ws_state` compute for every state, and the
`google_ws_suspended` migration backfill are covered by
`tests/test_employee_google_workspace.py`; the analogous student-side `google_ws_state`
and backfill tests live in `tests/test_exit_management.py`.
`tests/test_employee_google_workspace_tour.py` +
`static/tests/tours/employee_google_workspace_tour.js` open the employee form in a real
browser for each state and assert exactly one header button renders — the client-side
render that a `TransactionCase` cannot exercise. The student-side integration has its own
`tests/test_student_google_workspace.py` — see
[Google Workspace student integration](../contacts/google_workspace_student.md#tests).
