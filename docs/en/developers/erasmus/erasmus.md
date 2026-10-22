# Erasmus+ calls and applications

Issues #682 (umbrella), #683 (phase 1: calls and applications), #684 (phase 2: scoring and
interviews), #685 (phase 3: resolutions, claims and place offers), #686 (phase 4: the staff
call) and #687 (phase 5: mobility preparation). Design of the whole project: `plans/erasmus_portal.md`.
This page describes what is implemented.

The centre publishes a yearly Erasmus+ call for its vocational training students (CFGM/CFGS, any
year). Students apply from the portal (`/my/erasmus`), upload the documents the call asks for and
follow their application; the Erasmus team checks the requirements and the documents, asks for
corrections (subsanation) and admits or excludes each application, then scores the admitted ones (record average, interview,
languages, fewer opportunities, first mobility, conduct warnings) and ranks them per modality.
The resolutions, approved by the Erasmus coordinator, are published on the portal, claims are recorded, and the places are
offered to the selected and, when one is renounced, to the next reserve. The centre's vocational
training staff apply to their own call through the same portal page; a panel rates their mobility
plans (see "Staff call"). Once a place is accepted, the mobility is prepared in EMS: destination,
host entity, documents and checklist (see "Mobility preparation" at the end).

## Models

```mermaid
erDiagram
    ems_erasmus_call ||--o{ ems_erasmus_call_modality : "modality_ids"
    ems_erasmus_call ||--o{ ems_erasmus_call_document : "document_ids"
    ems_erasmus_call ||--o{ ems_erasmus_application : "application_ids"
    ems_erasmus_call_modality }o--o{ ems_level : "level_ids"
    ems_erasmus_application }o--|| res_partner : "partner_id (student)"
    ems_erasmus_application }o--|| ems_erasmus_call_modality : "modality_id"
    ems_erasmus_application ||--o{ ems_erasmus_application_document : "document_ids"
    ems_erasmus_application_document }o--|| ems_erasmus_call_document : "call_document_id"
    ems_erasmus_application_document }o--o{ ir_attachment : "attachment_ids (every version)"
```

| Model | Purpose |
|---|---|
| `ems.erasmus.call` | One call: who applies (`audience`: students or staff), course, dates (`date_open`, `date_close`, optional `subsanation_deadline`), the published call PDF, the text shown on the portal, state. |
| `ems.erasmus.call.modality` | A selection list with its own places (GM, GS): project (KA121-VET / KA131-HED), places, period, destinations, and the **levels** whose students compete in it. |
| `ems.erasmus.call.document` | A document the call asks for: required, optional or required for minors; confidential (only the Erasmus team sees it). |
| `ems.erasmus.application` | One student's application to one call (unique per call and student). |
| `ems.erasmus.application.document` | The files uploaded for one document of the call, with the team's review. |

The modalities and documents are copied when a call is duplicated, so next year's call starts
from this year's.

**Who can apply is decided by the modalities, not by code:** a student can apply when the level of
their main group is in one of the call's modalities, and that modality is the application's. Any
year of the cycle.

## Call states

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> published: Publish (needs a modality and a required document)
    published --> draft: Back to draft (no application submitted yet)
    published --> closed: Close applications
    closed --> [*]
```

A published call is shown on the portal to every student who can apply to it. Applications are
accepted only while it is published **and** the company's local time is between `date_open` and
`date_close` (`is_accepting`, computed with `ems.datetime_utils`, never the browser's clock).
Closing turns every application still in draft into *Not submitted*.

## Application states

```mermaid
stateDiagram-v2
    [*] --> draft: first save on the portal
    draft --> submitted: Submit (every required document uploaded)
    submitted --> submitted: edit and submit again (until date_close)
    draft --> not_submitted: call closed
    submitted --> subsanation: Request corrections (team)
    subsanation --> submitted: applicant uploads and submits again
    submitted --> admitted: Admit (team)
    submitted --> excluded: Exclude (team, with a reason)
    subsanation --> excluded: Exclude
    admitted --> submitted: Back to review
    excluded --> submitted: Back to review
```

- The state only changes through these actions (`write()` refuses a direct change).
- **Submit** checks that every required document has a file (documents required for minors only
  when the applicant is a minor) and emails a receipt listing the files
  (`email_template_erasmus_application_submitted`). Each new submission sends a new receipt.
- **Request corrections** needs at least one document marked *Needs changes* or a required
  document missing; it emails the list and the call's `subsanation_deadline`
  (`email_template_erasmus_application_subsanation`). Those lines get `correction_requested`;
  until the deadline the applicant can upload to them only (not change the answers, nor other
  documents) and submit again, which clears the flags.
- **Admit** needs both admission checks met and every required document *Valid*. **Exclude**
  needs the exclusion reason.
- Emails go only to the applicant's own address; a recipient without one is noted in the chatter.

## Documents

Every upload adds an attachment to the document line; earlier files are never removed, so every
version stays. A new upload puts the line back to *Pending review*. The team marks each line
*Valid* or *Needs changes* (with a comment the applicant sees on the portal).

## Admission checks

Separate from the documents, each stores result (*Pending*, *Met*, *Not met*), author and date,
stamped by `write()`:

| Check | Who records it |
|---|---|
| Requirements (enrolled in a modality's level, no previous Erasmus+ internship in this cycle, family authorization if minor) | Erasmus team |
| No serious sanction this course | **Head of Studies or Director only** (`ems.group_head_of_studies`, which the Director implies) |

A Head of Studies who is not in the Erasmus team can open the applications and write only the
sanction check and its note; any other field is refused.

## Portal (`controllers/portal_erasmus.py`)

| Route | What |
|---|---|
| `GET /my/erasmus` | Published calls the student can apply to and their own applications. |
| `GET /my/erasmus/call/<id>` | The application form for that call. |
| `POST /my/erasmus/call/<id>/save` | Save answers and uploads; with `submit`, submit too. |
| `GET /my/erasmus/call/<id>/rules` | Download the call PDF. |

The applicant is always `request.env.user.partner_id`: no partner or application id travels in a
form. The controller works with `sudo()` (portal users have no ACL on these models) and checks
eligibility and state itself. The portal home card appears only to students who have an
application or can apply to a published call (`res.partner._ems_erasmus_portal_visible`); families
do not see it.

## Access control

New group `ems.group_erasmus` ("Erasmus+ / Manager"), assigned through the roles *Erasmus
coordinator* (`ems.role_erasmus`) and *Erasmus mobility technician* (`ems.role_erasmus_technician`).
The coordinator's role gives `ems.group_erasmus_coordinator` ("Erasmus+ / Coordinator", implies
Manager), the only one besides `ems.group_academic_admin` that can publish a resolution (#686: the
coordinator alone approves them). The administrator is a member of both.

| Model | Erasmus team | Head of Studies / Director | Portal |
|---|---|---|---|
| `ems.erasmus.call`, `.modality`, `.document` | rwcu | r | via controller (sudo) |
| `ems.erasmus.application` | rwcu | rw (sanction check only, enforced in `write()`) | via controller |
| `ems.erasmus.application.document` | rwcu | r, **not confidential ones** (`ir.rule`) | via controller |

Menu *Erasmus+*: *Applications* (team, Head of Studies, Director) and *Calls* (team).

## Scoring (phase 2, #684)

Art. 12 of the call: up to 100 points, 50 to be eligible (`ems.erasmus.call.min_score`).

| | Criterion | Field(s) on the application | Who / how |
|---|---|---|---|
| A | Record average x 4 (max 40) | `grade_average`, `grade_line_ids` | **Computed by EMS at closing** (below). Never typed by hand. |
| B | Interview: general (max 20) + English (max 15) | `interview_general`, `interview_english` | Mean of the submitted interviews (below). |
| C | Language certificate (B1 2.5, B2 5, C1 7.5, C2 10) | `language_level` | Erasmus team. |
| D | Fewer opportunities (10 or 0) | `fewer_opportunities_check` | Erasmus team only (confidential). |
| E | First mobility (5 or 0) | `first_mobility` | Erasmus team. |
| F | -3 per conduct warning, max -9 | `strike_ids`, `strike_count` | **Frozen at closing** (below). |

`score_total` = A + B + C + D + E + F, with no floor at zero. Every manual criterion starts empty
(*pending*) and stores who set it and when (`<field>_user_id`, `<field>_date`, stamped by
`write()`). **A pending criterion is never zero:** `score_complete` stays false and the
application is left out of the ranking.

### Frozen at closing

*Close applications* (`ems.erasmus.call.action_close`) freezes, for every application that was
submitted (states *submitted*, *corrections requested*, *admitted*, *excluded*), the data the
score is based on (`_ems_freeze_scoring_data`, sets `scoring_frozen_date`). Later changes in
grades or warnings never change it.

**Record average (A)** - `_ems_grade_lines()`, every module of the applicant's current cycle
(the study of their main group), every year of it:

- Past years: the student's year records of that study (`ems.student.year_record`, not
  provisional; previous-centre records included). The final grade when there is one; otherwise
  the internal grade if some outcome was evaluated (or it was overridden).
- Current course: the live grade lines (`ems.grade_subject_line`, last round per module) of the
  study's modules: the computed grade when every weighted part is in, otherwise the provisional
  internal grade from the outcomes evaluated so far (`_internal_from_outcomes`: RA-weighted, whole
  number, 4 at most with a failed RA). A module with nothing evaluated is left out.
- Convalidated and recognised modules are left out; failed ones count with their grade.
- A module taken more than once counts once, with its most recent grade (the current course
  before any year record, then the latest course).
- Mean weighted by module hours (`ems.subject.total_hours`), two decimals. The modules used are
  copied to `grade_line_ids` (`ems.erasmus.application.grade`: module, course, grade, hours).

There is no manual average (decided 2026-10-22: no certificate of previous studies): a student
new to the centre is scored with this course's provisional grades. With no evaluated module at all,
A stays pending (`score_a_pending`) and the application has no complete score.

**Conduct warnings (F)** - the applicant's `ems.strike` records up to `date_close` whose group
belongs to the same study (`group_id.study_id`), copied to `strike_ids`/`strike_count`. EMS only
holds warnings since the course it started recording them.

### Ranking

Per modality, among *admitted* applications (`rank`, stored, recomputed when any application of
the call changes). The ranking of a modality is only computed when **every** admitted
application in it has a complete score; until then every rank in it is 0. Order: total, then the
tie-breaks of art. 12 - fewer opportunities, first mobility, English part of the interview,
record average - and finally the recorded draw (`draw_order`, lower first). Applications still
tied after all of it share the rank and get `needs_draw`. `is_eligible`: complete and total at
least `min_score`.

## Interviews (phase 2, #684)

```mermaid
erDiagram
    ems_erasmus_application ||--o{ ems_erasmus_interview : "interview_ids"
    ems_erasmus_interview }o--|| res_users : "evaluator_id"
    ems_erasmus_application ||--o{ ems_erasmus_application_grade : "grade_line_ids (frozen)"
    ems_erasmus_application }o--o{ ems_strike : "strike_ids (frozen)"
```

`ems.erasmus.interview` and the staff's `ems.erasmus.plan_rating` (phase 4) share the evaluator's
workflow through the abstract model `ems.erasmus.evaluation` (`models/erasmus/evaluation.py`):
evaluator, state, submit, reopen, lock at the review deadline or the provisional resolution, the
evaluator's activity, `ems.group_erasmus_evaluator` membership and the write guard (an evaluator
writes only the rubric `_ems_criteria` and their notes). Each model only adds its rubric.

The Erasmus team sets the interview's date and place on the application (`interview_date`,
`interview_place`) and assigns two evaluators (`ems.erasmus.interview`, one per evaluator, any
internal user). *Send interview call* emails the applicant the date and place
(`email_template_erasmus_interview_call`), at least 24 hours ahead (art. 11).

Each evaluator scores annex 4's rubric, 0-5 per criterion, all required to submit:

| Part | Criteria | Field |
|---|---|---|
| General (max 20) | motivation, maturity and autonomy, handling difficulties, adaptation and communication | `general_score` |
| English (max 15) | comprehension, fluency and interaction, accuracy, vocabulary and pronunciation | `english_score` |

```mermaid
stateDiagram-v2
    [*] --> draft: assigned (activity for the evaluator)
    draft --> submitted: Submit (every criterion scored)
    submitted --> draft: Reopen (evaluator until the call's interview_deadline; team any time)
```

- **Evaluators see only their own interviews** (record rule `evaluator_id = user`), never the
  other evaluator's, nor anything else of the application. Being assigned adds them to
  `ems.group_erasmus_evaluator` (*Erasmus+ > My evaluations*); losing every interview removes it.
- After the call's `interview_deadline` (label *Score correction deadline*, shared with the plan ratings) the evaluator can no longer change or reopen; the team
  can still reopen, writing a rectification note (`rectification_note`), posted in the chatter.
- The application's interview score is the mean of the submitted interviews, complete when every
  assigned interview is submitted and there are two of them, or one with a recorded reason
  (`single_interview_reason`, annex 4).
- A no-show (art. 11) is an exclusion: *Exclude* also works on admitted applications.

### Access (phase 2)

| | Erasmus team | Head of Studies / Director | Evaluator |
|---|---|---|---|
| Criteria C, E, draw | W | R | - |
| Criterion D | W | - | - |
| `ems.erasmus.interview` | rwcu | - | rw own (rubric, notes), no create/unlink |
| `ems.erasmus.application.grade` | r | r | - |

## Resolutions, claims and place offers (phase 3, #685)

```mermaid
erDiagram
    ems_erasmus_call ||--o{ ems_erasmus_resolution : "resolution_ids"
    ems_erasmus_resolution ||--o{ ems_erasmus_resolution_line : "line_ids (frozen)"
    ems_erasmus_resolution_line }o--|| ems_erasmus_application : "application_id"
    ems_erasmus_application ||--o{ ems_erasmus_offer : "offer_ids"
    ems_erasmus_application ||--o{ ems_erasmus_claim : "claim_ids"
    ems_erasmus_claim }o--o| ems_erasmus_resolution : "resolution_id (against)"
```

| Model | Purpose |
|---|---|
| `ems.erasmus.resolution` | A list the Erasmus team prepares and the Erasmus coordinator approves by publishing it: `admission`, `provisional`, `definitive` or `rectification`. |
| `ems.erasmus.resolution.line` | One applicant in it, frozen when the resolution was prepared: modality, rank, every criterion, total, result, masked identity document. |
| `ems.erasmus.offer` | A place offered to an applicant and their answer. |
| `ems.erasmus.offer.wizard` | Offer a free place to the next reserve (transient). |
| `ems.erasmus.claim` | A claim (after the provisional) or an appeal before the Director, recorded by the team. |

New fields on the call: `claims_deadline` (shown to applicants with the provisional result) and
`acceptance_deadline` (the deadline of the offers made when the definitive resolution is
published). New application states: `selected`, `reserve`, `not_selected`, `accepted`,
`renounced`; the ranking (`_compute_rank`) counts every one of them as admitted
(`RANKED_STATES`), so publishing results never changes a rank.

### Resolutions

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> draft: Prepare lines (freezes them, repeatable)
    draft --> published: Publish (Commission approval recorded)
    published --> [*]
```

Order, each one needing the previous one published (`PREVIOUS_KIND`): admission, provisional,
definitive, then any number of rectifications. Admission, provisional and definitive are published
once per call (`SINGLE_KINDS`).

**Preparing** (`action_prepare`, checked again on publishing) needs the call closed, every
application admitted or excluded, and - except for the admission list - every admitted one with a
complete score and no pending draw (*A missing value blocks*, never zero). It also needs every
applicant's identity document (`document_id`, or `passport_id`). The lines copy, for the admission
list, the admitted and the excluded; for the others, also every result (`RANKED_STATES`), with the
rank, the criteria and the result:

| Result | Rule (`_ems_ranking_result`) |
|---|---|
| `excluded` | The application is excluded; the reason goes on the line, only for the applicant. |
| `not_selected` | Not eligible: below the call's minimum score. |
| `selected` | Eligible and rank within the modality's `places`. |
| `reserve` | Eligible, after the places. |

**Publishing** is the coordinator's approval (`ems.group_erasmus_coordinator` or
`ems.group_academic_admin`, checked in `action_publish()`; who and when are `published_by_id` and
`publish_date`, shown on the list as the approval date). It needs the lines, notes for a
rectification and, for a definitive resolution or a rectification, a future `acceptance_deadline`.
Then:

- The resolution can never be changed or deleted (`write()`/`unlink()` refuse it; the lines have
  no write access at all). A correction is a new rectification.
- Every applicant on it gets their result by email (`email_template_erasmus_resolution_published`,
  rendered per line): the reason if excluded, the rank and total otherwise, the claims deadline
  with the provisional, the acceptance deadline if selected. Replies go to whoever published it,
  which is how claims arrive.
- The provisional resolution locks every interview of the call (`ems.erasmus.interview.is_locked`),
  as the review deadline does: after it, only a team rectification reopens one.
- A definitive resolution or a rectification sets each application's state to its result - except
  those that already answered an offer (`accepted`, `renounced`), which a rectification never
  undoes - and creates an offer for every selected one without an offer waiting or accepted, with
  the call's `acceptance_deadline`. No separate offer email: the result email already asks them to
  answer.

**Published lists never show names.** The portal list (`/my/erasmus/call/<id>/resolution/<id>`)
and the PDF for the centre's website (`ems.action_report_erasmus_resolution`, same template
`ems.erasmus_resolution_list`) show, per modality, the rank, the masked identity document
(`public_id`), the total and the result. `mask_document_id()` follows the Spanish data protection
agency's guidance for additional provision 7 of Organic Law 3/2018: DNI `***4567**`, NIE
`****4567*`, any other document its 4th to 7th characters.

### Place offers

```mermaid
stateDiagram-v2
    [*] --> pending: definitive published (selected) / wizard (reserve)
    pending --> accepted: applicant accepts on the portal
    pending --> renounced: applicant renounces on the portal
    pending --> expired: deadline passed (cron)
    pending --> cancelled: team withdraws it
```

- The applicant answers on the portal (`POST /my/erasmus/call/<id>/offer`, `answer=accept|renounce`,
  optional `reason`), before the deadline, which `_ems_answer` checks with the centre's clock. The
  application moves to `accepted` or `renounced`.
- No answer = renounced: the hourly cron `ems.ir_cron_erasmus_expire_offers`
  (`_cron_expire_offers`) marks the offer `expired` and the application `renounced`.
- **A free place is never offered on its own.** The modality computes `free_places` (places minus
  the offers waiting or accepted) and `next_reserve_id` (the best-ranked `reserve` application
  without one). The team clicks **Actions > Offer a free place** on the call; the wizard shows that
  proposal and asks for a new deadline; confirming creates the offer (`from_reserve`) and emails it
  (`email_template_erasmus_offer`).
- The team can withdraw an offer still waiting (*Withdraw offer*, e.g. made by mistake; state `cancelled`): the place becomes free again.

### Claims

A log, recorded by the team from the email that brought it (art. 14): application, the published
resolution it is against, kind (claim, appeal before the Director), received date, text, files,
response. **Resolve** needs the response and stamps the date. Upholding a claim means correcting the
application's data and publishing the next resolution (the definitive, or a rectification).

### Export to spreadsheet

**Actions > Export to spreadsheet** (the applications list, and the Actions dropdown of an
accepted application and of the call once its definitive resolution is published) downloads an
`.xlsx` with one row per applicant who **accepted** a place. An external tool imports it as is, so
the sheet (*Participantes*) and the headers are fixed Spanish strings, in this order, never
translated (`PARTICIPANT_HEADERS`):

| Column | Source |
|---|---|
| Nombre, Apellidos | `firstname`, `lastname` |
| DNI | `document_id`, else `passport_id` |
| Email, Teléfono, Dirección | personal `email`, `phone` (else `mobile`), the postal address on one line |
| Fecha de nacimiento | `birth_date`, as a real date cell (dd/mm/yyyy) |
| Nacionalidad | `citizenship_id` |
| Género | always empty: EMS keeps no gender for students |
| Ciclo formativo, Curso | the main group's study acronym and year (1 or 2) |
| Titular de la cuenta, Banco, BIC, IBAN | the first `res.partner.bank` (holder, else the student's name), IBAN without spaces |
| Tutor legal, Email del tutor legal, Teléfono del tutor legal | only for minors: **every** family contact (`_ems_family_contacts()`), joined with ", " in the same order in the three columns |

It carries personal and bank data: the file is built on the fly by `/ems/erasmus/participants`
(`controllers/erasmus_export.py`) and never stored, and only `ems.group_erasmus` can get it
(`_ems_participants()` refuses anyone else; the server action has that group only).

### Portal (phase 3)

| Route | What |
|---|---|
| `GET /my/erasmus/call/<id>` | Adds the place offer (accept / renounce) and a *Results* card: one entry per published resolution, with the applicant's own result, rank, total and every criterion. |
| `GET /my/erasmus/call/<id>/resolution/<id>` | The published list, without names. Only for applicants of that call, only published resolutions. |
| `GET /my/erasmus/call/<id>/resolution/<id>/pdf` | The same list as a PDF. |
| `POST /my/erasmus/call/<id>/offer` | Answer the logged-in user's own pending offer of that call. |

### Access (phase 3)

| Model | Erasmus team | Head of Studies / Director | Portal |
|---|---|---|---|
| `ems.erasmus.resolution` | rwcu (published: read only); publishing: coordinator only | r | via controller (sudo), published only |
| `ems.erasmus.resolution.line` | r (written by *Prepare lines* only); criterion D hidden from others | r | own lines and the list |
| `ems.erasmus.offer` | r + *Withdraw offer*; created by publishing and the wizard | r | answers their own |
| `ems.erasmus.claim` | rwcu | r | - |

Menus *Erasmus+ > Resolutions*, *Place offers* and *Claims*: team, Head of Studies, Director.

## Staff call (phase 4, #686)

A call's `audience` (*Applicants*) is `student` or `staff`; it cannot change once the call has
applications. The engine is the same (call, application, documents, resolutions, offers, claims);
what differs:

| | Students | Staff |
|---|---|---|
| Who sees the call on the portal | A student whose main group's level is in a modality | An internal user with an employee file (`res.partner._ems_erasmus_employee`) |
| Modality | Computed from the level when applying; required to publish | Not needed to publish (the places may change): required before preparing the provisional resolution; the team assigns each selected person's project and period |
| Documents | Configured per call | The four of art. 8 added on their own (`_ems_staff_documents`, on create and on the `audience` onchange), the mobility plan `panel_visible` |
| Admission checks | Requirements + serious sanctions (Head of Studies) | Requirements only |
| Scoring | Art. 12 (A-F), A and F frozen at closing | Art. 11 of the staff call (1-6): the panel, what the applicant declares (last mobility, seniority, language) and the merits the team records |
| Ranking | Per modality | One list for the whole call |
| Places | Per modality | The sum of every modality, offered as one pool |
| Identity document of the lists | `res.partner.document_id` / `passport_id` | `hr.employee.identification_id` / `passport_id` (`_ems_identity_document`) |
| Minimum score | 50 | 0 (set by the onchange of `audience`) |

```mermaid
erDiagram
    ems_erasmus_call ||--o{ ems_erasmus_call_panel : "panel_ids"
    ems_erasmus_call_panel }o--|| res_users : "user_id"
    ems_erasmus_application }o--o| hr_employee : "employee_id"
    ems_erasmus_application ||--o{ ems_erasmus_plan_rating : "plan_rating_ids"
    ems_erasmus_plan_rating }o--|| res_users : "panel_member_id"
    ems_erasmus_plan_rating }o--o| res_users : "evaluator_id (the member, empty if abstaining)"
    ems_erasmus_application ||--o{ ems_erasmus_application_merit : "merit_ids"
```

| Model | Purpose |
|---|---|
| `ems.erasmus.call.panel` | A panel member of a staff call (user, post), copied when the call is duplicated. |
| `ems.erasmus.plan_rating` | One panel member's rating of one application's mobility plan (annex 2: `relevance`, `transfer`, 0 / 0.5 / 1 each). Unique per (application, panel member). Inherits `ems.erasmus.evaluation`. |
| `ems.erasmus.application.merit` | A merit of criteria 3 (centre project: collaboration 0.5, coordination 1) or 6 (internationalisation activity 0.5), with its justification. |

### Application form

The portal shows the staff form when `audience == 'staff'` (`ANSWER_FIELDS['staff']`): activity
(`staff_activity`), host entity or course, "host not found yet", destination, preferred dates,
last staff mobility and date at the centre (below), centre projects, interest in accompanying
students, support needs
(confidential: `groups` Erasmus team and administrator), the declared language certificate
(`declared_language_level`), image consent, notes. The controller saves only the answers of the call's audience;
`_ems_portal_save` refuses an activity outside the selection. `employee_id` is set when the
application is created. `is_minor` is always false for staff.

### Panel and plan ratings

**Actions > Send plans to the panel** (`action_send_to_panel`, closed staff call only) creates one
rating per admitted application and panel member still without one, so it can be repeated after
admitting more. A panel member who applied to the call (`_ems_candidate_partners`: any application
past draft) gets an abstention instead: no `evaluator_id`, reason *Candidate in this call* (art. 10).
For any other conflict of interest the team writes the `abstention_reason`, which clears the
evaluator (`write`); clearing the reason gives the rating back to the member. There are no
substitutes (decided with the coordinator 2026-10-22): `_check_evaluator` only accepts the panel
member, or nobody, and never a candidate of the call.

`plan_score` is the mean of the submitted ratings that are not abstentions; `plan_complete` needs
every non-abstaining rating submitted and a rating for every panel member (`call.panel_ids`). A
pending rating leaves the score incomplete.

**What a panel member sees:** only their ratings (record rule `evaluator_id = user`), and, so they
can open the plan, the application document lines whose call document is `panel_visible` and not
confidential, of the applications they rate (record rule on `ems.erasmus.application.document`,
read only); the rating shows those files (`plan_attachment_ids`). Nothing else of the application.

### Criteria (art. 11 of the staff call)

| | Criterion | Field(s) | Points |
|---|---|---|---|
| 1 | Mobility plan | `plan_score` → `score_plan` | max 2 |
| 2 | Last staff mobility | `last_staff_mobility` (team correction) else `declared_last_staff_mobility` → `score_last_mobility` | never / older 1.5, two courses ago 0.5, recent 0 |
| 3 | Centre projects | `merit_ids` (project kinds) → `score_projects` | sum, max 1.5 |
| 4 | Languages | `language_level` (checked by the team) else `declared_language_level` (the applicant's) → `score_staff_language` | B2 1, C1 1.5, C2 2 (B1 0) |
| 5 | Seniority | `seniority` (team correction) else `declared_seniority` → `score_seniority` | < 1 year 0, 1-2 1, 2-5 1.5, ≥ 5 2 |
| 6 | Internationalisation | `merit_ids` (internationalisation) → `score_internationalisation` | sum, max 1 |

**Declared values** (`_compute_declared_staff_bands`): the applicant gives the month of their last
Erasmus+ staff mobility from the centre (`declared_last_mobility_date`, or
`declared_never_staff_mobility`) and the month they joined the centre (`declared_centre_start_date`);
both are required to submit. The mobility belongs to the course starting the 1 September before it
and is compared with the call's course; seniority counts whole months up to the call's closing date
(company time). The portal sends them as `<input type="month">` values (`YYYY-MM`, stored as the 1st).

`score_complete` needs the plan complete, criteria 2 and 5 (declared or corrected) and
`merits_checked` (stamped like every manual criterion, so "no merits" is an explicit answer).
Criterion 4 never blocks: no declared certificate counts as none (`_ems_staff_language_level`).

**Ranking** (`_compute_rank`, `_ems_rank_key`): one list per call, once every admitted application
is complete. Tie-breaks (decided with the coordinator 2026-10-22): plan score, seniority, then the
recorded draw. Result
(`_ems_ranking_result`): selected within the sum of every modality's places, reserve after them.

### Resolutions, offers and export

- The resolution lines also freeze the staff criteria (`STAFF_SCORE_FIELDS`). The published list
  (`_ems_list_groups`) is a single table for a staff call, still without names.
- Offers of a staff call have no modality until the team assigns one; `free_places` and
  `next_reserve_id` live on the call (`_ems_free_places`, `_ems_next_reserve`), and the offer
  wizard asks for no modality.
- **Export to spreadsheet** (`_ems_staff_participant_row`) reads the employee file: name from the
  user's contact, identity document, private email (else work), private phone (else mobile),
  private address, birthday, nationality (`country_id`) and `bank_account_id`. Género, Ciclo
  formativo, Curso and the legal guardian columns stay empty.
- One place per person: the unique (call, applicant) constraint gives it.

### Access (phase 4)

| Model | Erasmus team | Head of Studies / Director | Panel member (`ems.group_erasmus_evaluator`) |
|---|---|---|---|
| `ems.erasmus.call.panel` | rwcu | r | - |
| `ems.erasmus.plan_rating` | rwcu | - (unless in the panel) | rw own (rubric, notes) |
| `ems.erasmus.application.merit` | rwcu | r | - |
| `ems.erasmus.application.document` | rwcu | r, not confidential | r, `panel_visible` lines of the plans they rate |

Menus *Erasmus+ > Plan ratings* (team) and *My plan ratings* (evaluators).

## Mobility preparation (phase 5, #687)

Accepting a place offer (`ems.erasmus.offer.action_accept`) creates the participant's **mobility**.
The application keeps the selection; the mobility holds everything after it.

```mermaid
erDiagram
    ems_erasmus_call ||--o{ ems_erasmus_destination : "destination_ids (students)"
    ems_erasmus_destination }o--|| ems_erasmus_call_modality : "modality_id"
    ems_erasmus_call ||--o{ ems_erasmus_call_document : "preparation_document_ids (stage preparation / return)"
    ems_erasmus_call ||--o{ ems_erasmus_call_task : "task_ids (checklist)"
    ems_erasmus_application ||--o| ems_erasmus_mobility : "mobility_ids"
    ems_erasmus_mobility }o--o| ems_erasmus_destination : "destination_id"
    ems_erasmus_mobility }o--o| res_partner : "host_partner_id, host_contact_id"
    ems_erasmus_mobility ||--o{ ems_erasmus_application_document : "document_ids"
    ems_erasmus_mobility ||--o{ ems_erasmus_mobility_task : "task_ids"
```

| Model | Purpose |
|---|---|
| `ems.erasmus.destination` | A destination of a students' call, in one modality: country, city, places, the levels it suits (empty: all), dates, host entities, notes. `free_places` = places minus its mobilities not cancelled. Not copied with the call (destinations change every year). |
| `ems.erasmus.mobility` | One per accepted application (`unique(application_id)`): destination, the proposal and its decision, country, city, host entity (a company contact) and its contact person, dates, documents and checklist. |
| `ems.erasmus.call.task` | A checklist step of the call (not a document): when (`stage`: before leaving / on return), only for some modalities. |
| `ems.erasmus.mobility.task` | That step for one mobility, ticked by the team (who and when stamped). |

**Documents.** `ems.erasmus.call.document` has a `stage`: `application` (phases 1-4), `preparation`
or `return`. The call's `document_ids` shows only the application ones (One2many domain), so the
application's lines and every earlier rule are unchanged; `preparation_document_ids` holds the
other two. Each one can be limited to some modalities (`modality_ids`) and says who signs it
outside EMS (`sign_participant`, `sign_guardian` for minors, `sign_centre`, `sign_host`, shown as
`signers`). The mobility's lines are `ems.erasmus.application.document` records with `mobility_id`
set: same review, every version kept, a new upload goes back to review. A new call gets default
documents and steps per audience (`_ems_preparation_documents`, `_ems_preparation_tasks`: art. 17
of the students' call, art. 15 of the staff call), editable. `_ems_sync_requirements()` adds what
the mobility's modality needs and is missing, never removing a line: on creation, when a staff
member's modality is assigned (`application.write`), and from *Update documents and checklist*.

New call fields: `choice_turn_hours` (default 72), `choice_open`, `preparation_days` (default 30;
the mobility's `preparation_deadline` = start date - days, art. 17: "at least a month before") and
`return_days` (default 30; `return_deadline` = end date + days). There is no identity document among
the defaults: EMS already holds it on the contact or employee file.

### Mobility states

```mermaid
stateDiagram-v2
    [*] --> choosing: offer accepted
    choosing --> preparing: destination chosen / one destination / proposal validated
    choosing --> preparing: Set the agreed destination (team)
    choosing --> cancelled: renounced / cancelled
    preparing --> done: Close (return documents and steps complete)
    preparing --> cancelled: renounced / cancelled by the team (with a reason)
```

The state changes only through the actions. Cancelling frees the place (`_ems_cancel`): the
accepted offer and the application become `renounced`; the place is then offered with the existing
wizard, never on its own.

### Destination choice (students, art. 15)

`call.action_open_destination_choice()` (after the definitive resolution, with destinations) sets
`choice_open` and runs `_ems_advance_choice()`, which runs again after every choice, proposal,
rejection and cancellation. Per modality:

- **One destination:** every mobility still choosing that it suits is assigned directly.
- **Several:** if no turn is open, the best-ranked mobility still choosing (`_ems_choosing`: not
  waiting for an own proposal) gets `turn_deadline` = now + `choice_turn_hours` and the email
  `email_template_erasmus_choice_turn`. One turn at a time.
- On the portal they choose among `_ems_choices()` (free and suitable for their `level_id`, the
  level when the place was accepted). If none suits them, they talk to the Erasmus team (art. 15),
  which agrees an alternative (their own find, or a destination through an intermediary
  organisation), writes it on the mobility and clicks *Set the agreed destination*
  (`action_agree_destination`, needs the country).
- No answer: the hourly cron `ems.ir_cron_erasmus_expire_turns` (`_cron_expire_turns`) clears the
  turn and sets `turn_missed`; the place is kept and the next one gets the turn. Once nobody in the
  modality is left to choose in order, every mobility that missed its turn gets `free_choice` (and
  the turn email, without a deadline) and can choose any destination still free.

Assigning copies country, city and dates from the destination and emails
`email_template_erasmus_mobility_assigned`.

### Proposals and their decision

The same fields serve a student's **own destination** and a staff member's **activity**:
`proposal_*`, `proposal_state` (`pending` / `validated` / `rejected`), `decision_note`,
`decided_by_id`, `decision_date`.

| | Student | Staff |
|---|---|---|
| Sent | From the portal while choosing, with the host's written commitment (required) | Copied from the application when the mobility is created; again from the portal only after a rejection |
| Validated by (`_ems_can_validate`) | Erasmus team | **Direction**: the Director or a Head of Studies (`ems.group_head_of_studies`, which the Director implies); the Erasmus team cannot |
| Validated | Preparing, country and city from the proposal | Same |
| Rejected (needs `decision_note`) | Back to choosing the centre's destinations | Proposes another activity on the portal |

A pending proposal schedules a to-do (`mail.activity`) for every validator, marked done on the
decision; a rejection emails `email_template_erasmus_proposal_rejected`. The administrator can
always validate.

### Preparation, return and closing

- *Notify pending documents* emails `email_template_erasmus_mobility_documents` with the lines
  missing or needing changes.
- `preparation_complete` / `return_complete`: every required line of the stage valid and every
  step done. **Close** needs `return_complete`.
- **Cancel** (team) needs `cancel_reason`; the participant can renounce from the portal.
- **Staff absence for training** (`_ems_sync_training_leave`, run when the dates or the state
  change): once a staff mobility is preparing with both dates, EMS files an `hr.leave` of
  `ems.leave_type_training` for those whole days (`leave_id`), submitted, so it follows the usual
  approval of that employee's absences. While it is not decided it follows the dates and is
  withdrawn (unlinked) if the mobility is cancelled; once decided, a change or a cancellation only
  leaves a note on the mobility for the team to correct it by hand.

### Graduates

The course transition (`_apply_graduates`) does not retire a graduate with an open mobility
(`res.partner._ems_erasmus_open_mobility`): it is reported and keeps the portal. When the mobility
is closed or cancelled, `_ems_erasmus_release_graduate()` retires an active alumnus with no open
mobility left, as the transition would have (`res.partner._ems_retire_graduate`, shared with it).

### Portal (phase 5)

`POST /my/erasmus/call/<id>/mobility/<step>` acts on the logged-in user's own mobility of that
call: `choose` (`destination_id`), `propose` (the `proposal_*` fields and
`proposal_files`), `upload` (`document_<call document id>`) and `renounce` (`reason`). The call page
shows the *Your mobility* card (`ems.portal_erasmus_mobility`).

### Access (phase 5)

| Model | Erasmus team | Head of Studies | Director | Portal |
|---|---|---|---|---|
| `ems.erasmus.destination`, `.call.task`, `.mobility.task` | rwcu | r | r | via controller |
| `ems.erasmus.mobility` | rwcu | r + `decision_note` and validating staff proposals (`write()` guard) | same as Head of Studies | via controller |

Menu *Erasmus+ > Mobilities* (team, Head of Studies, Director), with a *Proposal to validate*
filter.
