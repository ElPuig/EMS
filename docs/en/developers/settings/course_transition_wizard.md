# Technical Reference: `ems.course_transition_wizard`

## Overview

`ems.course_transition_wizard` is the **end-of-year transition**: the single operation that closes the outgoing course and opens the incoming one. It freezes the academic history, turns graduates into archived alumni, places the returning students into their destination groups from their confirmed enrollments, and wipes the operational records of the year that just ended.

It is deliberately **scoped by study** (`study_ids`), because studies do not finish at the same time: a CFGS may be closed in June while an ESO level is still evaluating. Each run transitions the studies it is given and marks them `transitioned`; the **global course flip** (which course is "current") only happens on the run that leaves no `active` study behind.

The wizard is **preview-first**: nothing is written until a dry-run has listed the blockers, the warnings and the exact record counts, and the operator has ticked the backup checkbox. Step 8 is irreversible.

**Module files:** `models/settings/course_transition_wizard.py`, `models/curriculum/study.py` (`transition_state`), `models/enrollment/enrollment.py` (`_ems_admit_student` latecomer branch), `views/settings/course_transition_wizard.xml`, `views/settings/form.xml`, `security/ir.model.access.csv`, `tests/test_course_transition.py`, `static/tests/tours/course_transition_tour.js`

## Hierarchy and relations

```mermaid
erDiagram
    EMS_COURSE_TRANSITION_WIZARD ||--o{ EMS_COURSE_TRANSITION_WIZARD_LINE : "line_ids (preview)"
    EMS_COURSE ||--o| EMS_COURSE_TRANSITION_WIZARD : "source_course_id / target_course_id"
    EMS_STUDY }o--o{ EMS_COURSE_TRANSITION_WIZARD : "study_ids (scope)"
    EMS_COURSE_TRANSITION_WIZARD_LINE }o--|| RES_PARTNER : "student_id"
    EMS_COURSE_TRANSITION_WIZARD_LINE }o--o| EMS_GROUP : "destination_group_id"
    RES_COMPANY ||--o| EMS_COURSE : "current_course_id (flipped)"
    EMS_STUDY ||--o| EMS_STUDY : "transition_state active/transitioned"
```

Both models are `TransientModel`: the preview is a throwaway projection, never a stored plan.

## `ems.study.transition_state`

```python
transition_state = fields.Selection(
    [('active', 'Active'), ('transitioned', 'Transitioned')],
    default='active', copy=False)
```

A new field, so **no migration script** is needed (no XML ID is renamed). It is the switch that makes a *latecomer* work: `sale.order._ems_admit_student()` places a student immediately (group + subject enrollments) when the destination study is already `transitioned`, and leaves the placement to the bulk wizard while the study is still `active`. That branch already exists in `enrollment.py`, guarded by a `getattr` because the field did not exist yet; creating the field and dropping the `getattr` activates it.

Step 5 resets every study back to `active` when the flip happens, so the next course starts clean.

## Preview (dry-run — writes nothing)

### Blockers

| Blocker | Rule |
|---------|------|
| Target course | It exists and is different from `source_course_id` |
| Evaluation not closed | Every `ems.grade_session` of the **last round** (max existing `round` per group·subject) of the groups in scope is in state `final`, linking the offenders to `ems.action_grade_session_state_wizard` |
| Confirmed enrollment with no group | No `sale.order` of `_incoming_orders()` lacks `ems_group_id` (D13) |
| Student with no enrollment | No `missing` line whose `study_id.uses_enrollment_flow` is true (D17) |
| Origin study still evaluating | No study this run pulls a student **out of** — outside the scope and not yet `transitioned` — has an unfinalised last round (D11) |

### Warnings (informative, never blocking)

| Warning | Note |
|---------|------|
| Graduates continuing at the centre | `action = 'graduate_continue'`, **listed one by one**: they keep the graduation but are neither converted nor archived (D10) |
| Students with no destination | `transition_status = 'missing'`, **listed one by one** (D8), split by `study.uses_enrollment_flow` |
| Draft / sent enrollments in the target course | **NOT cancelled** — step 6 only touches the outgoing course. They stay open for a September confirmation |
| Incomplete evaluation | See the rule below (D9) |
| Attendance templates to archive | Including templates whose `group_ids` span studies both in and out of scope |
| Records to delete | Counts per model for step 8, grade sessions included |

### Incomplete-evaluation rule (D9)

The criterion depends on whether the group is in the **last course of its study**:

- **Not the last course** (e.g. 1st of a CFGM/CFGS): `internal_is_complete` on `ems.grade_subject_line`. Promotion to the next course is decided by the *internal* grade — the 90% awarded by the centre.
- **Last course**: `has_final`, which also demands the external (work placement) part.

The reason is that the **work placement (EM) only exists in the final course**, when students actually go to a company. Since the centre's `ems.planning` gives a 10% `external_ponderation` to first-course subjects as well, `_final_from_parts()` returns `(0, False)` for them — no final grade at all, not even a failing one. Using `has_final` everywhere would therefore report *every* first-course student as incompletely evaluated.

This mirrors the semantics already frozen in the academic history, where `ems.student.year_record.subject.state` is binary and **determined only by the RAs**: a pending or failed work placement never fails a subject, because the student repeats the placement, not the subject.

## Apply

```mermaid
flowchart TD
    S0["0 · Academic history<br/>generate_for_students(scope, source)"] --> GUARD{"Step 0 OK?"}
    GUARD -- no --> ABORT["Abort the whole wizard"]
    GUARD -- yes --> S1["1 · Graduates → alumni<br/>_ems_convert_to_ex_student()"]
    S1 --> S2["2 · Revoke portal<br/>_ems_revoke_student_portal()"]
    S2 --> S2B["2b · Archive the graduates<br/>active = False"]
    S2B --> S7["7 · Archive attendance templates"]
    S7 --> S8["8 · Operational cleanup<br/>IRREVERSIBLE"]
    S8 --> S3["3 · Placement (group)"]
    S3 --> S4["4 · Subject enrollments"]
    S4 --> S4B["4b · Detach the unplaced<br/>main_group_id = False"]
    S4B --> S5["5 · Mark transitioned<br/>+ conditional global flip"]
    S5 --> S6["6 · Outgoing enrollments<br/>lock confirmed / cancel draft"]
    S6 --> S9["9 · Audit: message_post + CSV"]
```

Steps 3 and 4 are a single bulk call to `sale.order._ems_apply_destination_placement()`, which is already idempotent and already ordered (group before subject enrollments). Every step is scoped to `study_ids` except the flip.

### Why the cleanup runs before the placement

The steps are numbered by the phase they belong to, not by the order they execute in: **7 and 8 run before 3 and 4**, and that is load-bearing rather than cosmetic.

`res.partner._ems_clear_operational_records()` deletes *every* `ems.enrollment` of the student with no group or course filter. It was written for a withdrawal, where the student leaves the centre altogether and keeping any enrollment would be wrong. Running it after the placement would therefore delete the very enrollments steps 3-4 had just created, leaving every promoted student in their new group with no subjects at all.

`tests/test_course_transition.py::test_apply_keeps_the_new_enrollments_after_the_cleanup` pins this down: swapping the two blocks makes it fail, together with the two placement tests.

### Archiving attendance templates cascades to their schedule lines (step 7)

`_templates_to_archive()` (the scope minus any template whose `group_ids` span a study still out
of scope) is archived via `action_archive()`, not a bare `write({'active': False})` — the
distinction matters: `EmsAttendanceTemplate.action_archive()` is overridden to also archive
`attendance_schedule_ids`, while a plain `write()` bypasses that override entirely. An earlier
version of this method used `write()` directly, which left every archived template's schedule
lines `active=True` forever - invisible in the template's own (now-archived) form, but still
matched by `classify_external_conflicts`/`find_self_conflicts` (`ems.attendance_template`, used by
the working-schedule import wizard's own conflict screens), silently contradicting those methods'
own docstring assumption that a transitioned study has nothing active left to reconcile against.
`test_apply_archives_the_schedule_lines_of_an_archived_template` pins this down - the two older
template tests never caught it because their own `_template()` fixture creates a template with no
schedule lines at all.

### Teacher calendar blocks in scope, counted at preview (`plans/course_transition_teacher_schedule_archival.md`, phase 5b)

`_migrating_calendar_blocks()` finds every active `resource.calendar.attendance` row, on any
teacher's real (non-framework) personal calendar, whose own `group_ids` belongs to a study in
scope — the calendar-side mirror of `_scope_templates()`'s domain, but read directly from the
calendar block itself rather than trusted purely via the attendance template it happens to back.
This is deliberately **independent** of `_templates_to_archive()`: a teacher can build their own
schedule bypassing the normal template/calendar sync, so a calendar block genuinely in scope isn't
guaranteed to have a perfectly-matching template/schedule line — `resource.calendar` is meant to be
the authoritative source for "what does this teacher's calendar say they're teaching," independent
of whether the template side agrees (see the plan's own decisions 3/4).

As of this phase, `action_preview()` only **counts** these blocks
(`calendar_block_count`, shown in the preview alongside `template_count`) — nothing is archived
yet. The actual archival cascade (using `ems.attendance_mixin.find_schedule_lines_for_slot` to
find and archive the matching schedule line, or just drop a departing co-teacher from
`teacher_ids` when another teacher's block for the same slot survives) is a later phase of the
same plan.

### Archiving the graduates (D4, step 2b)

Graduates are **archived**, not just converted, consistent with issue #357 (withdrawals and alumni are both archived, mirroring how archiving an `hr.employee` asks for a departure reason).

The archive runs **after** the portal revoke and lives in the wizard rather than in `_ems_convert_to_ex_student()`, for two reasons: the helper runs before the revoke, and `res.partner.write()` refuses to archive a contact still linked to an active portal user. A student whose revoke failed is reported and left active instead of raising, so one failure cannot roll back a batch of hundreds.

### Graduating and continuing at the centre (D10, step 2c)

Finishing a study and enrolling into another one are **independent facts, not a contradiction**. A CFGM graduate moving up to a CFGS, or a CFGS graduate starting a second one — even in another family — is both at once, and the case is high volume: the 25-26 data has 28 SMX leavers enrolled into ASIX/DAM/DAW.

Earlier versions treated it as a blocker ("a student cannot leave and come back in the same run"), which refused the whole transition. It is now derived and split:

```mermaid
flowchart TD
    G{"exit_type == 'graduation'<br/>and exit_course_id == source"} -- no --> OTHER["place / unplaced / missing"]
    G -- yes --> E{"non-cancelled sale.order<br/>in the target course?"}
    E -- no --> LEAVE["_leaving_graduates()<br/>step 2: alumni + portal revoke + archive"]
    E -- "yes, confirmed" --> STAY["_continuing_graduates()<br/>step 2c: keep student, clear exit metadata"]
    E -- "yes, draft/sent" --> PEND["_pending_graduates()<br/>step 2d: applicant, portal kept, not archived"]
```

**Nobody marks `graduate_continue`.** It is a computed preview label: the tutor only knows about the graduation, and the enrollment arrives on its own through the GEDAC assignment, so the wizard is the only place where the two facts meet.

### Why an unconfirmed offer becomes an applicant (D12, step 2d)

The three cases are not two. A graduate holding an offer **nobody has confirmed yet** can be neither placed (there is nothing to place) nor turned into alumni, and the reason is a hard constraint rather than a preference:

> #357 archives every alumnus, and `res.partner.write()` refuses to archive a contact with an active portal user. An alumnus is therefore, by construction, someone **without portal** — and `/my/gestion-matriculas` is `auth="user"`, so without portal the offer could never be confirmed. `_ems_revoke_student_portal()` makes it worse: it revokes the family's user too unless another child is still enrolled, cutting off both routes.

`applicant` is the state that already models this exact situation, and reusing it means no new machinery:

| Need | Already provided by `applicant` |
|------|--------------------------------|
| Portal access | `ems.portal.access.wizard` domain is `('contact_type', 'in', ('student', 'applicant'))`, and an applicant gets **its own** login rather than the family's |
| Sees the offer | `get_portal_enrollment()` filters by partner, state and course under `sudo()` — no `contact_type` check |
| Return path | `sale.order._ems_admit_student()` has always converted `applicant` → student on confirmation |
| Not archived | Applicants are never archived by the transition |

Conceptually it is not a workaround: an internal SMX graduate holding an ASIX offer is in the very same position as an outsider who preinscribed to ASIX. `study_id`/`level_id` follow the destination on the order so they read as an applicant of the study they are heading to; the exit metadata is cleared (they have not left, they are waiting to come in); `has_graduated` stays, which is what makes a later manual withdrawal land on alumni.

**D3 reversed:** the wizard used to offer an "archive applicants without a confirmed enrollment" checkbox. It never archived anything — the flag only ever reached a warning, no apply step consumed it — and the intent was wrong anyway: applicants with no enrollment in July are precisely the ones who may turn up in September, and now that a graduate holding an unconfirmed offer becomes an applicant itself, the sweep would have caught them too. Checkbox, counter, warning and `_declined_applicants()` are gone; summer clean-up stays manual.

**Order is load-bearing:** step 2c runs *after* `_apply_history()`, because `year_record._generate_one()` stamps how the student left the outgoing course by reading `exit_course_id` — which `_ems_convert_to_student()` clears. `has_graduated` is never touched: it is permanent (D2).

`_ems_convert_to_student()` also sets `active = True`, and `sale.order._ems_admit_student()` converts `alumni`/`withdrawal` as well as `applicant`, so the individual September path matches what the bulk `_apply_placement()` already did.

### Freezing the history on the way out of the group (D11)

`year_record._generate_one()` reads `student.main_group_id` to stamp the group, study, level and tutor of the year that ends. Step 0 therefore only reaches the students the run still sees in its own groups — and `_incoming_orders()` reaches **further than** `_scope_students()`, so a run can place a student whose origin study it is not transitioning.

Run order does not solve it. The 25-26 data has students finishing SMX to start ASIX/DAM/DAW; the symmetric case (finish ASIX start DAM, finish DAM start ASIX in the same year) makes the dependency **cyclic**, so whichever study runs first strands the other:

```mermaid
sequenceDiagram
    participant R1 as Run 1 (DAW)
    participant S as Student (SMX2A)
    participant R2 as Run 2 (SMX)
    R1->>S: _incoming_orders() reaches it, places it
    Note over S: main_group_id: SMX2A → DAW1A
    R2->>S: _scope_students() no longer sees it
    Note over S: no year record, and step 8 deletes<br/>the SMX grade sessions by group
```

So the freeze moved to `sale.order._ems_apply_destination_placement()` — the single choke point every placement goes through, bulk and individual — right **before** `main_group_id` is overwritten, passing the origin group explicitly through the new `group=` argument of `generate_for_students()`/`_generate_one()`.

`freeze_on_leaving()` is a no-op when a record for `(student, current_course)` already exists (the normal case: step 0 got there first) and when the origin study is already `transitioned` (its own run froze everybody, and the current course may already be the incoming one).

Two consequences elsewhere:

- **A blocker**, not a warning: freezing a history half-way is worse than refusing to run, so `_unclosed_origin_studies()` checks the last round of every out-of-scope origin study this run would pull someone out of. `_last_round_sessions()` now takes an optional `groups` argument so both blockers share it.
- **Step 8 clears `ems.enrollment` by group as well as by student**, for exactly the reason grade sessions already did: a student pulled out by another study's run is no longer in `_scope_students()`, and its enrollments in the outgoing groups would linger forever.

### Detaching whoever nobody placed (step 4b)

`ems.group` carries the course number but **not the academic year**, so groups are reused: a student left pointing at the outgoing group turns up next September as a member of the new cohort. Nothing used to clear it — leaving graduates lose it in step 1 and placed students have it overwritten in step 3, but everybody else kept it. On the 25-26 data that is ~107 students with no enrollment plus ~161 enrolled without a destination group.

The criterion is **who was actually placed**, not "who is still sitting in a group of the scope":

```python
stranded = (students - placed).filtered(lambda student: student.main_group_id)
```

`_apply_placement()` therefore returns the placed `res.partner` recordset instead of a count. Keying on the scope groups would detach a student promoted from 1st to 2nd year of the same study, since its destination group is in the scope too — `test_apply_keeps_the_group_of_a_student_promoted_within_the_same_study` pins that down.

`study_id` and `level_id` are deliberately **kept**: they record what the student was doing, which is what the "no destination" report and a late enrollment both read. Only the group goes.

### An unplaced student was a dead end (D13)

A `sale.order` confirmed **without** `ems_group_id` used to be a warning: *"they will be skipped"*. It was skipped indeed — and then there was no way back:

```python
# the probe that settled it
tras apply            -> no group
tras escribir el grupo -> no group          # write() had no side effect
tras action_confirm    -> UserError: "Some orders are not in a state requiring confirmation"
```

`_ems_apply_destination_placement()` only ran from `action_confirm()` and from the wizard's bulk pass, so filling the group in afterwards did nothing and the order could not be confirmed twice. The student was left with no group, no subject enrollments and no evaluation sessions, recoverable only by editing `main_group_id` by hand and creating every `ems.enrollment` one by one. On the 25-26 data that was **161 enrollments against 129 placeable ones**.

Two changes, because one alone is not enough:

- **A blocker**, not a warning. A warning is the right shape when the consequence is recoverable; this one was not.
- **`_ems_place_on_group_assignment()`**, called from `write()` when `ems_group_id` is filled in. It is deliberately narrow — `state == 'sale'`, placement is individual (below), and the student has **no** group yet. That last guard matters: `_ems_apply_destination_placement()` creates the new group's enrollments but does not remove the old ones, so re-pointing an already-placed student would leave it enrolled in two groups at once.

### The destination course of a re-enrolment (D15)

`_ems_suggest_group()` reads the destination course from `sale_order_template_id.study_year`. A **repeater** never goes through a template: they re-enrol only in what they failed, so the field is empty and the suggestion gave up before looking at a single group. On the 25-26 data that was 10 of the 51 confirmed enrollments with no destination group.

Matching their lines against a template as a whole does not work either — no template is ever a superset of them:

```
Zakariae Boukraa (SMX2D)
   Seguretat informàtica
   Muntatge i manteniment d'equips     <- module pending from an earlier course
   Matrícula El Puig Castellar         <- economic item
   Quota AMPA                          <- economic item
   Tutoria 2n SMX                      <- the one reliable handle
```

`_ems_course_from_tutorship()` uses the tutorship instead: there is exactly one per enrollment and it is course-specific (`Tutoria 2n SMX`, `T2_CFGS_ICB0_DAM`), so whichever templates sell that product pin the year down. It resolves all 10.

Ambiguity returns nothing and the group stays empty — no tutorship line, more than one, or templates disagreeing on the year. If the centre ever stopped making tutorships course-specific, the rule would simply find no answer instead of guessing wrong.

It does **not** touch the other 41: those fail because no group exists at all in the destination study/course/shift (GA1B afternoon promoting to a 2nd year that only exists in the morning, AD with no 2nd-year group at all). That is missing data, not a rule the code can improve.

### Newcomers stop being applicants at the worst moment (D16)

`_ems_suggest_group()` picked its strategy with `contact_type == 'applicant'`. The question it means to ask is *"is there an origin group to copy the letter from?"*, and the contact type looked equivalent — but it stops being true at exactly the wrong moment: confirming the enrollment runs `_ems_admit_student()`, which turns the applicant into a student. From then on a newcomer awaiting the bulk placement matched neither branch and got no suggestion at all.

The condition is now the absence of `main_group_id`, which is what the two strategies actually differ on. It surfaced on a single student — a GEDAC applicant admitted straight into 2nd year whose destination group did not exist when she enrolled — but 150 students were one manual step away from the same hole: `student`, no group, confirmed enrollment, waiting for the transition.

### Placement is individual after the flip too (D14)

`_ems_admit_student()` keyed the individual placement on `ems_study_id.transition_state == 'transitioned'`. But step 5 puts **every** study back to `active` once nothing is pending, so in the normal end state — the whole centre transitioned — the branch was true for nobody and confirming an enrollment in September placed no one:

```
flip=True | transition_state after the flip='active' | group after confirming=NONE
```

`_ems_placement_is_individual()` now answers the real question, "has the bulk pass already happened for this enrollment?", with two ways of being true:

| Condition | Situation |
|-----------|-----------|
| `transition_state == 'transitioned'` | Partial transition: that study is done, the centre still runs the outgoing course |
| `ems_course_id == company.current_course_id` | The course has already started, so the wizard is long past |

An enrollment for a course that has not started yet is still left to the wizard.

### A student with no enrollment blocks, but only where enrolling is the flow (D17)

D8 originally said the opposite: list them, never block, *"in July there is no way to tell a student moving to another school from one who enrolls late"*. That reasoning still holds for **withdrawing them automatically**, which the wizard still refuses to do. It does not hold for letting the run pass without anybody looking, because two things turned out to be irreversible:

- **Graduating them afterwards is impossible.** `graduation_wizard._is_last_course()` needs `main_group_id` to tell whether the student is in the last course, and step 4b has just taken it away.
- **Withdrawing them afterwards destroys the year record** (see the withdrawal note below).

Scoping is what makes it workable. `study.uses_enrollment_flow` — computed from the study having an active `sale.order.template` — separates the two worlds, and the 25-26 data shows why a blanket blocker would be unusable:

| Study | Uses the flow | Students | With no enrollment |
|-------|---------------|----------|--------------------|
| ESO | no | 493 | **478** |
| BTX | no | 112 | **107** |
| ASIX | yes | 55 | 28 |
| SMX | yes | 130 | 9 |

ESO and BTX do not enroll through `sale.order` at all; their continuity arrives with the September Esfer@ re-import, so a missing enrollment there is the expected state and stays a warning. In a vocational cycle it is a blocker.

**A draft or sent proposal is enough** to clear it: those students are `pending`, not `missing`. The blocker only fires when there is nothing at all.

### A frozen record is never rewritten from an empty group (D18)

`year_record.generate_for_students()` is idempotent on `(student_id, course_id)`: an existing record has its content **replaced**, subject lines unlinked and all. That is what makes it safe to call repeatedly — until the student has nothing left to read.

After a run, a student the transition did not place has no `main_group_id` (step 4b) and no live grade lines (step 8 deleted them, precisely because the record replaces them). Regenerating then rewrites the record from blanks:

```
before  group=CTWS2A  study="CTWS (2026)"  1 subject
after   group=False   study=False          0 subjects
```

And the record is the **only** surviving trace of that year — the grades it copied are gone. Only a backup restores it.

It is not hypothetical: `ems.withdrawal_wizard.action_apply()` regenerates on every exit, `_current_course()` stays on the outgoing course until the global flip, and the manual tells the operator to register the leavers **after** applying the transition. The window is exactly the summer.

The guard lives in `_generate_one()` rather than in the withdrawal wizard: three callers reach it (the transition, the withdrawal wizard and `freeze_on_leaving`), and a fourth would reintroduce the bug. An explicit `group=` argument still refreshes normally, which is what `freeze_on_leaving()` relies on.

### The preview only promises what THIS run will do (D19)

`_incoming_orders()` filters by `study_ids`, so a run places into its own studies and nothing else. A CFGM graduate moving up to a CFGS the centre has not transitioned yet is therefore **not** placed by the CFGM run — their destination study's run will do it — and step 4b detaches them in the meantime.

The preview showed the destination group anyway. On the first real SMX run all 22 `graduate_continue` lines promised ASIX1A / DAM1A / DAW1A / GA1C, and afterwards those 22 students had no group and no subject enrollments: correct behaviour, wrongly announced, on screen and in the audit CSV alike.

`_destination_of(order)` now returns the group only when the order's study is in scope **and** the order is confirmed; otherwise the column stays empty, which is what it already means for `graduate` and `missing`. A warning names them so the information is not lost:

> *N student(s) are heading to a study this run is not transitioning, so they are not placed here: they keep their enrollment and join their group when that study transitions. Meanwhile they are left with no group.*

Same defect class as `place_count` announcing 138 and moving 122 (D-pending): the preview is a promise, and every number in it has to be one the apply keeps.

### Conditional flip (step 5)

```mermaid
flowchart LR
    MARK["Mark study_ids as transitioned"] --> CHECK{"Any study left active?"}
    CHECK -- yes --> PARTIAL["Partial transition:<br/>no flip, list pending studies"]
    CHECK -- no --> FLIP["source.is_current = False<br/>target.is_current = True<br/>company.current_course_id = target<br/>target.is_enrollment_default = False<br/>every study back to active"]
```

`ems.course` enforces "only one current" and "only one enrollment default" through Python `@api.constrains`, not SQL, so the outgoing flag must be **cleared before** the incoming one is set.

### Latecomers

Students with no confirmed enrollment when their study transitions do **not** block. Step 0 archives their history, step 8 cleans their operational records and steps 3-4 skip them, so they end up as `student` with no group and `transition_status = 'missing'`. If they enroll later, `action_confirm()` → `_ems_admit_student()` → the now-active `transitioned` branch places them on their own.

Marking a genuine leaver as withdrawn stays **manual** (`ems.withdrawal_wizard`), by design: in July there is no way to tell a student moving to another school from one who simply enrolls late. The D8 listing exists precisely so that list is on screen when the transition finishes.

## Access control

| Group | Preview | Apply | Notes |
|-------|---------|-------|-------|
| `ems.group_academic_admin` | ✅ | ✅ | Sole owner of the wizard and of the Settings button (D1); already owns the grade-session state wizard the preview links to |
| `ems.group_secretary` | ❌ | ❌ | Manages enrollments, not the academic calendar |
| `ems.group_tutor` / teachers | ❌ | ❌ | — |
| Portal / families | ❌ | ❌ | — |

The wizard writes through `sudo()` where the reused helpers already do (`_ems_apply_destination_placement`, `_ems_clear_operational_records`): the operator is an academic admin, not necessarily a grades or attendance manager.

## Safeguards

- **Backup checkbox** — a single mandatory confirmation ("I have taken a backup") enables Apply.
- **Step 0 gates step 8** — the operational records are only deleted once the history has been frozen.
- **Idempotency** — every step can be re-run if the transition is interrupted, step 8 excepted.
- **Grade sessions must be deleted** (step 8) because `UNIQUE(group_id, subject_id, round)` carries no course; deleting them also resets `is_locked` naturally.
- **`has_graduated` is permanent** — never reset, and readonly on the contact form (D2).
