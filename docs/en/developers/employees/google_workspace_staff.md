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
        EMP->>Q: _gw_enqueue_create(): with_delay(_gw_create_account, identity_key)
        Note over HR,Q: the "Create Google account" button queues this same job (#582)
        Q->>EMP: SELECT ... FOR UPDATE NOWAIT (_gw_lock_for_creation)
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
5. `user._ems_link_google_signin(google_id)` (`res.users`, `models/shared/google_signin.py`,
   shared with the student portal sign-in) sets `oauth_uid` + `oauth_provider_id`
   when the id is known and not taken by another user (auth_oauth unique constraint).
6. Link `employee.user_id`, call `_sync_security_groups()` so role/job-mapped
   groups apply immediately (the `write()` trigger only fires on
   `role_ids`/`job_id`/`tutorship_ids`), and post a chatter summary
   (created/re-linked + whether Google sign-in was pre-linked).

Call sites inside `_gw_create_account()`:

- **Success path** — right after `work_email` is written, before
  `_gw_deliver_credentials()`, with the `id` from the `users().insert` response.
- **Adopt path** (employee already had a corporate `work_email`, e.g. manual email or
  data migrated from before the integration) — delegates to `action_create_ems_user()`
  (below) instead of calling `_ems_create_user` inline, so the same code runs whether
  it is reached automatically or by the user pressing the dedicated button.

### `action_create_ems_user()`

Public action (no Google API call): `_ems_create_user(google_id=self._gw_google_user_id())`,
guarded by the same `employee_type`/`work_email` checks. This is the Actions dropdown entry shown
in the `pending_user` state (below) — a corporate account already exists but no `res.users`
is linked yet — and it is what `_gw_create_account()`'s adopt path now calls
internally, so there is a single implementation either way.

In **dry-run** (`company.google_ws_dry_run`) no API call is made, so there is no
Google id: the EMS user is created without OAuth fields.

### One creation at a time (#582)

The automatic creation and the **Create Google account** entry used to be two independent paths
into Google: the job queued at save time called the creation, and so did the button, directly in
the web request. Pressed right after saving, both ran side by side, both saw no `work_email`, and
the loser got a 409 for the address the winner had just created, moved on to the next candidate
and created it, then rolled back on the database: an orphan second account in Google, invisible
in EMS. Three pieces close it, the same on `res.partner`:

- **One job.** `_gw_enqueue_create()` queues `_gw_create_account()` with the identity key
  `_gw_create_job_key()` (`gw_emp_create_<id>`). `_gw_enqueue_if_ready()` and the button
  (`action_create_google_account()`) both go through it, so queue_job's identity check keeps a
  second press, or a press after the automatic queuing, from adding a job. The button answers
  with a notification and reloads the form. When the employee isn't ready (missing data, an
  existing corporate or non-corporate address) the button still calls `_gw_create_account()`
  directly: those paths explain themselves or adopt the address, without creating anything in
  Google.
- **A hidden button while it lasts.** queue_job's identity check only covers waiting jobs, not a
  started one. `google_ws_creation_pending` (non-stored) is `True` while a job with that key is
  `wait_dependencies`/`pending`/`enqueued`/`started` (`google.workspace.mixin._gw_creation_job_running()`,
  `sudo()` since queue.job is admin-only), and the button's `invisible` includes it.
- **A row lock before Google.** `_gw_create_account()` starts with
  `google.workspace.mixin._gw_lock_for_creation()`: `SELECT ... FOR UPDATE NOWAIT` on the
  employee's row, then a cache invalidation. Whatever else is creating the same account at that
  moment holds the row, so this one fails before calling Google, with `LockNotAvailable` (or a
  serialization failure if the row changed since the snapshot), which queue_job and Odoo's HTTP
  layer both retry; the retry sees the address the first one saved and adopts it. This covers any
  other path into `_gw_create_account()` too, e.g. the reactivation fallback below.

### `action_relink_google_signin()`

Repairs "Sign in with Google" for an employee who **already has** an EMS user whose
OAuth fields were lost (`oauth_uid` / `oauth_provider_id` emptied by hand, by a bad
import, or by a partial restore). Without them the user cannot log in at all:
`auth_oauth` matches an incoming login exclusively by `(oauth_uid,
oauth_provider_id)`, and its fallback path (`signup`) fails because the login already
exists — so Google answers correctly and Odoo still returns *Access Denied*. There is
no e-mail-based fallback.

The action resolves the numeric Google id through the Directory API
(`_gw_google_user_id(raise_on_error=True)`) and hands it to the same
`res.users._ems_link_google_signin()` used by the creation paths, so there is one implementation
of the link itself. It never overwrites a link that is already there — the button is
hidden in that case — and it never touches the Google account.

Unlike the automatic paths, every failure is raised instead of swallowed: pressing a
button and getting no feedback is worse than an error message. `_gw_google_user_id()`
therefore takes a `raise_on_error` flag (default `False`, preserving the silent
behaviour the queue jobs rely on) and, when set, reports dry-run and API failure as
distinct errors. It deliberately does **not** try to tell "no such account" from
"account outside my scope": the service-account role is scoped to the managed OUs and
Google answers **403, not 404**, for anything outside them, so the two are not
reliably distinguishable from the response — the message names both causes instead. A
`oauth_uid` already claimed
by a different `res.users` (the `auth_oauth` unique constraint) is reported naming
that user, since the fix there is to clear the stale record first.

## Lifecycle

Archiving a member of staff does **not** suspend the Google account straight away. It opens
a 30-day grace period (issue #388): the account keeps working, a warning email goes out,
and a daily cron does the actual suspension once the date arrives. The EMS user, in
contrast, is still archived immediately — losing Odoo access is the point of archiving, and
it is reversible.

```mermaid
flowchart LR
    A[Archived] -->|warning email + chatter| B[google_ws_deactivation_date = today + 30]
    B -->|daily cron, date reached| C[Account suspended, moved to the suspended OU]
    B -->|unarchived| D[Schedule cancelled, nothing ever changed in Google]
    C -->|unarchived| E[Reactivated]
```

| Employee event | Google account | EMS user (`res.users`) |
|---|---|---|
| Created / completed (ready) | created (queued) | created + OAuth pre-linked |
| Archived (`active = False`) | **nothing yet**: `google_ws_deactivation_date` set to today + `GW_DEACTIVATION_DELAY_DAYS`, warning email sent, chatter note posted | archived immediately (`_ems_sync_user_active`) |
| Deactivation date reached (daily cron) | suspended, moved to suspended OU (queued) | unchanged (already archived) |
| Unarchived before the deactivation date | schedule cancelled; the account was never touched | unarchived |
| Unarchived while suspended | reactivated (queued) | unarchived |
| Deleted (`unlink`) | suspended synchronously | archived |
| Renamed (`name` written) | name patched to `_gw_split_name()` (queued), suspended accounts included | renamed (`_sync_user_name`, synchronous) |

Unlike the student side, staff accounts are **never deleted** — the issue only asks for
deletion of student accounts. `GW_DELETION_DELAY_DAYS` and `action_delete_google_account()`
exist only on `res.partner`.

The delay is a fixed constant in `models/shared/google_workspace_mixin.py`
(`GW_DEACTIVATION_DELAY_DAYS`, 30), not a company setting.

### Renaming (`action_sync_google_account_name`)

Writing `name` on a teacher/ASP whose `work_email` is in the company's Google domain
enqueues `action_sync_google_account_name()` (`_gw_enqueue_rename`, deduplicated by
`identity_key`), which patches the Google user's `givenName`/`familyName` with the same
`_gw_split_name()` heuristic used at creation time, through the mixin's
`_gw_sync_account_name()` (shared with students). The corporate address itself is never
changed. A non-corporate `work_email` is skipped (not an account EMS manages). A 403/404
answer (account deleted, or outside the managed OUs) posts a chatter note instead of
failing the job, since a retry could never succeed; any other error is raised so the job
shows as failed.

The linked EMS user is renamed too, synchronously and regardless of the Google integration
(`hr.employee._sync_user_name()`, `models/employees/employee.py`): native hr only syncs the
other way (renaming a `res.users` renames its employees), so a fixed employee name - typically
a pending-identification placeholder replaced by the real teacher - used to leave the user
with the old one. It writes `firstname`/`lastname`, never `name`, so the native sync does not
bounce it back. `migrations/18.0.0.33.0/post-migrate.py` aligned every user that had already
drifted, employee name winning, and queued the Google rename for them.

### The daily cron

`ems.ir_cron_gw_staff_lifecycle` (`data/main/ir_cron_google_workspace.csv`) runs
`hr.employee._gw_cron_process_lifecycle()` once a day, searching with `active_test=False`
(every candidate is archived by definition) and enqueuing the existing
`action_suspend_google_account` job rather than calling the Directory API itself:

```python
[('active', '=', False), ('google_ws_deactivation_date', '<=', today),
 ('google_ws_suspended', '=', False), ('work_email', '!=', False)]
```

### `unlink()` keeps suspending synchronously

A hard delete leaves no record to hold `google_ws_deactivation_date`, so there would be
nothing for the cron to find later — and it is not the archive path the grace period is
about. It therefore keeps suspending immediately, exactly as before.

### The warning email

`ems.mail_template_google_deactivation_employee`
(`data/main/mail.template-google_lifecycle.csv`) is sent once, when the schedule is
created, to **both** `private_email` and `work_email`: the corporate mailbox is still alive
during the grace period and is the one actually read day to day. An employee with neither
address gets the chatter note only.

The user archiving is deliberately **synchronous and independent** of
`google_ws_enabled` and of the job queue: a former employee must lose Odoo access
immediately even if the Google integration is disabled or the queue is down.
`_ems_sync_user_active` skips `self.env.user` and the superuser.

## Actions dropdown state (`google_ws_state`)

The employee form's Actions dropdown (`views/community/employee/form.xml`, see
[Form "Actions" dropdown](../shared/actions_dropdown.md)) offers at most **one** of four
mutually-exclusive Google/EMS user entries, driven entirely by one computed, stored `Selection`
field — `google_ws_state` — instead of each button evaluating its own combination of
`work_email`/`user_id`/`google_ws_suspended`/`google_ws_manual_email`. This replaced an
earlier version where two independently-computed `invisible` expressions could disagree
and show two entries at once for a teacher whose account was adopted from
pre-integration/migrated data (`work_email` set, `user_id` not yet linked) — the bug that
motivated the consolidation.

```mermaid
stateDiagram-v2
    [*] --> none: not teacher/asp
    none --> manual_pending: google_ws_manual_email ticked
    none --> pending_user: work_email set, no user_id\n(adopt / migration gap)
    manual_pending --> pending_user: work_email filled in manually
    none --> active: _gw_create_account() (queued job)\n(work_email + user_id both set)
    pending_user --> active: action_create_ems_user()
    active --> suspended: action_suspend_google_account()
    suspended --> active: action_reactivate_google_account()
```

| `google_ws_state` | Actions dropdown entry shown | Meaning |
|---|---|---|
| `none` | Create Google account (hidden while `google_ws_creation_pending`) | No corporate email yet |
| `manual_pending` | *(none)* | `google_ws_manual_email` ticked, waiting for the email to be typed in |
| `pending_user` | Create EMS User | Corporate email exists, no `res.users` linked (adopt / migration gap) |
| `active` | Suspend Google account (+ Re-link Google sign-in when `google_signin_missing`) | Fully set up |
| `suspended` | Reactivate Google account | `google_ws_suspended = True` |

The one button that is **not** part of that mutually-exclusive set is **Re-link Google
sign-in**, driven by its own non-stored computed boolean, `google_signin_missing`
(`google_ws_state == 'active'` and the linked user has no `oauth_uid`). It is a repair
offered *alongside* Suspend rather than another state of its own: the account is
genuinely active and fully set up, only the sign-in link is broken, so hiding Suspend
while it shows would misrepresent the account. The compute reads `user_id.oauth_uid`
through `sudo()` — an `hr.group_hr_user` who is not an Odoo administrator cannot read
`res.users` OAuth fields, and the button must still render for them.

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
| Plain employee creation | `name` (plus `private_email` at view level for **new** teacher/ASP records, except a vacancy, which needs its `schedule_import_code` instead) |
| Google account creation | `name`, `private_email` (recovery + credentials email, never an address of the centre's own domain, see [Personal email can never be a corporate one](../contacts/google_workspace_student.md#personal-email-can-never-be-a-corporate-one-514)); phone/NIF optional |
| EMS user creation | corporate `work_email` (produced by the previous step) |

## Vacancies pending identification (#584)

A vacancy is a teacher record with `schedule_import_code` set (`pending_identification` computed
`True`): a post with its department, schedule and so on, but nobody filling it yet. The
working-schedule importer creates them from a placeholder code (see
`docs/en/developers/employees/working_schedule.md`'s "Pending-identification teachers"), and a Head
of Studies creates them by hand from the form.

```mermaid
stateDiagram-v2
    [*] --> named: form, staffing type "Named teacher" (default)
    [*] --> vacancy: form, staffing type "Vacancy" + code
    [*] --> vacancy: schedule importer, placeholder code
    vacancy --> named: staffing type switched to "Named teacher" (+ name, private email)
    vacancy --> named: adopt an existing corporate account (Create EMS User)
    named --> [*]
```

**`staffing_type`** (`models/employees/employee.py`) is what the form shows as "Staffing type":
`named` / `vacancy`, only on teachers. It has no column of its own. The compute reads
`schedule_import_code` (vacancy while it is set), so the selector and the code never disagree and
the importer's placeholders read as vacancies without a migration. The inverse:

- `vacancy`: requires a code and a teacher (`ValidationError` otherwise);
- `named`: calls `_ems_confirm_identity()`, which posts a chatter note with the code and clears it.

The transition is one-way: `write()` refuses to turn a named teacher (no code) into a vacancy,
whether through `staffing_type` or by setting `schedule_import_code` (`ValidationError`). Only
`create()` (the form or the schedule importer) makes a vacancy.

On the form, the selector is shown only while creating the record or while it is still a vacancy;
a saved named teacher doesn't show it at all.
Choosing "Vacancy" shows the required **Vacancy code** and hides the personal email (no longer
required), the suggested Google username and "Assign corporate email manually". Switching a saved
vacancy back to "Named teacher" makes the personal email required again (`not id or
pending_identification`; `pending_identification` only changes on save), since that save is what
creates the account.

**No account while it is a vacancy.** `_gw_ready()` is `False` while `schedule_import_code` is set,
so no creation job is queued whatever data the record has (a personal email typed in through
another path included). `_gw_notify_missing_fields()` stays silent too, since missing data is
expected on a vacancy. `_gw_create_account()` refuses it with a `UserError` before its missing-data
check, and the "Create Google account" button is hidden while `pending_identification`.

**Identifying the person** is switching the staffing type to "Named teacher" with their real name
and personal email, and saving. The inverse runs inside the base `write()`, after the stored
fields, so the code is already gone when this integration's `write()` calls
`_gw_enqueue_if_ready()`, which then queues the creation like for any new teacher (the single job
of #582). The schedule/`ems.teaching`/`ems.attendance_template` rows are untouched: they belong to
this same `hr.employee` id.

The **adopt path** confirms the identity too: a vacancy given a corporate address by hand
("Assign corporate email manually") and linked with **Create EMS User** ends up in
`_ems_create_user()`, which calls the same `_ems_confirm_identity()` once the user is linked. That
is also the way out for a person who already has a corporate account elsewhere, since the vacancy
must never get a new one.

**Unique code.** `_check_schedule_import_code_unique` (an `@api.constrains`, not a SQL
constraint, so existing duplicates never block an upgrade) rejects two **active** employees with
the same code. An archived vacancy doesn't block its code. Codes are stored stripped and compared
ignoring case through `hr.employee._search_by_schedule_import_code()`, which the importer uses too
(`_get_or_create_pending_teacher`, `_get_teacher`): "x1" typed on the form and "X1" in a file are
the same vacancy. Codes are not upper-cased, because the importer also stores real e-mail addresses
there (the "create new" path for an unknown e-mail).

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

`tests/test_employee_google_workspace.py` also covers #582: the button queues the same job
instead of creating (one job after two presses), `google_ws_creation_pending` while the job is
pending/started and not once it failed or finished, and `_gw_create_account()` stopping before
any Google call when the row lock fails (plus the lock itself, checked from a second cursor).

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
browser for each state and assert exactly one Google/EMS user entry is offered in the Actions dropdown — the client-side
render that a `TransactionCase` cannot exercise. That tour also covers the grace period's banner and its
"Cancel scheduled deactivation" entry on an archived teacher, reached through the search
panel's Archived filter.

`TestEmployeeGoogleWorkspaceLifecycle` (same file as the other backend tests) covers the
grace period itself (#388): scheduling on archive rather than suspending, the warning
email, the first date winning over a second archive, cancelling on unarchive and via the
button, the schedule being cleared once the account is actually suspended, the cron's
date/active guards and idempotence, and `unlink()` still suspending immediately.

The rename sync (#542) is covered in `TestEmployeeGoogleWorkspace` (`test_rename_*`,
`test_sync_name_*`): which writes enqueue it, the Directory API payload, the 403/404
report and dry-run.

The student-side integration has its own
`tests/test_student_google_workspace.py` — see
[Google Workspace student integration](../contacts/google_workspace_student.md#tests).
