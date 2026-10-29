# Technical Reference: Student Card (PDF)

## Overview

The student card (issue #524) is a QWeb PDF on `res.partner` that replaces the card Esfera
generates: an A4 sheet with the cards of the selected students, two columns, cut by hand. Every
card shows:

- The centre: its logo, name, phone and address (`res.company` / its partner).
- The student: photo (`image_1920`, a silhouette when missing; scaled down to fit its 22 x 29 mm
  frame with its proportions kept, since wkhtmltopdf ignores `object-fit`), "Last names, First name",
  identity document (`document_id`, or `passport_id` when there is none), birth date and IDALU
  (`student_id`).
- The **band**, two rounded blocks side by side. On the left, the main group's level acronym (ESO,
  BTX, CFGB, CFGM, CFGS, PFI, EFPS) in big letters on that level's own colour, the study's acronym
  (never its full name, so the block keeps one line; left out when it equals the level's, as in ESO
  and BTX) and the group's course year, big in a white circle (in ESO a 1st and a 4th year are told apart
  at a glance). On the right, whether the student **may leave the centre** (`can_leave_centre`), for
  the teacher at the door: "Pot sortir del centre" on green or "No pot sortir del centre" on red. The student may
  leave when they are of age (`is_adult`) **or** the family accepted an authorization whose template
  is of type *Leave the Centre* (`auth_leave`) for the academic year in force. Computed when the
  card is printed: a card printed before the student turns 18, or before the family accepts, keeps
  saying "No" until it is printed again.
- The academic year in force (`res.company.current_course_id`).
- The centre's stamp (`res.company.ems_card_stamp`) over the photo's lower right corner, as on
  official documents (swapping the photo breaks it), or an empty dashed circle to stamp by hand when
  none was uploaded.
- A Code128 barcode of the IDALU, for a future check-in at the entrance.

The back carries the Departament d'Educació i Formació Professional's logo
(`static/src/img/departament_educacio.png`, the same logo the Esfera card printed), the centre's
name, address and phone, a "personal and non-transferable" note, and the **QR of the card's public
check page** (see below).

```mermaid
flowchart LR
    LIST["Students list (selection)"] -->|"ir.actions.server, list binding"| ACT["res.partner.action_print_student_card()"]
    FORM["Student form: Actions dropdown"] --> ACT
    GROUP["Group form: Actions dropdown"] -->|"ems.group.action_print_student_cards()"| ACT
    ACT -->|"students the user acts on, sorted by name"| REP["ir.actions.report ems.report_student_card"]
    LEVEL["ems.level.card_color"] --> REP
    COMPANY["res.company: logo, address, ems_card_stamp, current_course_id"] --> REP
    ACT -->|"_ems_ensure_card_token()"| TOKEN["res.partner.ems_card_token / ems_card_course_id"]
    TOKEN -->|"QR on the back"| REP
    QR["QR scanned (no login)"] --> PAGE["GET /ems/card/&lt;code&gt;"]
    PAGE -->|"_ems_card_from_token()"| TOKEN
```

## Card check page (QR)

The QR on the back holds `<web.base.url>/ems/card/<code>`, a public page
(`controllers/student_card.py`, template `ems.student_card_check`) anyone holding the card can open
without logging in. It is how the teacher at the door tells a genuine card from a forged one, and it
always shows whether the student may leave the centre *now*, which the printed card can't.

**The code.** `res.partner.ems_card_token` (192 random bits, `secrets.token_urlsafe(24)`, unique) and
`ems_card_course_id`, both `groups='base.group_system'` and only read or written through `sudo()`:
a code is as good as the card in hand. `_ems_ensure_card_token()` runs in
`action_print_student_card()`, not while rendering (the report is downloaded on a read-only
cursor), and keeps the student's code for the whole academic year, so a damaged card printed again,
alone or with its whole group, keeps the same QR and never voids the cards already handed out. It
issues a new one when the code belongs to another year.

**Validity** (`_ems_card_from_token()`), checked on every scan: the code is the student's current
one, issued for `res.company.current_course_id`, and the contact is still a `student`. So a card
expires at the course flip, a withdrawal/graduation/expulsion voids it with no further action, and
`action_revoke_student_card()` (Actions dropdown of the student's form, same people as printing,
note on the record via `_message_log`) voids every card printed so far by renewing the code.

**What the page shows** (`_ems_card_check_values()`), decided with the developers to keep it free of
data-protection concerns while still useful against forgery: the level/study/course band, the
initials, the IDALU's last four digits (the rest as asterisks) and "Pot sortir / No pot sortir del
centre", never the name, the photo, the birth date or *why* the student may leave. Plus the time of
the check and a CSS-animated "live" dot, which tell the real page from a screenshot. A code that is
not valid shows "Carnet no vàlid" and nothing else. The page shows no photo, so the protection
against a swapped photo is physical: the ink stamp over the photo, and laminating.

**Hardening:** `X-Robots-Tag: noindex, nofollow, noarchive`, `Cache-Control: no-store`,
`Referrer-Policy: no-referrer`, `sitemap=False`, no listing anywhere. Failed checks (unknown or no
longer valid codes) are limited per client address: after `MAX_FAILED_CHECKS` (20) within
`FAILED_CHECKS_WINDOW` (10 min) every check from it gets a 429 until the window passes. Valid checks
are never counted, so a teacher scanning a whole queue is never stopped. The counter lives in each
worker process's memory, which is enough against guessing a 192-bit code; behind a reverse proxy
it needs Odoo's `proxy_mode` so `remote_addr` is the client's, not the proxy's.

The page is rendered in the centre's language (Catalan), like the card itself.

## Model changes

| Model | Field / method | Notes |
|---|---|---|
| `ems.level` | `card_color` (Selection, stored compute, `readonly=False`) | The level's colour on the card, one of a closed pastel palette (`CARD_PALETTE` in `models/curriculum/level.py`, key → hex). The palette has no red or green, which the card keeps for the exit block, so no level can be confused with it. Computed from the acronym when the level is created (`CARD_COLORS` for the official levels, grey for any other) and editable afterwards in the level form. Not in `data/cat/ems.level.csv`, so an upgrade never reverts a colour the centre changed. |
| `res.company` | `ems_card_stamp` (Image) | The centre's stamp, uploaded in Settings > EMS > Center Data. |
| `res.config.settings` | `ems_card_stamp` (related) | |
| `res.partner` | `can_print_student_card` (Boolean, non-stored, `depends_context('uid')`) | Reads the Actions dropdown entry's `invisible=`. |
| `res.partner` | `can_leave_centre` (Boolean, non-stored) | `is_adult or auth_leave`. Not stored, since `is_adult` depends on today's date. |
| `res.partner` | `auth_leave` (Boolean, stored compute, `contact.py`) | Accepted *Leave the Centre* authorization in the year in force; the same compute as the other `auth_*` flags (see [Authorizations](../enrollment/authorization.md)). |
| `ems.authorization.template` | `auth_type` value `leave` | *Leave the Centre*. The centre creates the template itself (its legal text) from Academic management. |
| `res.partner` | `action_print_student_card()` | Keeps the students (`contact_type == 'student'`) the user acts on, sorted by name, and returns the report action. Raises a `UserError` when none is left. |
| `res.partner` | `_get_student_card_values()` | Per-student values for the template (document, level, colour, study acronym, course year). |
| `ems.group` | `can_print_student_cards`, `action_print_student_cards()` | Same, for every student whose main group is this one. |
| `res.partner` | `ems_card_token`, `ems_card_course_id` (`groups='base.group_system'`, sudo only) | The card's code and the academic year it was issued for. |
| `res.partner` | `_ems_ensure_card_token(renew=False)`, `_ems_card_check_url()`, `_ems_card_from_token()`, `_ems_card_check_values()` | Issue/keep/renew the code; the QR's URL (False without a valid code); the student a valid code belongs to; what the check page shows. |
| `res.partner` | `action_revoke_student_card()` | New code for the students the user may print a card for; `UserError` when none. |

## Access control

Who may print a card is who may act on the student, the same rule as the student's other actions
(`ems.student.scope.mixin._scope_acts_on_student`, issue #483):

| Role | Students |
|---|---|
| Academic admin, Secretary, Head of Studies | Every student |
| Tutor, and the Department/Seminar Chief, Head of Studies and Director above them (`tutor_scope_user_ids`) | That tutor's students |
| Any other teacher | None (the entry is hidden; the server action refuses) |

The check is made again on the server in `action_print_student_card()`: a list selection, or a
group the user isn't the tutor of, never prints a card the user could not print from the form.
Revoking a card (`action_revoke_student_card()`) follows the same rule. The check page needs no
login at all: the code is the credential (see "Card check page" above).

## Layout notes

- Paper format `ems.paperformat_student_card`: A4 portrait, small margins, no header/footer
  (`web.basic_layout`, not `external_layout`).
- Cards are laid out with a table (two cells per row), not flexbox or grid: wkhtmltopdf's WebKit
  lays neither out. The band's two blocks are one table with `border-collapse: separate` and a
  horizontal `border-spacing`, each cell with its own `border-radius`.
- Soft colours throughout: pastel backgrounds with dark text (the level and exit blocks), grey labels.
  The report layout borders tables, rows and cells; the card's stylesheet resets all of them. Each row has `page-break-inside: avoid`, so a card is never split across two
  sheets.
- Double-sided printing: each sheet of fronts (up to ten cards) is followed by its sheet of backs,
  flipped on the long edge. A back row lists its cards right to left (`[::-1]`), so every back, and
  its own QR, lands behind its own front, and an odd last card's back sits on the right; left and
  right margins are equal so the columns line up.
  Cards are `box-sizing: border-box` so five 54 mm rows fit an A4 sheet.
- The barcode uses Odoo's own `barcode` QWeb widget (an inline PNG), Code128, from the IDALU. No
  barcode is printed for a student without IDALU. It is rastered at 400 x 80 px for a 36 x 8 mm print
  (about 280 dpi): drawing it is most of the render time, and 600 x 100 cost a third more for nothing
  a reader can tell apart.
- The centre's address is one sub-template (`ems.report_student_card_address`), shared by both sides.
- Measured on this box's largest group (34 students, cold): access check 0.08 s, action 0.04 s, HTML
  1.0 s, PDF 3.0 s (146 KB), 90 queries for the whole render.

## Manual screenshots

`test_capture_student_card_check_page` captures the check page (valid and revoked) at phone width
for the teachers' manual.

`tests/test_docs_screenshots_student_card.py` (tagged `-standard`) captures the manuals' screens with
invented students and the simulated stamp (`tests/common.py`'s `draw_invented_centre_stamp()`); the
card example in `docs/assets/secretary/student-card-example.png` is cropped from a PDF rendered with
the same kind of fixtures.
