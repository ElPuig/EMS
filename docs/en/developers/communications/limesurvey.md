# Technical Reference: LimeSurvey integration (`models/communications/limesurvey.py`)

## Overview

Unlike [`ems.notice`](notice.md) (self-contained, sends through Odoo's own `ir.mail_server`),
this file talks to a real, external LimeSurvey instance over its RemoteControl 2 JSON-RPC
API. That makes it the module's actual external-API trust boundary: **no automated test in
this codebase may ever call the real, production-connected LimeSurvey API** — every test
against this file mocks the HTTP layer (`requests.post`). A separate local LimeSurvey
container exists for manual, non-automated verification only.

This doc is being filled in block by block, following the 5-block DTON split agreed for this
phase (`limesurvey_api` → module-level orchestration → `ems.limesurvey.header` →
`ems.limesurvey.recipient`/`.block`/`.enrollment`). Sections below are added as each block
lands.

---

## Architecture: why multithreading ([`ems.multithreading`](../shared/multithreading.md))

External API calls are slow, and Odoo times out long-running HTTP requests; the model group
solves this with `run_in_thread()`'s four-stage pattern:

```mermaid
flowchart LR
    A["setup()\nread-only cursor\nloads DB data into a\npersistent dict"] --> B["compute()\nno cursor at all\nslow API calls happen here"]
    B --> C["store()\nwrite cursor\ncommits persistent dict\nback to Odoo, retries\non commit conflict"]
    C --> D["callback()\nnotifies completion\n(front-end refresh)"]
```

`ems.limesurvey_header`'s `action_*` methods each build `setup`/`compute`/`store` closures
around this shared skeleton (`run_action()`, block 3) and hand them to `run_in_thread()`.
`ems.limesurvey_recipient` reuses the exact same skeleton for single-recipient actions.

---

## Block 2: `LimesurveyApi` — the raw RemoteControl 2 JSON-RPC client

`LimesurveyApi` (renamed from `limesurvey_api` in this pass, for PascalCase consistency with
every other class touched in this rollout) wraps LimeSurvey's RemoteControl 2 protocol:

```mermaid
sequenceDiagram
    participant Caller
    participant Api as LimesurveyApi
    participant LS as LimeSurvey RC2 API

    Caller->>Api: create_survey() / list_participants() / ...
    Api->>LS: get_session_key(user, pwd)
    LS-->>Api: session_key
    Api->>LS: <method>(session_key, ...params)
    LS-->>Api: result
    Api->>LS: release_session_key(session_key)
    Api-->>Caller: parsed result (or raised UserError)
```

**Every public method opens and releases its own session** — `_run_api_request()` calls
`_get_session_key()` before the request and `_release_session_key()` in a `finally` block
after, so a method that needs several RC2 calls (e.g. `create_survey`'s
`import_survey` → `set_survey_properties` → `activate_tokens`) does a full
handshake/release cycle per call, not once for the whole method. This matters for testing:
mocking `requests.post` for an N-call method requires 3×N queued responses (session key,
call, release — repeated per call), not N+2.

Credentials (`limesurvey_api`/`_usr`/`_pwd`/`_gid`) are read once in `__init__` from
`env.company`; `limesurvey_pwd` is itself a compute/inverse pair backed by Fernet-encrypted
storage (`models/settings/company.py`), same pattern as the Google Workspace service-account
JSON on the same model.

### Error handling

- `_parse_api_response()` centralizes the three ways an RC2 call can fail: non-200 HTTP
  status (raises with the response's own HTML error page scraped down to the `error-title`
  text via `_extract_limesurvey_html_error`), a non-JSON body, or a JSON body carrying an
  `error` key.
- `_run_api_request()` additionally raises if the call *succeeds* at the transport/JSON level
  but the RC2 `result` field is `None` — LimeSurvey uses this to signal permission/method
  errors that don't come back as an `error` key.
- Every public method (`create_survey`, `delete_survey`, `activate_survey`, ...) then applies
  its own success predicate on top of that (e.g. `delete_survey` treats `{"status": "No
  permission"}` as "already deleted" only if a follow-up `get_survey_properties` confirms the
  survey no longer exists).

### Fixed in this pass

- **`count_participants`**: local variable was named `list`, shadowing the Python builtin —
  harmless here (nothing else in the method needed `list()`) but a normalization fix per this
  rollout's convention. Renamed to `participants`.
- **`create_survey`**: bare `except:` → `except Exception:`.
- **`remind_participants`**: built a `data` list that conditionally included `part_ids`, but
  the actual `_run_api_request` call ignored it and always sent `[survey_id]` — meaning
  `part_ids` was silently dropped even when the caller passed it. Verified via grep that the
  only current caller (`do_send_reminders`, block 3) never passes `part_ids`, so this was
  latent/inert, not an active production bug — fixed anyway since the intent was clear and
  the fix is zero-risk (the params list is now actually threaded through to the RC2 call).
- **`get_group`**: compared `g['name'].lower()` against an un-lowercased `name` parameter —
  a case-sensitivity bug that would silently fail to match e.g. `"Students"` against a group
  literally named `"students"`. Verified via grep that `get_group` is never called anywhere
  in the current codebase (dead code) — fixed defensively (`name = name.lower()` added)
  since it's zero-risk and the bug would otherwise resurface the moment this method gets a
  caller.
- Class renamed `limesurvey_api` → `LimesurveyApi`; its two call sites
  (`run_action`'s `setup()` closure, and the survey-cleanup loop in `ems.limesurvey_header`)
  updated accordingly. Tabs → spaces throughout the class body.

No other bugs found in this class — the session handshake, error parsing, and each method's
own success/failure branches all matched their evident intent once traced against actual RC2
response shapes (a boolean/echo success flag per changed property, e.g. `{"expires": true}`
from `set_survey_properties`, not an echo of the submitted value — this shape is why
`deactivate_survey`/`reactivate_survey` can share the same `result.get("expires")` truthy
check despite setting the field to a date string vs. `None` respectively).

### Tests

`tests/test_limesurvey_api.py` (new, 33 tests) — every test mocks `requests.post` via
`unittest.mock.patch`, queuing one `(session_key, method_result, release_ack)` response
triplet per expected RC2 call. Covers the session handshake itself, `_parse_api_response`'s
three failure paths, `_extract_limesurvey_html_error`'s scraping, and each public method's
success/failure branches (including the `create_survey` cleanup-on-partial-failure path,
which mocks `delete_survey` directly to isolate it from the RC2 calls it would otherwise
trigger).

---

## Block 3: module-level orchestration (`do_*`, `run_action`, `load_persistent_data`)

Two regions of plain module-level functions (not methods — they take `ls_api`/`self` as
ordinary parameters, callable from either `ems.limesurvey_header` or
`ems.limesurvey_recipient`) sit between `LimesurveyApi` and the models that use it:

- **`do_*` functions** ("DETACHED PUBLIC METHODS" region): one function per user-facing
  action (`do_upload_survey`, `do_open_survey`, `do_remove_recipients`, ...). Each wraps its
  body in `_do()`, which normalizes the return contract (`True`/`False`) and, on any
  exception, stamps `traceback.format_exc()` onto every recipient dict in `survey["recipients"]`
  so the error surfaces per-row in the UI instead of only in the server log.
- **`run_action` / `load_persistent_data`** ("ATTACHED & SHARED METHODS" region): the glue
  between a model's `action_*` method and the `setup`/`compute`/`store`/`callback` skeleton
  described above. `run_action` builds the four closures and hands them to
  `self.run_in_thread(...)`; `load_persistent_data` walks either a header's
  `limesurvey_recipient_ids` or a single recipient and groups them by `internal_id` into the
  `surveys` dict that `compute()` and `do_*` operate on.

```mermaid
flowchart TD
    A["action_upload() (header/recipient)"] --> B["run_action(self, title, ...,\ncompute, persistent_data)"]
    B --> C{"already_running()?"}
    C -- yes --> Z["notify 'already running', return True"]
    C -- no --> D["is_running=True, state=status_w"]
    D --> E["run_in_thread(setup, compute, store, callback)"]
    E --> F["setup(): load_persistent_data()\ninto persistent_data['surveys']"]
    F --> G["compute(): for each survey,\ndo_upload_survey() / do_upload_recipients() / ..."]
    G --> H["store(): write persistent_data\nback onto the Odoo recipients"]
    H --> I["callback(): notify, is_running=False,\nstate=status_ok or status_ko"]
```

### Fixed in this pass

- **`run_action`'s synchronous-failure path was silently broken.** If `run_in_thread()` ever
  raised *before* spawning its thread (the only realistic case: the OS refuses to create a
  new thread), the `except Exception:` handler called `callback(self, traceback.format_exc())`
  — but `callback` only accepts `self`. That raised a `TypeError` inside the handler, which
  the immediately-following `finally: return True` then silently discarded (a `return` inside
  `finally` unconditionally swallows any exception in flight). Net effect: the caller saw
  `True` as if everything succeeded, `is_running` stayed `True` forever (blocking every future
  action on that record via `already_running()`), and the user got no failure notification at
  all. Fixed by threading the error through `persistent_data` — the same channel every other
  failure path in this function already uses — before calling `callback(self)` with its real
  signature. Covered by `test_run_action_recovers_when_run_in_thread_raises_synchronously`,
  which forces `run_in_thread` to raise and asserts `is_running` correctly resets to `False`
  and `state` correctly moves to `status_ko`.
- **`run_action` returned `None`, not `True`, when `already_running()` was true.** Every other
  path returns `True` (the `finally: return True` on the try/except covers both the success
  and the exception-recovery cases); the `if not self.already_running():` guard skipping that
  whole block left the function falling off the end with an implicit `None` instead. Harmless
  in practice (Odoo button-triggered methods treat `None`/`True` the same — no action /
  refresh), but inconsistent with the rest of the function's contract. Fixed with an explicit
  `return True` after the guarded block.
- **`load_persistent_data`'s guard clause raised the wrong thing.** `raise
  NotImplemented("...")` — `NotImplemented` is the singleton sentinel object used for
  `__eq__`-style protocol fallbacks, not an exception class, so calling it
  (`NotImplemented("...")`) itself raises `TypeError: 'NotImplementedType' object is not
  callable` before the intended message is ever seen. Verified this branch is otherwise
  unreachable in the current codebase (only ever called with `self` being
  `ems.limesurvey_header` or `ems.limesurvey_recipient`) — fixed to `raise
  NotImplementedError("...")` regardless, since the wrong exception type would otherwise
  confuse whoever eventually hits it.
- `_do`'s `except Exception as e:` — `e` was unused; narrowed to `except Exception:`.
- Tabs → spaces throughout both regions, matching this rollout's normalization convention.

### Investigated and closed, no fix needed — the `department` column (2026-07-30)

`_build_csv()`'s `department` column is a hardcoded literal `"DEPARTMENT"` for every row —
unlike every other column (`level`, `topic`, `subject_code`, `subject_name`, `degree`,
`group`, `trainer`), which is read from the actual survey response via a per-block `{prefix}`
key (see [Block 4](#block-4-emslimesurvey_header-crud--action-methods) below for where those
prefixed keys come from). Confirmed by reading `replace_block_content()` (the function that
fills in a block's own placeholders when a survey is generated): there is no `{'DEPARTMENT'}`
placeholder anywhere in the block-generation pipeline, unlike `{'LEVEL'}`/`{'S_CODE'}`/
`{'DEGREE'}`/etc. — department is never generated as a per-block question code in the first
place, so `_build_csv()` has no real value it could read even if it tried. `ems.subject` also
has no department-like field to derive one from.

**Developer's decision (2026-07-30):** leave as-is, deliberately. There is currently no clear
way to relate a student to a department in EMS, so wiring this up for real isn't attempted.
The literal `"DEPARTMENT"` string is a **legacy placeholder**: the exported CSV is fed into
Metabase (an external BI tool, outside this codebase) for reporting, and the department
column is filled in manually via a find-and-replace on the CSV before that import — this is
an accepted, existing operational step, not a bug to fix in EMS. Once Metabase is retired in
favor of doing this reporting directly from EMS (a future, not-yet-planned change), this
column will likely be dropped entirely rather than wired to real data. Not tracked as an open
plan — this is a closed, intentional decision, not a pending gap.

### Tests

`tests/test_limesurvey_orchestration.py` (new, 33 tests):
- `TestDetachedHelpers` — `_do`, `_email_not_empty`, `_clean_trainer`, `_build_csv`, no DB or
  API involved.
- `TestDoFunctions` — every `do_*` function against a `MagicMock()` standing in for
  `LimesurveyApi` (never the real class, let alone the real API), covering each function's
  success and failure branches, including `do_upload_recipient_changes`'s three-way branch
  (update in place / move to an existing survey / create a brand-new survey).
- `TestLoadPersistentData` — real `ems.limesurvey_header`/`ems.limesurvey_recipient` records
  (this shared infrastructure needs real Odoo recordsets, not mocks), covering both calling
  conventions (header walking its recipients; a single recipient loading its own survey), the
  grouping-by-`internal_id` behavior, and the `NotImplementedError` guard.
- `TestRunAction` — real header record with `run_in_thread` patched (`autospec=True`) to run
  the four closures synchronously, or to raise, isolating `run_action`'s own control flow from
  actual threading. Covers the success path, the synchronous-failure regression above, and the
  already-running guard.

---

## Block 4: `ems.limesurvey_header`

The survey definition and the entry point for every action (`action_compute`,
`action_upload`, `action_open`, `action_close`, `action_reopen`, `action_download`,
`action_remind`, `action_draft`, `action_remove`) — each `action_*` (other than `action_compute`
/`action_draft`, which are pure-DB and need no threading) builds a `compute()` closure that
iterates `persistent_data["surveys"]` and calls the matching `do_*` function from
[Block 3](#block-3-module-level-orchestration-do_-run_action-load_persistent_data), then hands
it to `run_action()`.

```mermaid
flowchart TD
    A["action_compute()"] --> B["_compute_recipients_students/teachers/asp()"]
    B --> C["state = 'computed'"]
    C --> D["action_upload() -> run_action(..., compute_survey_data=True)"]
    D --> E["state = 'uploaded'"]
    E --> F["action_open()"] --> G["state = 'open'"]
    G --> H["action_remind() (repeatable)"]
    G --> I["action_close()"] --> J["state = 'closed'"]
    J --> K["action_reopen() -> back to 'open'"]
    J --> L["action_download()"] --> M["state = 'closed', csv_data populated"]
```

`compute_survey_data(recipient, only_key)` builds each recipient's survey key (a SHA-256 hash
of a `survey_name` string built from the header + its `limesurvey_block_ids`, so two
recipients whose blocks resolve identically end up sharing one survey) and, when `only_key` is
`False`, the actual TSV content sent to `create_survey`. Blocks can be **special** (filtered by
course/WPI-enrollment/per-subject-enrollment) or plain; a `special_type='subject'` block is
repeated once per non-tutorship subject enrollment on the recipient.

### Fixed in this pass

- **Significant bug in `compute_survey_data`'s per-subject-enrollment branch.** The line
  deciding whether to append teacher names to a subject block's title read `if
  len(teacher_name) > 0:` — but `teacher_name` (singular) is a *different* variable, only ever
  assigned later in the method's `if append:` branch, which a `special_type='subject'` block
  never reaches (`append` stays `False` for it). The correctly-computed value for *this*
  iteration was `teachers_names` (plural, built two lines above from `ems.teaching` records for
  the current enrollment's group+subject). Concretely, this meant: (a) if no earlier block in
  the same `limesurvey_block_ids` loop had happened to set `teacher_name` yet — e.g. a
  subject-enrolled block is the *first* block — the method raised `UnboundLocalError:
  local variable 'teacher_name' referenced before assignment`, crashing survey generation
  entirely; (b) otherwise, it silently used a **stale value left over from an unrelated
  earlier block** to decide whether to show *this* subject's actual teachers, either dropping
  real teacher names or (less likely) appending them based on the wrong condition. Fixed by
  using `teachers_names` (the freshly-computed, correct value) in the condition. Regression-
  covered by `TestComputeSurveyData.test_teacher_names_are_appended_to_subject_block_title`,
  which deliberately makes the subject-enrolled block the *only* block on the header (so the
  old code would have hit the `UnboundLocalError` path, not just the stale-value path).
- **`_compute_recipients_teachers`/`_compute_recipients_asp`** — same `raise
  NotImplemented("...")` mistake as Block 3's `load_persistent_data` (`NotImplemented` is the
  singleton comparison-protocol sentinel, not an exception class — calling it raises `TypeError:
  'NotImplementedType' object is not callable`). `action_compute`'s own `try/except Exception`
  already caught whichever `TypeError` resulted, so this wasn't a hard crash, just a confusing
  message ("...'NotImplementedType' object is not callable" instead of "...Coming soon...").
  Fixed to `raise NotImplementedError(_("Coming soon..."))` — newly-wrapped literal, `.po`
  entries added to `i18n/ca_ES.po`/`i18n/es_ES.po`.
- Class renamed `ems_limesurvey_header` → `EmsLimesurveyHeader`; added `_order = "create_date
  desc"` (matching `ems.notice`'s precedent — most-recent-first is the natural listing order
  for a wizard-like record with no other obvious sort key). Loop variables normalized to match
  their model (`rec` → `recipient`/`header`, `std`/`grp` → `study`/`group` in the two onchange
  methods) per this rollout's convention. Tabs → spaces throughout.

### Access control (updated 2026-09-05)

Applies identically to all 4 models in this file (`ems.limesurvey_header`/`.block`/
`.recipient`/`.enrollment`), enforced by `security/rules/communications.xml` (one admin rule +
two quality-coordinator rules per model, mirroring the coexistence/`ems.strike` idiom in
`security/rules/coexistence.xml`):

| Group | Sees | Creates/edits/deletes |
|-------|------|------------------------|
| `group_academic_admin` | Every survey/block/recipient/enrollment | Everything |
| `group_quality_admin` (Quality coordinator) | Every survey/block/recipient/enrollment (read-only for others') | Only the ones they created |
| `group_quality` (plain Quality team member) | Everything (unchanged, unrestricted) | Everything except unlink (unchanged — `ir.model.access.csv` only, no per-owner `ir.rule`) |

**Fixed a pre-existing gap:** `group_academic_admin` previously had **no**
`ir.model.access.csv` row at all for any of these 4 models — despite `menu_limesurvey_headers`
(`views/communications/surveys/header/menu.xml`) already listing `group_academic_admin` as one
of the menu's visible groups. An admin clicking "Surveys" would have hit an `AccessError`
immediately. Added `access_ems_limesurvey_{header,block,recipient,enrollment}_admin` rows plus
matching `rule_limesurvey_*_admin` `ir.rule`s (`domain_force=[(1,'=',1)]`), so admin access now
actually matches what the menu already implied.

**New restriction for the Quality coordinator specifically** (`group_quality_admin` —
previously had unrestricted full CRUD, same as plain `group_quality`): two rules per model,
one read-only with an open domain (`perm_read=True`, `domain_force=[]`) and one write/create/
unlink-only scoped to `create_uid = user.id` (`perm_read=False`). Every record across all 4
models is created directly by whichever coordinator is operating that survey — no `sudo()`,
cron, or `queue_job` path exists in this file that creates or writes these on someone else's
behalf (`action_compute`/`action_upload`/etc. all run synchronously or via
[`ems.multithreading`](../shared/multithreading.md)'s `run_in_thread`, which explicitly
captures and reuses `self.env.uid` from the request that triggered it — see
`run_in_thread`'s own docstring) — so `create_uid` reliably identifies the owning coordinator
everywhere, including `ems.limesurvey_block`/`.recipient`/`.enrollment`, which have no
standalone menu and are only ever reached inline through their parent header's form.
Regression-covered by `TestLimesurveyAccessControl` in `tests/test_limesurvey_header.py`.

### Testing note: `unlink()` and `action_upload()` etc. can reach the real API directly

Unlike `run_action()`'s callers (which go through `run_in_thread`, itself easy to patch),
`unlink()` calls `LimesurveyApi(self.env).delete_survey(...)` **synchronously, inline**, for
any recipient that still has an `external_id`. A test that deletes an "uploaded" header
without mocking `LimesurveyApi` would silently attempt a real network call using whatever
`env.company.limesurvey_api/_usr/_pwd/_gid` happens to be configured on this box. Every test
that exercises this path patches `LimesurveyApi` at the module level
(`odoo.addons.ems.models.communications.limesurvey.LimesurveyApi`) to a `MagicMock` first.

### Tests

`tests/test_limesurvey_header.py` (new, 21 tests):
- `TestLimesurveyHeaderCore` — required fields, the two onchange cascades, `action_compute`'s
  recipient-building (group/level/study filters, email fallback `student_email` → `email`,
  enrollment sub-records, exclusion of students with no `main_group_id`), `action_draft`,
  `unlink()`'s three state-gated branches (blocked / redirect-warning / allowed) plus the
  API-touching branch (mocked), `action_get_csv`, `action_none`, and one representative
  `action_upload()` run with both `LimesurveyApi` and `run_in_thread` mocked end-to-end to
  prove the wiring works without ever touching the network.
- `TestComputeSurveyData` — the regression test for the `teacher_name`/`teachers_names` bug
  above, plus a smoke test of `only_key=True` mode.
- `TestLimesurveyAccessControl` (added 2026-09-05) — admin's full access across all 4 models
  (the pre-existing gap above), and the Quality coordinator's read-all/edit-own split, exercised
  on `header`/`block`/`recipient`/`enrollment` alike.

---

## Block 5: `ems.limesurvey_recipient` / `.block` / `.enrollment`

Three smaller satellite models:

- **`ems.limesurvey_block`** — one content block within a header's TSV, with optional
  `special_*` filters (course, WPI-enrollment, per-subject-enrollment, tutorship) consumed by
  `compute_survey_data` (Block 4).
- **`ems.limesurvey_recipient`** — one row per person invited to a survey; can be
  auto-populated (`ems.limesurvey_header._compute_recipients_students`) or added manually
  (`state='manual'` at create time, restored from the linked `student_id` via
  `action_restore()`, then immediately flipped to `'pending'` — `'manual'` never survives as a
  persisted value, it only exists to trigger the restore-and-normalize dance inside `create()`).
  Its own `action_upload`/`action_remind`/`action_delete` mirror the header's actions
  ([Block 3](#block-3-module-level-orchestration-do_-run_action-load_persistent_data)/
  [Block 4](#block-4-emslimesurvey_header)) but operate on a single recipient.
- **`ems.limesurvey_enrollment`** — a recipient-scoped *copy* of the student's real
  `ems.enrollment` rows, editable independently so quality staff can tweak survey content
  without touching the real enrollment data (only secretarial staff should do that).

### Fixed in this pass

- **Two real bugs found and fixed in `action_remind`/`action_delete`.** Unlike every other
  `run_action`-based method in this file (`action_upload` here, and all six
  `ems.limesurvey_header` actions), these two skipped the `success = persistent_data["success"]`
  / `if success:` guard entirely and went straight to `for key in persistent_data["surveys"]:`.
  If `setup()` ever failed (i.e. `load_persistent_data`/`compute_survey_data` raised for this
  recipient — a realistic possibility given how much `compute_survey_data` does), `persistent_data["surveys"]`
  is never populated, and this unconditional access raises `KeyError: 'surveys'` inside
  `compute()`. In real (non-mocked) usage `compute()` runs inside `run_in_thread`'s background
  thread, **outside** any try/except of `run_action`'s own (that only wraps the call that
  *starts* the thread) — an uncaught exception there is silently swallowed by Python's default
  thread exception handling, so the failure would never reach the user: the record would just
  sit stuck in `is_running=True` forever with no notification, same class of symptom as the
  `run_action` bug fixed in Block 3, but reachable through a different gap. Fixed by adding the
  same `success = persistent_data["success"]` / `if success:` guard already used everywhere
  else in this file. Regression-covered (within the practical limits of a synchronous-mock
  test harness — see `test_action_remind_survives_failed_setup`/
  `test_action_delete_survives_failed_setup`) by forcing `load_persistent_data` to raise and
  confirming the call completes without raising.
- **`create()`'s manual-recipient path crashed with `KeyError: 'student_id'`** if a `'manual'`
  record was created without a `student_id` at all — `self.env["res.partner"].browse([v["student_id"]])`
  used direct dict-bracket access instead of `.get()`. `action_restore()` (called right after)
  already handles "no student" gracefully (`else: return False`), so the autofill block should
  too. Fixed to `browse(v.get("student_id"))` (Odoo's `browse()` treats `None`/falsy as an
  empty recordset, so `student.name`/`student.student_email` cleanly read as `False` when
  absent — no behavior change for the normal case where `student_id` is provided, which the
  UI's add-student popup always does).
- Classes renamed `ems_limesurvey_block`/`ems_limesurvey_recipient`/`ems_limesurvey_enrollment`
  → `EmsLimesurveyBlock`/`EmsLimesurveyRecipient`/`EmsLimesurveyEnrollment`. Loop variables
  normalized (`rec` → `block`/`recipient`/`enrollment` per model). Tabs → spaces.

### Fixed 2026-07-30: `special_wpi_enrolled`/`special_subject_enrolled` → `special_type`

The two mutually-exclusive Booleans (`special_wpi_enrolled`, `special_subject_enrolled`) were
kept in sync by `_onchange_special`, but the exclusion only worked in one direction (checking
WPI cleared Subject; checking Subject while WPI was already on silently reverted Subject with
no feedback) — the `elif` branch could never fire with a `True` value to clear. A pre-existing
TODO comment on that line already questioned whether checkboxes were the right widget; the
developer chose the radio-button redesign over patching the onchange asymmetry, for clarity to
the end user (mutual exclusion becomes structurally guaranteed, not logic-enforced).

Replaced both Booleans with a single `special_type` `Selection(['wpi', 'subject'])` field
(`widget="radio"` in the view) — `_onchange_special` is gone entirely, nothing to keep in
sync. `compute_survey_data`'s branch (line ~891) now checks `block.special_type` instead of
the two booleans. `special_tutorship` (a third, independent Boolean also on this model) was
**not** folded in — it's checked in a separate, unconditional branch further down
`compute_survey_data` and was never part of the WPI/Subject exclusion.

**Migration:** existing data (25 `wpi` + 25 `subject` + 100 neither, confirmed against both
this dev DB and a real production snapshot) is preserved via
`migrations/18.0.0.22.0/{pre,post}-migrate.py` (`_rename_old_special_columns`/
`_backfill_special_type`), following the same rename-before-schema-sync pattern already used
for the `attendance_status` migration in the same version.

Tested in `tests/test_limesurvey_recipient.py::test_special_type_selection_is_exclusive_by_construction`
and `tests/test_limesurvey_header.py::test_special_type_wpi_appends_block_for_enrolled_student`
(the latter closing a pre-existing coverage gap — no test had exercised the WPI branch of
`compute_survey_data` before this change).

**Tour added (2026-07-30), prompted by the developer asking whether the view change itself
had actually been verified in a browser** — it hadn't; `static/tests/tours/limesurvey_block_tour.js`
+ `tests/test_limesurvey_block_tour.py` is the first tour for this model, covering the
"form within a form" path (the header's non-editable `limesurvey_block_ids` one2many list
opens the block's own registered form in a modal dialog): create a header, add a block,
toggle `special` on, pick the `special_type` radio option, save, reopen to confirm it
persisted. Building it caught two real, pre-existing (not new) bugs unrelated to this
specific change — see `plans/missing_tour_coverage_audit.md`, the backlog item this
prompted for the rest of the module:
- Odoo's `SelectionField` JSON-stringifies the option `value` HTML attribute, so
  `run: "select students"` on the header's own `target` field silently selects nothing —
  `run: "selectByLabel Students"` is the correct action for a plain `<select>`.
- `widget="code"` (`tsv_raw_text`, both header and block forms) renders via the Ace editor
  library; its real input is a deliberately invisible textarea the tour engine's generic
  `edit` action can't drive — needs `ace.edit(anchor).setValue(text, -1)` in a custom
  `run()`, following the same pattern Odoo core's own tours use
  (`addons/test_website/static/tests/tours/reset_views.js`).

### Testing note

Same rule as Block 4: `ems.limesurvey_recipient.create()`'s manual-add-to-an-already-uploaded-header
path calls both a real `self.env.cr.commit()` (stubbed via `patch.object(self.env.cr, 'commit')`
in tests — Odoo's `TransactionCase` forbids real commits) and `action_upload()` (which reaches
`run_in_thread`/`LimesurveyApi` exactly like every other action — both mocked, same as
elsewhere in this phase).

### Tests

`tests/test_limesurvey_recipient.py` (new, 19 tests): `TestLimesurveyBlock` (the onchange,
including a test documenting the known asymmetry above), `TestLimesurveyRecipient`
(`action_restore`, `create()`'s manual-state autofill and its two bugs above, `_compute_inuse_student_ids`
— tested via `write()` since `'manual'` never survives `create()`, `open_error_popup`, and
`action_remind`/`action_delete`'s happy path plus their failed-setup robustness), and
`TestLimesurveyEnrollment` (`_compute_inuse_subject_ids`, the `related` fields).

---

## Phase summary

All five blocks of this phase are complete. `limesurvey.py`'s full DTON pass: every class
renamed to PascalCase, all tabs converted to spaces, loop variables normalized to their model,
9 real bugs found and fixed (4 in `LimesurveyApi`, 2 in `run_action`, 1 in
`load_persistent_data`, 1 in `compute_survey_data`, 1 in `_compute_recipients_teachers`/`_asp`,
2 in `action_remind`/`action_delete` — see each block's section above for details), 2 gaps
found and left for a product decision (the CSV `department` placeholder, the block
special-fields mutual-exclusion asymmetry), and full test coverage added from zero
(`tests/test_limesurvey_api.py`, `test_limesurvey_orchestration.py`, `test_limesurvey_header.py`,
`test_limesurvey_recipient.py`) — every single test mocking the network/API layer, per the
standing rule that no automated test in this codebase may ever call the real,
production-connected LimeSurvey service.
