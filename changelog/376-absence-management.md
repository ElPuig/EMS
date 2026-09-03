# What's new:

## Staff absence management moved from Google Forms into EMS (cycle 1: foundation):

The centre managed staff absences with three parallel Google applications (a Form feeding a
Sheet driven by an Apps Script), one per collective - VET/CCFF, ESO/BTX and ASP - identical
except for who approved them. EMS now builds this on Odoo's native `hr_holidays` rather than a
bespoke model, so the request workflow, approval, hour computation against the employee's
working schedule, attachments, calendar event and reporting all come from the framework.

This first cycle lands the foundation: the `hr_holidays` dependency (which also brings in
`calendar`), the absence type catalogue, the derived approver and the access model. The
EMS-specific request fields, the hour rules, the 15 h/course health allowance and the guard-duty
integration follow in later cycles - see `plans/absence_management.md`.

## Absence approver derived from the department hierarchy, not configured:

The Google sheet held a `Config` tab mapping each department to its absence manager. EMS derives
it instead: `hr.employee.leave_manager_id` now resolves to the Area Manager of the employee's
top-level department (Deputy Head of Studies for VET, Head of Studies for ESO/BTX, Secretary for
ASP), replacing the native derivation, which followed `parent_id` and would have pointed at the
Seminar Chief or Department Chief - the wrong person for an absence request. It re-syncs
automatically whenever an Area Manager changes, through the same cascade the role hierarchy
already uses, and an Area Manager's own absences fall back to the Director so nobody approves
their own.

## Absence type catalogue:

Nine absence types seeded in `data/cat/hr.leave.type.csv`, matching the Generalitat's own staff
absence regulations: sick leave, health, medical appointment, invasive medical test, menstrual
or climacteric flexibility, training, justified absence, service assignment and ATRI. All are
requested in hours, approved by the employee's approver, and never gated on an allocation - the
health-hour allowance is designed to warn rather than block. Catalan and Spanish translations
included.

## Absence confidentiality:

The absence type is public - it is what the calendar and, later, the guard-duty board show - but
the written reason and any supporting document are visible only to the employee, their approver
and the Head of Studies / Direction. This comes from two native mechanisms rather than new EMS
code: `hr.leave.private_name`, which masks the reason for everyone else, and the Time Off
Responsible group, whose record rule is scoped entirely by who the employee's approver is. The
Head of Studies chain gets centre-wide officer access; the Secretary chain gets only their own
reports, which keeps the rest of the secretariat out of teachers' health data.

## Absence request fields and hour rules (cycle 2):

The absence request now carries the centre's own data alongside Odoo's: whether it counts in the
monthly hours report, whether it is a whole-day absence, whether it is filed through ATRI, the
responsible declaration the employee has to accept, and Direction's own document check. The
first three are proposed from the absence type and stay editable by the approver afterwards,
because employees do miscategorise their own absences - the same freedom the spreadsheet's own
columns gave them.

Direction's check no longer appears while a request is being written - it cannot have been
verified before it exists - and shows as a coloured badge in every absence list, the employee's own
included, so anyone can see at a glance whether a justification is still pending - while only
Direction can actually set it, enforced in the model rather than by hiding the field.

Direction's check (`Not done` / `Missing document` / `Done`) is deliberately independent of the
approval workflow rather than a second validation step: a request can be approved and still be
waiting for its supporting document. It is also where Direction confirms an ATRI absence was
really filed on the Generalitat's portal.

## Absence hours counted the way the centre counts them:

Odoo measures a leave against the employee's own timetable, which would credit a teacher with a
single lesson that day just one hour for missing the whole day. Absences are now counted the
centre's way instead: a whole-day or multi-day absence is worth a full working day per working
day, whatever the timetable says, and a partial absence counts the real time missed, rounded to
quarter hours. This also fixes a real gap in the spreadsheet, where an absence spanning more
than one day counted zero hours and simply fell out of the monthly report. The length of a
working day and the size of the health allowance are both settings, under a new "Staff Absence
Settings" block in EMS settings.

## Health absence allowance warns instead of blocking:

Self-declared health absences count against a per-course allowance. Going over it shows the
employee a warning when they file the request and flags the request in the approver's list, but
never refuses it - resolving an excess is a conversation between the centre and the employee,
not a decision for the software. This is also why no absence type is gated on an Odoo
allocation, whose semantics are exactly that block.

## Browser tour for the absence screens:

The Time Off list and form, both extended by EMS, are now covered by a browser tour that opens a
real request, checks the EMS fields render, changes Direction's check and verifies it round-trips
to the list. Neither the upgrade nor the backend tests open a browser, so this is what actually
proves the inherited views still render.

## The request form now reads like the form it replaces:

The absence type sits in a full-width block of its own rather than a half-width column, so the
long options no longer wrap into a wall of text the employee has to scroll past, and everything
below it is laid out in two columns so the whole request fits on one screen, and the short
name at the head of each option is set in bold to give something to scan. The responsible
declaration is carried over word for word - both the paragraph naming the absence types it
covers and the sentence the employee signs - and is required for exactly the types that text
enumerates. The declaration is required for every absence type, since it is the employee
asserting the reason they gave is true.

Filing a request now ends with an explicit "Send request" button that asks for confirmation that
every detail is correct. This closes a real hole: Odoo saves a form on its own after a while,
even one nobody typed into, so simply opening the request screen to look at it filed a genuine
absence. A request that has not been sent can no longer be saved at all.

The send button stays disabled until the request is genuinely complete - a type chosen, a real
span of time, and the declaration accepted - and says which of those is still missing. It also
recovers if the request cannot be saved for any other reason, rather than leaving the employee
looking at a request they can no longer send.

## Absence request kept faithful to the form it replaces:

The request screen now mirrors the Google form it comes from. The nine absence types carry the
form's own option texts verbatim - long sentences, because several are the legal wording the
employee is declaring when they pick one - and are offered as a list of options to tick rather
than a dropdown, so they can be read in full at the moment of choosing. None of them comes
preselected: choosing one is a declaration, not a default. A request's first state is called
"Pending", as the spreadsheet called it, rather than Odoo's "To Approve", which reads as an
instruction rather than a state. Everywhere the full
wording would only get in the way (the lists, the calendar) shows a short name instead, the same
one the old script used - and Odoo's own five types are archived so nobody can
pick one outside the centre's rules. How an absence is entered is now governed by a single "Whole day?" checkbox, the original
form's own column: left unticked the employee gives a day and a start and end time, and ticking
it asks for a start and an end date instead, with the end date following the start until they
change it. Odoo's own two toggles behind that - "Custom Hours", which said the opposite, and
"Half Day", which the centre has no use for - are gone from the form. The
supporting document is labelled "Justificante" and carries the form's own instruction about what
a medical certificate has to state. The ATRI flag is no longer something the employee chooses:
like the monthly-report flag, it follows from the absence type, and only the approver sees and
corrects it - which is also why the absence type itself stays editable for the approver after
approval, since employees do pick the wrong one.

## Staff absences live under Employee Attendances:

Installing the Time Off app added a root menu of its own. Absences now hang from "Employee
Attendances" instead, next to the guard duty schedule and the correction requests - the same
subject from the centre's point of view. Administrative and services staff, who hold neither the
teacher nor the attendance officer group, were granted access to that parent menu so they can
still file their own absences. Odoo's allocations and accrual plans are hidden: they are a
blocking quota mechanism the centre deliberately does not use, so the dashboard's allocation
request card was removed too. The create button on the absence calendar now says
what it creates, "Absence request", instead of a bare "New".

Clicking "Absences" now opens the employee's own list directly, with no second click: the
entry carries that action itself and everything under it is restricted to absence managers,
which is what makes Odoo render it as a link rather than a dropdown. The create button on that
list reads "New absence", and the list is no longer grouped by month: it is short and already
sorted by date, so the grouping only buried a handful of requests under a fold each.

The menu was trimmed to the two screens the centre actually works from: an employee gets their
own absence list, which is what clicking "Absences" opens, and the centre-wide absence calendar
is restricted to absence managers and Direction - it is what they use to see who is missing, and
an employee's own access rules would empty it anyway. Odoo's employee dashboard, which duplicates
the personal list as a calendar, is hidden along with the now-empty level above it.

## Removing a justification now asks for confirmation:

Odoo's attachment widget deletes a file the moment its "x" is clicked, with no confirmation and
no undo. On an absence that file is the justification itself - often the only copy of a
certificate the employee handed in - and whoever clicks it is usually working through a long
list of requests. It now asks first.

## Per-employee absence report:

Odoo's absence analysis screen now matches the spreadsheet tab it replaces: one line per
employee showing the hours that count against the yearly health allowance, which is the figure
the centre has to watch. It is filtered by the school year rather than the calendar year - the
calendar year cuts a course in half, so a September absence and a February one were never
counted together - and it no longer offers to create an absence, which belongs on the employee's
own screen.

## Monthly absence report:

The spreadsheet's monthly totals tab, as a report: absences grouped by month with the hours that
count towards what each area reports, and the number of absences behind them. Only the absences
the manager has marked as counting are included, and refused or cancelled ones are left out -
the spreadsheet's formula ignored the status column, so a cancelled request still contributed
hours nobody was ever absent for.

## Notifications:

The approver is told when a request arrives and the employee when it is decided, both through
Odoo's own mechanisms. On top of that, the employee's own department chief is informed once the
absence is approved or refused - which is the only reason the old form asked everybody which
department they belonged to, and something EMS already knows. They are informed rather than
given access: the written reason stays masked for them, so they learn a colleague is away and of
what kind without the reason behind it. All of it leaves through the centre's own mail server
rather than the personal account of whoever last configured the old script.

What those notifications say has been rewritten. Odoo announced an approval with a single line
that dropped the absence type's full legal wording mid-sentence and said nothing else, and the
department chief received little more than "Status: Pending → Approved". Both are replaced by a
summary naming the person, the absence type, the dates, the hours and the outcome - still
without the written reason, which stays private.

## User manuals:

Four manuals in Catalan, Spanish and English, one per role that actually touches the feature:
requesting an absence (anyone at the centre), managing them (Head of Studies and Direction),
approving them for administrative and services staff (Secretary), and configuring them
(Administrator). Each is written against the form and the spreadsheet it replaces, so a reader
who knew the old way can find the equivalent.

## ATRI portal links:

Choosing an ATRI absence type now shows, on the form itself, that the leave also has to be
requested on the Generalitat's portal, with a link straight to it and to its reference manual.
The links are in the teachers' manual too.

## The supporting document can be filed on any absence, at any time:

Odoo only offered the attachment on the three absence types that formally require one, and only
while the request was still awaiting a decision. Both restrictions are gone: a justification can
now be attached to any absence of any type, and to a request that has already been approved -
which is how a medical certificate handed in days later gets filed, and the only way Direction's
"Missing document" check could ever be cleared. Where the employee could previously see the
field but be refused by Odoo's own access rules on an approved request, a record rule of our own
now lets them file the document (and nothing else) themselves.

## Refusing an absence request now asks for confirmation:

A refused request cannot be reopened by anybody at the centre, so the employee has to file a new
one from scratch. The Refuse button sits next to Approve on the form, the list and the kanban,
and on the last two it is a bare icon at the end of a row - so all three now ask first, spelling
out that the decision is final.

## The chatter now says what an absence request is, in Catalan that means something:

Filing a request produced a chatter entry headed "Temps de desaprovació" - Odoo's own
machine-translated Catalan for "Time Off Approval", which means nothing - followed by the
absence type's entire legal wording as its description. The heading now reads "Aprovació
d'absències" and the description names the absence type the short way, the same way the lists,
the calendar and the notification e-mails already did.

# Fixes:

## An absence could silently drop out of the monthly report:

Three flags on a request are proposed from its absence type, and they shared one piece of code
to do it. Odoo skips that code entirely when a request is created with any one of those flags
already set, which left the "counts towards the monthly report" flag switched off without
anything failing - the absence simply went missing from the totals. Each flag is now worked out
on its own.

## Everyone became a Time Off officer when the app was installed:

Installing Odoo's Time Off app grants its Administrator group to the template new users are
copied from, and Odoo propagates that to every existing user - which handed all internal users
the right to read any colleague's absence reason and supporting document, and every employee
record besides. Those groups are now taken back from everyone who does not hold a role that
actually grants them, leaving centre-wide access to the Head of Studies and Direction and
approver-scoped access to the ASP area's own manager, as intended.

Who may approve is now derived from the approval relation itself rather than from belonging to
the secretariat: the group goes to whoever is currently named as an employee's absence approver
and is taken back from everyone else, so it stays correct on its own as those roles change. The
secretariat as a body are ordinary employees as far as absences are concerned.


## New users were still born able to read everyone's absences:

Taking the Time Off groups back from the staff missed the one record that hands them out: the
user template every new account is copied from, which is archived and so never showed up in the
list of users holding a group. Anyone created from then on started out as a Time Off
administrator again. The template is now cleaned along with everybody else, archived accounts
included.

## Department Chiefs were left able to approve absences:

Odoo hands the approver permission to whoever is named as an employee's manager, which at this
centre is their Department or Seminar Chief - not the person who actually decides absences. It
did so every time the department hierarchy was refreshed, and nothing ever took it back, so
several Chiefs could read the reason and the supporting document of every absence in their area.
The permission is now cleaned up whenever the hierarchy changes, and the upgrade works out the
real approvers before handing anything out.

## Translations that never reached the screen:

Fifteen translated strings in the absence feature were rendering in English despite being
translated: Odoo only hands a translation to the browser, or to Python, when its entry is marked
as coming from one or the other, and the marker was missing. Several entries also had their
references pointing at the wrong place after code moved between files, and three had been
written without the blank line that separates one entry from the next, which makes the reader
silently merge them. All corrected, and verified by asking Odoo what it actually serves rather
than by reading the files.

# Internal changes:

## Migration for existing installations (18.0.0.24.0):

Two of the fixes above cannot be expressed in a data file and would otherwise only reach
brand-new installations. Installing the Time Off app grants its administrator group to every
existing user, and Odoo's own five absence types are marked in a way that stops any data file
from archiving them, so both are handled in code - from the install hook for new databases and
from a migration script for the ones already running. The migration also recomputes every
employee's absence approver rather than trusting the order in which Odoo fills that field while
installing the app.

Rehearsed against a deliberately broken database - all users granted the administrator group and
the five native types re-activated - to confirm the script actually repairs it, rather than
shipping a script whose first real run would be in production.

## `hr.department._top_level_department()`:

New helper walking a department's `parent_id` chain up to its top-level ancestor. Deliberately
separate from the existing `_effective_manager()`, which stops at the first department that has
a manager of its own: an absence is always approved by the Area Manager of the whole area, never
by an intermediate Department Chief.

## `ems.course.date_range()`:

New helper returning a course's real calendar window (1 September to 31 August). The model only
stores the two years, but anything counting per course - the staff health allowance, for one -
needs real dates to filter on.
