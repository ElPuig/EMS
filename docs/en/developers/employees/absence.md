# Staff absences (`hr_holidays` EMS extension)

Replaces the Google Form + Sheet + Apps Script application the centre used to manage staff
absences, with three parallel copies (VET/CCFF, ESO/BTX, ASP) that differed only in who approved
them. EMS builds on Odoo's native `hr_holidays` rather than a bespoke model: the request
workflow, approval, hour computation against the employee's `resource.calendar`, attachments,
calendar event and reporting all come from the framework.

> **Current scope:** the `hr_holidays` dependency, the absence type catalogue, the derived
> approver, the access model (cycle 1), and the EMS request fields, hour rules and health
> allowance (cycle 2). The guard-duty integration and the notification rework land in later
> cycles — see `plans/absence_management.md`.

## Who approves: derived, never configured

The Google sheet held a `Config` tab mapping each department to its "Gestor d'absencies". EMS
already models that relationship: the approver is the **Area Manager of the employee's top-level
department**, which the role hierarchy keeps current on its own (see
[role_hierarchy.md](role_hierarchy.md) and [department.md](department.md)).

```mermaid
flowchart TD
    E["hr.employee"] --> D["department_id"]
    D --> W{"is_top_level?"}
    W -- no --> P["parent_id"]
    P --> W
    W -- yes --> M["manager_id (Area Manager)"]
    M --> LM["employee.leave_manager_id"]
    LM --> A["Approves hr.leave<br/>(leave_validation_type = 'manager')"]
```

| Top-level department | `top_level_role` | EMS role | Approves absences for |
|---|---|---|---|
| VET | `dhos` | Deputy head of studies | Vocational training staff |
| ESO / BTX | `hos` | Head of studies | Secondary and baccalaureate staff |
| ASP | `secretary` | Secretary | Administrative and services staff |

`hr.department._top_level_department()` walks `parent_id` up to the `is_top_level` ancestor.
`ems_employee_base._compute_leave_manager()` overrides the native compute — which follows
`parent_id.user_id`, i.e. the Seminar Chief or Department Chief, the wrong person here — and
resolves that department's `manager_id.user_id` instead. Like `_compute_parent_id()`, it depends
only on `department_id` and is re-triggered explicitly from
`ems_department._cascade_department_heads()`, so replacing an Area Manager re-points every
affected employee in one write.

The field stays `readonly=False` (a stored editable compute, as Odoo defines it), so an
administrator can override a single employee's approver by hand; the override holds until the
next recompute — that employee changing department, or their Area Manager being replaced.

**The approver is a `res.users`, not an `hr.employee`.** An Area Manager with no user account
therefore leaves every employee in their area with an empty `leave_manager_id`, which Odoo
degrades to "approved by an officer" — the Head of Studies chain — rather than failing. Worth
checking when an area's absences appear to have no approver.

## Absence type catalogue

`data/cat/hr.leave.type.csv` — Catalonia-specific, because the catalogue follows the Generalitat's
own staff-absence regulations (ATRI is its personnel portal), same rationale as
`data/cat/hr.job.csv`.

**The nine names are the original form's own option texts, verbatim.** They are long
sentences rather than short labels because several carry the legal wording the employee is
declaring when they pick one ("I was absent from my workplace for health reasons, a
circumstance I reported immediately to the centre's director"). English is the source language;
`i18n/ca_ES.po` holds the Catalan exactly as the Google form had it, character for character.

**No type is preselected.** Odoo ticks the first available one on a new request; here the type
is the legal ground the employee is declaring, so it has to be a deliberate choice. Turned off
through hr_holidays' own `holiday_status_display_name` context switch rather than by picking the
default apart afterwards.

**The form shows them as a radio list, not a dropdown** (`widget="radio"` on
`holiday_status_id`, which Odoo supports on many2one fields), exactly as the Google form did.
That is not decoration: several of the nine options *are* the legal wording the employee is
declaring by choosing them, so they have to be readable in full at the moment of choosing.

**Everywhere else shows a short name.** `hr.leave.type.ems_short_name` is the text up to the
colon - `Salut`, `ATRI`, `Assistència a Consulta mèdica` - which is what the Apps Script itself
displayed in the calendar and its emails (`type.substring(0, colonIndex)`). The absence list
shows it through the related `hr.leave.ems_type_short_name`, and `hr.leave._compute_display_name`
substitutes it into whatever Odoo builds, the calendar chip above all. Deliberately *not* done
by shortening the type's own `display_name`: the radio widget reads exactly that field, so
shortening it there would empty out the one place the full text matters. `ems_short_name` is not
stored, because `name` is translatable and a stored copy would freeze one language.

Odoo's own five types (`Paid Time Off`, `Sick Time Off`, `Unpaid`, `Compensatory Days`, and
`Extra Hours` from `hr_holidays_attendance`) are archived by
`hr.leave.type._ems_deactivate_native_types()`. That has to be code, not a data file: all five
carry `ir_model_data.noupdate = True`, and it is that stored flag - not the loading file's own
context - that decides whether an existing record is written.

| Type | Supporting document | Counts in monthly report | Notes |
|---|---|---|---|
| Baixa laboral | yes | **no** | Formal sick leave; excluded from the monthly hours report (2 of 53 real rows counted) |
| Salut | no | yes | Self-declared health absence; the only type consuming the 15 h/course allowance |
| Assistència a consulta mèdica | yes | yes | |
| Prova mèdica invasiva | yes | yes | Whole day by default |
| Flexibilitat per menstruació o climateri | yes | yes | Its own legal cap (8 h/month) is out of scope |
| Formació | yes | yes | Courses, Erasmus+ |
| Absència justificada | yes | yes | |
| Encàrrec de serveis | yes | yes | Field trips, official travel |
| ATRI | no | yes | Filed by the employee on the Generalitat portal, where it is justified; Direction confirms it |

All nine share `request_unit = 'hour'`, `requires_allocation = 'no'` (the 15 h cap warns, it
never blocks — see the plan) and `leave_validation_type = 'manager'`, which routes approval to
`leave_manager_id` above.

Since issue #440, `hr.employee.attendance_manager_id` (`hr_attendance`'s own approver field,
unrelated to leave requests) is a stored compute that always mirrors this same
`leave_manager_id` — see [My Profile restructuring](user_profile.md) for why and how.

## The request: what EMS adds to `hr.leave`

| Field | Seeded from | Who edits it |
|---|---|---|
| `ems_full_day` "Whole day" | `hr.leave.type.ems_full_day_default` | Employee, while the request is unapproved |
| `ems_counts_hours` "Adds the hours to the monthly report" | `hr.leave.type.ems_counts_hours` | The approver only |
| `ems_needs_atri` "Filed through ATRI" | `hr.leave.type.ems_needs_atri` | Nobody: not shown on the form, only read by an invisible node that shows the ATRI portal notice |
| `ems_responsible_declaration` | — | Employee; required when the type demands it |
| `ems_document_state` "Supporting document status" | set when the Head acknowledges the request | The Head's and Direction's buttons, and the employee attaching the document; never written directly by the employee |
| `ems_document_reminder_date` / `ems_document_escalated` | — | The reminder scheduled action only |
| `ems_direction_state` "Direction status" | — | Read by everyone, set by Direction only (its own buttons); hidden until the request exists |
| `ems_head_state` "Head status" | computed from `state` and `ems_document_state` | read-only |
| `ems_status` "Overall status" | computed | read-only |
| `ems_health_hours_used` / `ems_health_allowance_exceeded` | computed | read-only |

The first three are **stored editable computes**: picking an absence type proposes a value and
any later manual change survives. That is deliberate, and it reproduces what the Apps Script did
— it ticked `Suma Hores?` on submit and left the manager free to correct it afterwards, which
they do, because employees miscategorise their own absences.

The status fields are the steps of the approval and where the request stands between them - see
[The approval, step by step](#the-approval-step-by-step) below.

**The employee never picks the ATRI flag or the monthly-report flag.** Both are derived from the
absence type. The monthly-report flag is shown to the approver, who can override it per request.
The ATRI flag is shown to nobody: its only use is the ATRI portal notice on the form, and when the
employee chose the wrong type the approver changes the type itself, which recomputes both. That
is also why `holiday_status_id` stays editable for the approver after approval, overriding
Odoo's own readonly (`is_absence_manager` drives that).

## The approval, step by step

Every absence goes through the **Head** - the Area Manager who is the employee's
`leave_manager_id` (see above) - and then **Direction** (`ems.group_director`), always in that
order. The Head's side has two steps whenever the absence type requires a supporting document
(`hr.leave.type.support_document`): the document often only exists after the absence, so the
Head first **acknowledges** the request ("Received: pending documentation") and **validates** the
document later, once the employee has attached it. Direction reviews last (for ATRI absences,
that the request was really filed on the Generalitat's portal).

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> AwaitingDocumentation: Head - received (type requires a document)
    Pending --> PendingValidation: Head - received (document already attached)
    Pending --> PendingDirection: Head - validate (type requires no document)
    AwaitingDocumentation --> PendingValidation: employee attaches the document
    PendingValidation --> PendingDirection: Head - validate documentation
    PendingValidation --> AwaitingDocumentation: Head - documentation insufficient
    PendingDirection --> AwaitingDocumentation: Direction - documentation insufficient
    PendingDirection --> Approved: Direction done
    Pending --> Refused: Head or Direction refuses
    AwaitingDocumentation --> Refused
    PendingValidation --> Refused
    PendingDirection --> Refused
    Pending --> Cancelled: employee cancels
```

Which types require a document is `support_document` in `data/cat/hr.leave.type.csv`: every one
except "Health" (self-declared) and ATRI (justified on the Generalitat's portal). Being `data/cat/`
(`noupdate=False`), the CSV is the source of truth: a change made from the type's own form is
reverted by the next upgrade.

Four fields, three of them a column of the managers' list. The employee sees only the overall
status: their own list (`hr_leave_view_tree_my`) hides the Head's and Direction's columns
(`column_invisible`, so the fields stay loaded), and the form hides the three step badges unless
the reader `is_absence_manager` or `is_absence_direction` - the status bar says it all.

| Field | Values | Source |
|---|---|---|
| `ems_document_state` "Supporting document status" | Not required / Awaiting documentation / Pending validation / Validated | Set by `action_approve()` from the type and the attachments; moved by attaching the document and by the buttons |
| `ems_head_state` "Head status" | Pending / Awaiting documentation / Pending validation / Approved / Refused | Stored compute over Odoo's `state` and `ems_document_state` |
| `ems_direction_state` "Direction status" | Pending / Done / Refused | Direction's buttons |
| `ems_status` "Overall status" | Pending / Awaiting documentation / Pending validation / Pending Direction / Approved / Refused / Cancelled | Stored compute over the other two and `state` |

`ems_status` is the Head's column until the Head is done (Pending, Awaiting documentation,
Pending validation), then Pending Direction until Direction marks it done, then Approved. Plus
**Refused** whenever `state == 'refuse'`, whoever refused, and **Cancelled** when the employee
cancelled their own request.

**Odoo's own `state` is left exactly as it is, and stays the Head's decision.** No values are
added to it: `hr_holidays` hangs everything off it - `validate` creates the
`resource.calendar.leaves` that the hour balance, the auto check-out and the guard duty board all
read, and `validate1` already means a second approval with a fixed order (manager first, then an
officer), which is not this. So **an absence takes effect when the Head acknowledges it** (both
"Received: pending documentation" and "Validate" are Odoo's own `action_approve()`, only labelled
differently); neither the document nor Direction's review holds back the calendar. The status
columns are built on top of it.

`ems_head_state` follows `state` (`confirm` → Pending, `validate`/`validate1` → the document's
stage while it is awaited or submitted, Approved otherwise, `refuse` → Refused), with two
exceptions where it keeps the value it had: a refusal that was Direction's, and the employee
cancelling. Direction's refusal is recognised because `action_ems_direction_refuse()` sets
`ems_direction_state = 'refused'` *before* calling the native `action_refuse()`, and the compute
reads it without depending on it (the Head's column must not move when only Direction acts).

**The Head's buttons.** On a pending request, Odoo's Approve is relabelled "Validate" for a type
requiring no document, and a second button on the same `action_approve` reads "Received: pending
documentation" for the others (form header, list row as an inbox icon, kanban). `action_approve()`
then sets `ems_document_state`: `not_required`, `submitted` when a file was already attached with
the request, or `awaiting`. Once the document is attached, `action_ems_document_validate` (form
header, list row) moves it to `validated`; `action_ems_document_insufficient` sends it back to
`awaiting`, with a note to the employee. Who counts as the Head is `is_absence_head`: the
employee's `leave_manager_id`, or an officer other than Direction - the same line
`_compute_can_approve()` draws.

**Attaching the document is the employee's step, with no button.** `hr.leave.write()` hands a
request from `awaiting` to `submitted` as soon as its attachment fields are written and it has an
attachment (`_ems_submit_document()`, sudo: the employee may cause the change but never write
`ems_document_state` themselves, which `write()` and `create()` refuse). A file dropped into the
chatter's own attachment box is not a write on the request and does not count - the form's
"Supporting document" field is the place.

**Direction's buttons** are `action_ems_direction_done` (only while Pending Direction:
`UserError` otherwise), `_reset` (back to Pending), `_refuse`, and the same
`action_ems_document_insufficient` as the Head, which sends a request Direction is reviewing back
to the employee. All through plain `write()`s: the existing guard in `hr.leave.write()` is what
keeps them Direction's, for these buttons and any other way in. They sit in the form header and,
as icons with their label as tooltip, beside the Direction column in the list; they are hidden in
the employee's own list.

**One activity per step.** `_ems_update_activities()`, called from `write()` whenever `state`,
`ems_document_state` or `ems_direction_state` changes, keeps exactly one EMS activity open on the
request, for whoever acts next: "Attach the absence's supporting document" for the employee (due
the day after the absence, so it turns overdue on its own), "Validate the absence's supporting
document" for the Head (`_get_responsible_for_approval()`), "Direction review of the absence" for
the company's Director. The previous step's is marked done; a refused or cancelled request keeps
none. The four activity types live in `data/main/mail.activity.type.csv`.

**Reminders.** The daily scheduled action `ems.ir_cron_absence_document_reminder` runs
`_cron_ems_document_reminder()` over every request still awaiting its document whose last day is
past (`ems.datetime_utils.get_local_today()`, the centre's timezone). It posts a note to the
employee every `ems_absence_document_reminder_days` days (default 1: every day;
`ems_document_reminder_date` keeps it to once per interval) and, once
`ems_absence_document_escalation_days` calendar days have passed since the absence (default 3),
a note and an overdue activity to the Head, once (`ems_document_escalated`). Both are company
settings under Settings > Staff Absence Settings, with the same fallback-to-default helpers as the
health allowance. The notes are `mail.mt_note` addressed to their recipients only, so the
department chief and Direction following the request are not sent every reminder. Sending the
request back as insufficient resets both markers.

**Upgrade.** `migrations/18.0.0.30.2/post-migrate.py` marks every request the Head had already
approved as `validated` (that is what the approval meant until then), turns Direction's former
"Missing document" into "Awaiting documentation" (Direction back to Pending), recomputes both
stored status columns, and gives the employee the upload activity on those requests.

**A decision taken from the form goes back to the list.** The form is `js_class="ems_absence_form"`
(`static/src/js/backend/absence_form.js`): after any of the Head's or Direction's decision
buttons, its `afterExecuteActionButton()` calls the web client's own `historyBack()` - the same
call Odoo makes after deleting a record. That hook runs whether or not the button raised, so
success is read from the record instead: `state`, `ems_document_state` and `ems_direction_state` are captured before
the click and compared after the reload, and only a change goes back. A refused confirmation or an
error leaves the reader on the form, as does a form opened on its own (no breadcrumb to return
to, where `historyBack()` would load the home screen). Refusing is final - the whole request,
exactly like the Head's refusal - and confirms first.

**Direction does not approve on the Head's behalf.** Direction holds the officer group through
Head of Studies, so Odoo would offer it Approve/Refuse on every request - right beside the Head's
column, where clicking decides for the Head instead of recording Direction's review.
`_compute_can_approve()` is overridden to be `False` for `ems.group_director` except where the
Director is the employee's `leave_manager_id` (an Area Manager's own absence). The list and kanban
Approve/Refuse buttons, which natively look at `state` only, now also require `can_approve`; the
form's already did. It is a screen rule only: server-side, Direction keeps its officer rights.

**"Waiting For Me".** Odoo's own two filters only know the acknowledgement (`state = 'confirm'`),
so both are re-scoped to the Head's two steps (`ems_status` Pending or Pending validation): the
approver's `waiting_for_me` and the officers' `waiting_for_me_manager`. Direction's own
(`ems_waiting_for_direction`, `groups="ems.group_director"`) lists what is Pending Direction, plus
the Head's two steps on the requests Direction handles as the Head (`leave_manager_id = uid`).
The officers' filter, which Direction would otherwise get and which lists the Head's pending work,
is hidden from it (`groups="hr_holidays.group_hr_holidays_user,!ems.group_director"`). The
Management action (`hr_leave_action_action_approve_department`) opens with all three
`search_default_`s set; a filter the reader's groups hide is simply not applied, so each role
lands on its own. "My pending supporting documents" (`ems_my_pending_documents`) is the
employee's. The search panel on the left filters on `ems_status` instead of `state`.

Covered by `TestAbsenceRequest` (the whole sequence, each type family's first step, the document
filed with the request, attaching it, insufficient from the Head and from Direction, Direction
blocked before its turn, the activities, the reminders and the escalation with their settings,
refusals and resets, `can_approve`/`is_absence_head` for Director / Head of Studies /
Director-as-approver, who gets subscribed, and the filters' domains) and by three tours:
`ems_absence_direction_review` (Direction's default list, sending a document back from the row,
validating from the header, kanban), `ems_absence_head_approval` (Head of Studies acknowledging
from the row, validating a document from the form, kanban), `ems_absence_request` (the form's
columns, and no Direction button before the Head) and `ems_absence_employee_view` (the employee's
own list and form, without the approvers' columns and badges).

## The request form

Three deliberate departures from how Odoo would lay this out, all of them to match the form the
centre already knew:

- **The absence type is a radio list in a full-width block of its own**, moved out of the
  half-width left column with `position="move"`. Nine options, several of them a whole sentence,
  wrapped into half a screen meant scrolling past the question before reaching the dates.
- **Everything below it is laid out in two columns.** The native form puts the whole request in
  a half-width column and leaves the other half empty, so it needed scrolling for no reason: EMS
  widens that column to the full sheet (`col-md-6` → `col-md-12`) and sets `col="4"` on its
  group, which gives two label/field pairs per row. On the manager form the leave-stats widget
  wraps underneath instead of sitting beside it.
- **The short name is bold inside each option.** `ems_absence_type_radio`
  (`static/src/js/backend/absence_type_radio_field.js`) is Odoo's radio field with one change: it
  splits the label at the colon and sets the first half in bold, so there is something to scan
  without losing the declaration that follows. Its template inherits `web.RadioField` in
  **primary** mode - an extension inherit would repaint every radio field in the application.
- **Nothing is filed until the employee presses "Send request".** Odoo saves a form by itself
  after a while, *even one nobody typed into* - so a teacher who merely opened the request screen
  to look at it ended up with a real absence on record. The fix is a field rather than a fight
  with the web client: `ems_submitted` is required by a `@api.constrains`, and the only thing
  that ever sets it is the `ems_absence_submit` widget
  (`static/src/js/backend/absence_submit_widget.js`), behind a confirmation dialog.

  It has to be a widget, not a `type="object"` button: the web client saves the record *before*
  calling a button's method, and at that point the record is not saveable yet. The widget sets
  the field on the record in memory and then saves, in that order.

  The button stays **disabled** until the request is actually sendable - an absence type chosen,
  a real span of time (either "Whole day?" or an end time later than the start), and the
  responsible declaration accepted - and a tooltip says which of those is missing - carried on a wrapper around the
  button, because a disabled button emits no hover events, so neither `title=` nor Odoo's own
  `data-tooltip` would ever fire on the button itself. That is not
  only politeness: pressing it while something was missing used to set the flag, fail to save,
  and then hide the button, stranding the employee on a request they could no longer send. The
  widget also puts the flag back if the save does not go through for any other reason, so a
  server-side refusal cannot strand them either.

  The side effect is deliberate: an autosave on an unsent form now raises a validation message
  telling the reader to use the button or discard, instead of quietly creating a request.

### The first state is "Pending"

Odoo calls it "To Approve", which reads as an instruction to whoever is looking at it; from the
employee's own list it is simply the state their request is in, and the spreadsheet this
replaces called it `Pendent`. Relabelled with `selection_add=[('confirm', 'Pending')]` - for a
value that already exists, `fields.py` merges the added label over the inherited one, so this
renames just that one state and leaves the rest in Odoo's hands.

### The responsible declaration

Carried over verbatim, both halves: the paragraph naming the absence types it covers, and the
sentence the employee signs. **Required for every absence type**, not only the ones the intro
enumerates - it is the employee asserting that the reason they gave is true, which applies
whatever they picked. Enforced by `required=` in the view and by the same `@api.constrains` that
checks the request was sent.

## "Whole day?" is the only control over how an absence is entered

The original form asked for `Data inici` and `Data final` as full datetimes and carried a
`Dia Sencer?` column. EMS reproduces exactly that, with one checkbox:

| `ems_full_day` | The employee gives | Counted as |
|---|---|---|
| unticked (the usual case) | one day, a start time and an end time | the real time missed, rounded to 15 minutes |
| ticked | a start date and an end date | a full working day per working day |

Odoo expresses the same thing the other way round and in two fields, both of which are dropped
from the form: `request_unit_hours` ("Custom Hours") is now **derived** from `ems_full_day`
(`request_unit_hours = not ems_full_day`), and `request_unit_half` ("Half Day") has no use at
the centre. Both stay in the view as invisible fields rather than being removed, because other
parts of the form still reference them in `<label for="...">` and `invisible=` expressions, and
Odoo refuses to validate a view whose label points at a field it does not contain.

Ticking the box copies the start date into the end date
(`_onchange_ems_full_day_dates`), since a whole-day absence is usually a single day - the
employee only touches the end date when they want several.

The type still seeds the flag: `Salut` and `Prova mèdica invasiva` start ticked
(`ems_full_day_default`), reproducing the Apps Script's flat 7.5 h, and the employee unticks it
when they were only away for part of the day.

## Menu

Absences hang from **Employee Attendances**, not a root app menu of their own: staff attendance
and staff absence are the same subject at the centre, and that menu already gathers the guard
schedule and (under its own "Attendance" submenu) the correction requests. `ems.group_secretary`
is added to that parent menu,
because administrative and services staff hold neither the teacher nor the attendance officer
group and would otherwise not be able to reach their own absences at all.

**"Absences" carries the My Time Off action itself, and every entry under it is restricted to
absence managers.** That is not tidiness: Odoo renders a menu entry as a clickable link only when
it has no children the reader can see (`web.NavBar.SectionsMenu`,
`t-if="!section.childrenTree.length"`). So an employee, who can see none of the sub-entries,
gets a single click straight to their own list; a manager sees the sub-entries and therefore the
usual dropdown - which is why My Time Off keeps its own entry there, restricted, rather than
being archived.

| Entry | Who sees it | Why |
|---|---|---|
| (the "Absences" entry itself) | everyone | Carries the My Time Off action, so one click lands an employee on their own list |
| My Time Off | `group_hr_holidays_responsible` | Only a manager needs it as an entry: for them the parent is a dropdown header, not a link |
| Overview | `group_hr_holidays_responsible` | The centre-wide absence calendar: what an absence manager uses to see who is missing. Meaningless to an employee, whose record rules would empty it anyway |
| Management, Reporting, Configuration | native groups | Unchanged |
| Management > Requested absences | native groups | EMS entry on Odoo's own `hr_leave_action_action_approve_department`, replacing `hr_holidays.menu_open_department_leave_approve` ("Time Off"), which is archived: next to the expected absences, the name has to say which of the two kinds it lists |
| Management > Expected absences | `ems.group_head_of_studies` | Added by EMS, see *Expected absences* |

The action behind My Time Off also drops Odoo's default `search_default_group_date_from`: the
centre's own list is short and already sorted by date, so grouping it by month only buries a
handful of requests under a fold each.

Odoo's own employee dashboard (`hr_leave_menu_new_request`) is archived: it shows the same
records as My Time Off in a calendar, and the centre works from the list. Its parent level
("My Time") is archived with it, since the dashboard and the allocations were all it held.

## The supporting document is asked for on every request, at any time

Odoo shows the attachment only when the absence type carries `support_document`, and only while
the request is `confirm` or `validate1`. EMS drops both conditions from the inherited form
(`invisible="0"` on the label and the field alike).

- **By type.** The flag says which types *require* a justification, not which ones accept one.
  The centre files whatever the employee has for any absence: somebody who can document a
  "Justified absence" or a training day had nowhere to attach it.
- **By state.** The document is attached *after* the Head's acknowledgement - a medical
  certificate is usually handed in days after the absence itself. With the field hidden from the
  moment a request was approved, a request awaiting its document could never leave that state.

The second one needed a matching change in security, because two different mechanisms were
hiding it:

- `hr.leave.write()` already exempts `attachment_ids`, `supported_attachment_ids` and
  `message_main_attachment_id` **by name** from every restriction it puts on an approved or
  already-started request, so Odoo's own intention here is clear.
- Its **record rule** is not, and cannot be, that precise: `hr_leave_rule_employee_update`
  scopes an employee's write access to `state not in ('validate', 'validate1')`, and an
  `ir.rule` cannot name fields. So an employee could see the field on their approved request and
  still be refused when they filed anything into it.

`security/rules/attendance.xml`'s `rule_absence_own_request_write` widens that (rules of the
same group are OR-ed) to the employee's own requests whatever their state, and
`hr.leave._ems_check_own_approved_write()` closes it back down to the attachment fields above -
the field-level half an `ir.rule` cannot express. Everything else about an approved request
stays the approver's to change, and raises an `AccessError` naming the justification as the one
thing still open.

## The chatter entry an employee sees after filing

hr_holidays schedules an approval activity (`mail_act_leave_approval`) on every request awaiting
a decision, and the chatter prints it above everything else. Two things about it were wrong for
this centre, and neither could be fixed with a data file or a translation:

- **The note carried the type's whole legal wording.** It is built inline in `activity_update()`
  as `New %(leave_type)s Request created by %(user)s` from `holiday_status_id.name`, which here
  is a full sentence - so the first thing the employee read after filing was a paragraph of
  legalese. `hr.leave.activity_update()` rewrites the note with `ems_short_name` afterwards
  rather than reimplementing forty lines of state handling and deadline arithmetic that have
  nothing to do with it. The note is read as `str()`, not as the `Markup` the Html field
  returns: `Markup.replace()` escapes both arguments, so a type name carrying an apostrophe
  would stop matching itself.
- **Its Catalan name was machine-translated nonsense**: `Temps de desaprovació` for "Time Off
  Approval" (and `Temps d'apagada de la segona aproximació` for the second approval - "apagada"
  is a power cut, "aproximació" an estimate). `mail.activity.type
  ._ems_fix_approval_activity_names()` replaces both with `Aprovació d'absències` /
  `Segona aprovació d'absències`, leaving English and Spanish alone.

  **A `.po` entry cannot do this**, even though a `.po` reference may name a record another
  module owns: both activity types carry `ir_model_data.noupdate = True`, and
  `TranslationImporter.save()` overwrites an existing translation on such a record only under
  `force_overwrite`, which no module load ever passes (`_load_module_terms` passes plain
  `overwrite`). Same reason `_ems_deactivate_native_types()` has to be code. Called from both
  `post_init_hook` and `migrations/18.0.0.24.0/post-migrate.py`, and a no-op when Catalan is not
  installed.

The activity's **deadline** is Odoo's, untouched: `date_from` minus the type's `delay_count`
(15 days), floored at today - which is why a request filed well in advance shows "Finalitza en
N dies" and one filed for tomorrow shows today.

## Removing a justification asks first

The stock `many2many_binary` widget drops an attachment the moment its "x" is clicked - no
confirmation, no undo. On an absence that file is the justification itself, often the only copy
of a certificate the employee handed in, and the people most likely to click it are working
through dozens of requests in a row. `ems_attachment_confirm`
(`static/src/js/backend/absence_attachment_field.js`) is the same widget with a confirmation
dialog in front of the removal; the form uses it in place of the stock one.

Covered by the `ems_absence_justification` tour, which checks both halves: that the dialog
appears at all, and that cancelling it really leaves the file alone. It runs on a request that
is approved *and* of a type requiring no document, so it doubles as the browser-side proof that
neither condition hides the field any more.

## Refusing asks first too, because almost nobody can undo it

`action_reset_confirm` puts a refused request back to `Pending`, but Odoo reserves that to its
Time Off Manager group: `_check_approval_update` raises *"Only a Time Off Manager can reset a
refused leave"* for anybody else, an officer included. `res.users._ems_sync_time_off_groups()`
takes that group back from everyone, deliberately, since it also grants read access to every
colleague's absence reason and attachment - with one explicit exception, `base.user_admin`
itself, kept out of the revocation (`protected` in that method) because the account needs to
stay a genuine Time Off Administrator. **In practice a refused request is final for the Head,
for Direction and for the employee: only that one administrator account can reopen it, and the
employee should normally expect to file a new request instead.** The confirmation dialogs say
exactly that, rather than claiming the button doesn't exist at all - it does, for that one
account, right there on the same screen (found 2026-09-22, issue #501).

`EmsAbsenceLeave.action_reset_confirm()` overrides the native method so that reset actually
leaves the request clean: on its own, Odoo's version only ever touches `state`, so a request
Direction had refused (`ems_direction_state = 'refused'`) would come back as `Pending` overall
while Direction's own column kept showing `Refused`, with `ems_status` stuck unable to reflect
either. The override clears `ems_direction_state` back to `not_done` for exactly those leaves,
via `sudo()` - reaching this method at all already required the wider Time Off Manager group, so
clearing a now-stale refusal is not a fresh Direction decision needing its own check.

The button that causes it sits next to Approve on three different screens, and on two of them it
is a bare icon in a row. All three confirm first, through Odoo's own `confirm` attribute rather
than any code:

| View | Attributes |
|---|---|
| `hr_leave_view_form` (header) | `confirm`, `confirm-title`, `confirm-label` |
| `hr_leave_view_kanban` | `confirm`, `confirm-title`, `confirm-label` |
| `hr_leave_view_tree` | `confirm` only |

**The list gets only `confirm` on purpose.** A list view is validated against a RelaxNG schema
(`base/rng/list_view.rng`; there is no `form_view.rng` at all, which is why form and kanban are
unconstrained here), and its `button` definition allows `confirm` but neither `confirm-title`
nor `confirm-label`. Adding them makes the whole view invalid and the module upgrade fails.

Direction's own Refuse (`action_ems_direction_refuse`, see *The approval, step by step*) carries the same
confirmation, in the list and in the form header.

Covered by the `ems_absence_refuse_confirm` tour, which cancels the dialog from the list button
and confirms it from the form one, and by `test_refusing_is_not_reversible_at_the_centre`, which
asserts the rule the wording rests on for a regular officer. `test_resetting_a_head_refusal_
clears_it` and `test_resetting_a_direction_refusal_also_clears_the_direction_check` cover what
the one account that *can* reach `action_reset_confirm` actually gets back.

## Allocations and accrual plans are hidden

Odoo's allocations grant an employee a quota of a type up front and refuse requests once it runs
out. Every EMS type sets `requires_allocation = 'no'` deliberately - the health allowance warns,
it never blocks - so allocations can only confuse here, and accrual plans (rules that grow an
allocation over time) are meaningless without them. Both menus are archived in
`views/attendance/absence/menu.xml`, and the dashboard's own "Pending Requests / New Allocation
Request" card is removed by an OWL template inherit
(`static/src/xml/backend/absence_dashboard.xml`) - it was the last remaining way into them. The
same file renames the dashboard's create button from a bare "New" to "Absence request".

Both changes are covered by the `ems_absence_dashboard` tour: an OWL template inheritance error
surfaces only in a browser, never in `./upgrade.sh`, which merely checks the XML parses.

## Expected absences

The Head of Studies or their Deputy often knows a teacher will be away before the teacher files
anything (a phone call first thing in the morning, a training day agreed in a meeting). The guard
duty board has to plan around it all the same, so `ems.absence_pending`
(`models/employees/absence_pending.py`) lets them enter it on the teacher's behalf. It is not an
`hr.leave`: it has no type, no approval and no hours to count, and it is invisible to the teacher.

```mermaid
erDiagram
    HR_EMPLOYEE ||--o{ EMS_ABSENCE_PENDING : "employee_id (teachers only)"
    HR_LEAVE |o--o{ EMS_ABSENCE_PENDING : "leave_id (set once, for good)"
    EMS_ABSENCE_PENDING {
        datetime date_from
        datetime date_to
        text note
        selection state "pending / linked"
    }
```

| Field | Notes |
|---|---|
| `employee_id` | Required. The picker's domain (`_domain_employee_id`) offers only teachers in the user's own branch, the same domain the record rule enforces |
| `date_from`, `date_to` | Required `Datetime` range (UTC in the database, like every datetime). Default: today 08:00-15:00 in the company's timezone. `date_to > date_from` |
| `note` | Optional, for the Head's own reference |
| `state` | `pending` (labelled *Expected*) until linked, then `linked` (*Requested*) for good. Stored, not computed from `leave_id` |
| `leave_id` | The teacher's own request it was linked to. `ondelete='set null'` |

**Linking is automatic and final.** `hr.leave.create()` and, when its dates, hours, employee or
state change, `hr.leave.write()` call `ems.absence_pending._link_to_leaves()`: every `pending`
entry of the same employee that overlaps the absence becomes `linked` to it. The absence's range
is read by `hr.leave._ems_utc_range()` exactly as the guard duty board reads it (the requested
hours of a partial one-day absence, whole days in the company's timezone otherwise), not from
Odoo's own `date_from`/`date_to`, which clip a whole day to the employee's working hours. It runs
under `sudo()`, since the teacher filing the absence has no access to the model at all.

Only absences in a state the board plans around (`confirm`, `validate1`, `validate`) link. Once
linked, the entry has done its job and stays as history: refusing, cancelling, moving or deleting
the teacher's absence never sends it back to `pending`, and its employee and dates can no longer
be edited (`write()` raises). From then on only the real absence counts.

**On the guard duty board**, `ems.course._get_guard_duty_absence_intervals()` adds every
`pending` entry touching the requested day as a `pending` interval, clipped to that day in the
company's timezone (`_get_local_hours()`). Linked entries are ignored. See
[guard_duty_board.md](../attendance/guard_duty_board.md).

**Access.** Only `ems.group_head_of_studies` has an ACL on the model (full CRUD). The Director
implies that group. `rule_absence_pending_hierarchy` (`security/rules/attendance.xml`) narrows it
to `[('employee_id', 'child_of', user.employee_ids.ids), ('employee_id.employee_type', '=',
'teacher')]`: the teachers below the user through `parent_id`, i.e. their own branch of the real
hierarchy, not every teacher centre-wide. The Director sits above every Area Manager, so the same
domain gives them the whole centre. Department Chiefs, tutors and teachers have no access at all.

Technical administrators (`base.group_system`, e.g. `admin`) usually have no place in the org
chart, so the hierarchy rule alone would leave them no teacher to choose. They get their own ACL
and `rule_absence_pending_system`, `[('employee_id.employee_type', '=', 'teacher')]`; rules of
different groups are OR-ed, so it widens their reach to every teacher without touching anyone
else's. The teacher picker's domain (`_domain_employee_id`) mirrors both rules.

The menu entry, **Absences > Management > Expected absences**, carries
`groups="ems.group_head_of_studies,base.group_system"`.

## Hour computation

Odoo counts a leave against the employee's `resource_calendar_id` — in EMS, their real teaching
timetable. That is the wrong measure here: a teacher with a single lesson on a Tuesday who
misses the whole day would be credited one hour. The centre counts the opposite way, so
`hr.leave._get_durations()` (the method `hr_holidays` itself factored out to be hooked) is
overridden with one rule and no per-type exception:

```mermaid
flowchart TD
    A["Absence"] --> B{"More than one day,<br/>or 'Whole day' ticked?"}
    B -- yes --> C["7.5 h per Mon-Fri day in the range"]
    B -- no --> D["Real clock time missed,<br/>rounded to 15-minute steps"]
```

`Salut` is not special-cased: the Apps Script's flat 7.5 h for it was a shortcut, which is why
the manager hand-corrects it down to 0.5-3 h in 14 of the 41 real rows, whenever the employee
did come in for part of the day. It simply defaults to `ems_full_day_default = True`.

Both quantities are settings, not constants: `res.company.ems_full_day_hours` (7.5) and
`res.company.ems_health_allowance_hours` (15). Read them through `_ems_full_day_hours()` /
`_ems_health_allowance_hours()`, which fall back to the field default — a zero would make every
absence worth nothing and divide by zero in the duration computation.

Public holidays are not deducted from a multi-day range.

## The health allowance

Only types flagged `ems_counts_health_allowance` (just `Salut`) consume it. `ems_health_hours_used`
sums that employee's hours over the current course's window — `ems.course.date_range()`, 1
September to 31 August — and `ems_health_allowance_exceeded` flags going over.

**It warns, it never blocks.** An `@api.onchange` tells the employee they are over the limit and
the request is flagged in the approver's list view, but nothing refuses the request: going over
is the centre's problem to resolve with the employee, not the software's to decide. This is also
why no type uses an `hr.leave.allocation`, whose whole semantics are the block we do not want.

## Translating this feature's JavaScript and Python strings

Worth knowing before adding any string here, because nothing warns you when it is wrong: Odoo
only serves a translation to the browser, or to Python's `_()`, when its `.po` block carries the
right kind marker (`odoo/tools/translate.py::_load_web_translations`, whose filter is
`JAVASCRIPT_TRANSLATION_COMMENT in row['comments']`).

```
#. module: ems
#. odoo-javascript                 <- required for code:addons/ems/static/... references
#: code:addons/ems/static/src/js/backend/absence_submit_widget.js:0
msgid "Send request"
msgstr "Envia la sol·licitud"
```

A block with the reference and the translation but no marker loads into the database, exports
cleanly, and still renders in English. Use `#. odoo-python` for `code:` references outside
`static/`. To check rather than hope:

```python
CodeTranslations().get_web_translations('ems', 'ca_ES')      # what the browser receives
CodeTranslations().get_python_translations('ems', 'ca_ES')   # what _() resolves
```

## The per-employee report

Odoo's "Time Off Analysis" (`hr_holidays.action_hr_available_holidays_report`), reshaped into the
spreadsheet's own `Total per profe` tab: one line per employee with the hours that count against
the health allowance.

| Change | Why |
|---|---|
| `ems_health_hours` column, with `sum=` | The figure the centre has to keep under the yearly allowance. A stored field of its own so the list totals it per employee group - `ems_health_hours_used` on the request is a per-request running total and cannot be aggregated |
| "Current Course" filter, default | Odoo's own "Current Year" is the calendar year, which cuts a school year in half: a September absence and a February one would never be counted together |
| `create="0"` | Filing an absence belongs on the employee's own screen, which is where the send button and its confirmation live |

The filter needs a field to work on, so `hr.leave.ems_course_id` resolves each absence to the
`ems.course` whose window (`date_range()`, 1 September to 31 August) contains its start date. It
is stored, which also makes it groupable. A course created later does not retro-assign old
absences, which is correct: they already carry the course they were filed in.

## The monthly report

`Absences > Reporting > Monthly totals` (`ems.action_absence_monthly_report`), the spreadsheet's
`Totals per mes` tab: absences grouped by month, with the hours that count towards what each
Area Manager reports summed on the column and the number of absences coming from the group
itself.

Its domain is `ems_counts_hours = True` plus a state that is neither refused nor cancelled. That
last part is a deliberate departure: the spreadsheet's `SUMIFS` ignored the status column
entirely, so a cancelled request still contributed hours nobody was ever absent for.

`ems_counted_hours` is the summable counterpart of the flag - the absence's hours when it counts,
zero when it does not - for the same reason `ems_health_hours` exists on the other report: a
per-request figure has to be a stored column of its own before a list can total it per group.

### One compute per field, on purpose

`ems_counts_hours`, `ems_needs_atri` and `ems_full_day` all derive from the absence type and
were once a single compute method. They are three now: **Odoo skips a compute method entirely
for a record whose `create()` values mention any one of the fields it assigns.** Creating a
request with `ems_full_day` set - an import, an API client, the guard-duty automation to come -
therefore left `ems_counts_hours` false and quietly dropped that absence out of the monthly
report. Nothing fails; the number is just wrong.

## Who gets told

Most of this is Odoo's, and deliberately left alone:

| When | Who | Mechanism |
|---|---|---|
| A request is sent | The approver | Native activity scheduled on the request (`activity_update` → `_get_responsible_for_approval`) |
| Approved or refused | The employee | Native message on the request |
| Approved or refused | The employee's **own department chief** | EMS: `_ems_inform_department_chief()` subscribes them just before the state change |
| Approved by the Head | **Direction** (the company's `director_id`) | EMS: `_ems_direction_partners()` subscribes it in `action_approve()` - its own review starts there. Not when the Director is the absent employee or is the one approving |
| Approved or refused | Everyone following the request | EMS: `_ems_post_outcome()` posts a summary - who, which type, the dates, the hours, and the overall status (`ems_status`, e.g. *Pending Direction*) |

Odoo's own note on validation ("Your `<type>` planned on `<date>` has been accepted", with the
type's full legal wording dropped mid-sentence and nothing else) is **suppressed** and replaced
by that summary. It cannot be reworded through translation: `_()` resolves against the module
the string is emitted from, so an entry in EMS's catalogue is never consulted for a sentence
`hr_holidays` prints. Overriding `_validate_leave_request()` outright would mean copying its
calendar-meeting logic, so instead the note alone is stopped, through a context flag read by a
`message_post` override and set only for the duration of that one call.

The department chief is the one piece Odoo has no notion of. It is also the reason the Google
form asked every employee which department they belonged to: purely to look up who to copy, the
`Informat d'absencies` rows of its `Config` tab. EMS already knows the employee's chief, so the
question left the form and the answer is derived.

They are **informed, not given access**: `private_name` still masks the written reason for
anyone who is not the employee, their approver or an officer. The chief learns that a colleague
is away and of what kind - what covering a department needs - without the reason behind it.

Mail leaves through the company's configured server, which is the other half of what this
replaces: the Apps Script sent from the personal Google account of whoever last ran its
"Identificar-me com a remitent d'emails" menu entry, and stopped working when that person left.

## Public holidays

Public holidays are native `resource.calendar.leaves` rows with no `resource_id`, managed from
**Employee Attendances > Absences > Configuration > Public Holidays** (Time Off Administrator,
which in practice is only `admin`, see *Access control*). Odoo does not ship any holiday
calendar: national, Catalan, local and the centre's own closing days (free-disposal days,
Christmas, Easter...) are all entered by hand. EMS extends the model in
`models/employees/public_holiday.py`.

```mermaid
flowchart TD
    A[Public holiday created or edited] --> B{resource_id set?}
    B -- no --> C[calendar_id forced empty:<br/>applies to every schedule]
    B -- yes --> D[personal leave, calendar kept]
    C --> E[native: overtime recomputed<br/>for every affected employee/day]
    D --> E
    E --> F[EMS: technical attendances on days<br/>left with no expected hours are deleted]
```

### A public holiday always applies to every schedule

Natively, a public holiday may be tied to one working schedule (`calendar_id`, "Working Hours")
and then only applies to employees on exactly that schedule. That never fits EMS: every teacher
has a personal schedule (one `resource.calendar` per employee, recreated at every course
transition), so a holiday tied to one of them misses everybody else. The trap is easy to fall
into, because the "Public Time Off" smart button on a schedule's form opens the list with
`default_calendar_id` set to that schedule: the first Diada entered this way was tied to the
default schedule framework, which has no employees, and applied to nobody.

So `create()` and `write()` always leave `calendar_id` empty on a row without `resource_id`
(defaults from the context included), and the "Working Hours" column is hidden from the Public
Holidays list (`view_public_holiday_list_ems`). Personal leaves (`resource_id` set, e.g. an
approved `hr.leave`) keep their calendar untouched.

### Cleaning up the "absence" attendances a holiday makes obsolete

With `res.company.absence_management` on, Odoo's `hr.attendance._cron_absence_detection()`
creates every night a one-second *technical* attendance (`in_mode`/`out_mode` `'technical'`,
shown in red) for each employee who didn't check in the day before, so the missed hours count as
negative overtime. It deletes it right away when that day had no expected hours - a holiday
entered in advance therefore never produces one.

A holiday (or absence) entered *afterwards* is only half handled natively: creating, editing or
deleting a `resource.calendar.leaves` recomputes the overtime of the affected employees and days
(`hr_attendance/models/resource_calendar_leaves.py`), but the red technical attendance stays.
EMS's `_unlink_technical_attendances_without_expected_hours()`, run after `create()` and
`write()`, deletes the technical attendances on the affected days that are now left with no
expected hours (`hr.employee._get_expected_attendances()`, the same computation the native cron
uses). It only ever touches technical attendances, and only on days nothing is expected any more:
a real check-in on a holiday, or a technical attendance on a partial holiday, is kept. The same
applies to a personal leave, so approving a whole-day absence after the fact also clears that
day's red row.

`migrations/18.0.0.30.1/post-migrate.py` detaches the public holidays already tied to a schedule
through the same `write()`, which also clears the technical attendances they had left behind.

## Access control

| Group | `hr.leave` records visible | Reason and attachment | Can |
|---|---|---|---|
| Any employee | Own requests; colleagues' via the native calendar/dashboard | Own only — `private_name` renders as `*****` for everyone else | Create, edit and cancel their own while unapproved; file the supporting document at any time, approved included |
| Area Manager (`hr_holidays.group_hr_holidays_responsible`) | Only employees whose `leave_manager_id` is them, via the native rule `[('employee_id.leave_manager_id', '=', user.id)]` | Yes, for those employees | Approve, refuse |
| Head of Studies, academic admin (`hr_holidays.group_hr_holidays_user`) | All, centre-wide | Yes | Approve, refuse, manage the catalogue |
| Director (`ems.group_director`, implies the row above) | All, centre-wide | Yes | Direction's own approval (done / documentation insufficient / pending / refuse) on any request the Head has validated; acknowledge/validate/refuse as the Head only where it is the employee's `leave_manager_id` (screens only, see *The approval, step by step*) |

Two native mechanisms carry most of this:

- **`hr.leave.private_name`** (`groups='hr_holidays.group_hr_holidays_user'`) with
  `_compute_description()` masking `name` as `*****` unless the reader is the employee, their
  `leave_manager_id` or an officer. That is the confidentiality requirement — absence *type* is
  public, the written reason is not — with no EMS code at all.
- **`group_hr_holidays_responsible`**, whose record rule is scoped entirely by
  `leave_manager_id`.

EMS adds exactly one record rule of its own here, `rule_absence_own_request_write` (see the
supporting document section above), paired with a field-level check in `write()`. The
expected absences have their own model and rule, see *Expected absences* above.

  **Who holds it is derived from the approval relation, not from a group chain.** The three
  approvers sit in two different EMS chains (`group_head_of_studies` for VET and ESO/BTX, the
  Secretary for ASP), and the ASP one is a single person - not the secretariat as a body, whose
  members are ordinary employees as far as absences go. There is no group that means "approves
  absences", so `res.users._ems_sync_time_off_groups()` grants it to whoever is currently named
  as some employee's `leave_manager_id` and takes it back from everyone else. That stays exact
  on its own as Area Managers change.

Two things about that method are easy to get wrong, and both were:

- **It has to read archived users** (`active_test=False`). `base.default_user` - the template
  `res.users._default_groups()` copies onto every new user - *is* an archived user, and it is
  the record hr_holidays grants its Administrator group to in the first place. Skipping it left
  every account created afterwards born as a Time Off Administrator, able to read every
  colleague's reason and attachment: the exact thing this method exists to prevent, arriving
  through the back door.
- **On upgrade it has to run *after* `leave_manager_id` is recomputed**, which is why
  `migrations/18.0.0.24.0/post-migrate.py` calls `_recompute_leave_managers()` first (archived
  employees included). During that upgrade the field still holds Odoo's own value, derived from
  `parent_id` - the Department or Seminar Chief. Granting the approver group from it before the
  recompute handed the group to every Department Chief and left it there.

### hr_holidays grants the approver group behind EMS's back

Not only on upgrade: `hr.employee.write()` in hr_holidays grants
`group_hr_holidays_responsible` to whoever a **written `parent_id`** names, and takes it back
only from users who were previously somebody's `leave_manager_id`. In EMS `parent_id` is the
Department or Seminar Chief, a stored compute that `_cascade_department_heads()` refreshes
whenever an Area Manager, a Chief or a department's shape changes - and it does so *before*
`_compute_leave_manager()` has said who really approves. The Chief was therefore left holding a
group nothing would ever take back: four of them still had it on the development database, which
means read access to every absence reason and supporting document in their area - the exact
confidentiality rule this feature exists to enforce.

`_cascade_department_heads()` now finishes by calling Odoo's own
`res.users._clean_leave_responsible_users()` on the users that write could have touched, which
removes the group from anyone who is nobody's `leave_manager_id`. Covered by
`test_a_department_chief_never_keeps_the_approver_group`, which fails without it.

### hr_holidays leaks a restricted field into the Teachers screen through a widget

`current_leave_id` (the type of absence an employee is on right now) is declared
`groups="hr.group_hr_user"` on `hr.employee`. hr_holidays also swaps the presence icon on
`hr.hr_kanban_view_employees` to its own `hr_presence_status_private` widget, and that widget's
JavaScript declares `current_leave_id` as a **field dependency**:

```js
Object.assign(hrPresenceStatusPrivate, {
    fieldDependencies: [..., { name: "current_leave_id", type: "many2one" }],
});
```

A widget's field dependencies go straight into the read specification the client sends. They are
never filtered by the group-based node stripping the view postprocessor applies to the arch, so
the field is requested even for a user the arch correctly hid it from. In stock Odoo nothing
notices, because a non-HR user is never shown `hr.employee` at all - they get
`hr.employee.public`, a different model with a different kanban. EMS does show it: its own
"Educational Community > Teachers" and "> ASP" screens are `hr.employee`, and
`security/ir.model.access.csv` grants `ems.group_teacher` read on it. From the moment
hr_holidays became an EMS dependency, every teacher opening either screen got

> You do not have enough rights to access the fields "current_leave_id" on Employee (hr.employee)

instead of the screen.

`views/community/employee/kanban.xml` keeps the private widget for `hr.group_hr_user` and renders
hr's plain `hr_presence_status` - same icon, no leave type, no extra field read - for everyone
else, via a negated group (`groups="!hr.group_hr_user"`, supported since Odoo 17). That inherited
view carries `priority=20` so it applies *after* hr_holidays' own inherit of the same view
(priority 16), whose widget swap it depends on being already in place.

Widening `current_leave_id`'s own groups would have been the shorter fix and is deliberately not
what happened: what a teacher may know about a colleague's absence is the fact and the interval,
never its type - the same line `ems.guard.duty.board._get_guard_duty_absence_intervals` draws.

Covered by `tests/test_employee_presence_widget.py` (the arch, per group) and
`tests/test_employee_teacher_kanban_tour.py` (what the browser actually asks the server for -
the backend half cannot see this bug at all).

## Related

- `plans/absence_management.md` — full design plan, including the cycles not yet implemented.
- [department.md](department.md) — the top-level department / Area Manager model this builds on.
- [role_hierarchy.md](role_hierarchy.md) — how the three approver roles are assigned.
