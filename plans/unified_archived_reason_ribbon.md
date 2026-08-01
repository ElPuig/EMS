**Status: not yet implemented — design note only, drafted 2026-08-01, expanded same day to also
cover a new student "Expulsion" outcome, still current as of that date. Supersedes an earlier,
narrower `plans/employee_departure_reason_ribbon.md` (deleted) that only covered teachers - this
one covers the unified design across teachers AND students, form AND kanban, plus the new
Expulsion archival outcome for students that came out of finalizing colors.**

# One reusable "archived reason" ribbon (+ a new student Expulsion outcome), for students and teachers, form and kanban

## Request history (verbatim context, in order)

1. Right after this session's plain "Archived" ribbon rollout (19 models + `res.partner`'s
   Alumni/Withdrawal special case), the developer asked for the same idea on teachers: *"Cuando
   archivo se me pide el motivo, necesito uno nuevo: 'Traslado'... en el ribbon de archivado,
   haremos como con los alumnos: pondremos como texto el motivo del archivado."*
2. Then, noticing students *also* have a ribbon on their **Kanban card** (not just the form -
   see "What already exists" below) that isn't reason-aware yet either: *"veo que también hay un
   ribbon para la tarjeta Kanban, esa también me gustaría personalizarla."*
3. Then, tying both together: *"entiendo que has hecho ribbon custom para los dos motivos de
   archivado [en alumnos] y ahora propones hacer un widget nuevo para los profesores... Quizás
   valdría la pena que ese mismo widget funcione para profesores y alumnos... Dale una vuelta a
   ver como lo podemos hacer, y que aplique al kanban y a la ficha."*

This file captures the resulting design synthesis (thought through 2026-08-01, not yet built).

## What already exists today (as of 2026-08-01)

- **`res.partner` form** (`views/community/contact/form.xml`): this session replaced the native
  generic `web_ribbon` (`base.view_partner_form`) with **three** hardcoded ribbon widgets -
  native "Archived" (now `invisible="active or contact_type in ('alumni','withdrawal')"`), plus
  new "Alumni" and "Withdrawal" ones, each `invisible` on a specific `contact_type` value.
- **`res.partner` kanban** (`views/community/contact/kanban.xml`, inherits
  `base.res_partner_kanban_view`): still shows the **native, generic** "Archived" ribbon
  unmodified - confirmed 2026-08-01 by reading `base/views/res_partner_views.xml` line 407
  (`<widget name="web_ribbon" title="Archived" .../>` inside the kanban arch) and confirming
  EMS's own `kanban.xml` doesn't touch it. This is the ribbon referenced in ask #2 above.
- **`hr.employee` form** (`views/community/employee/form.xml`): this session's plain "Archived"
  ribbon (`invisible="active or pending_identification"`), not yet reason-aware - the subject of
  ask #1. `hr.departure.reason` (native Odoo, `hr/models/hr_departure_reason.py`) is what the
  departure wizard already asks for on archive; no EMS customization of it exists yet (no new
  "Transfer" reason record).
- `hr.employee`'s own kanban already has an unrelated custom badge ("Pending identification",
  this session's earlier work, `views/community/employee/kanban.xml`) - a **different concept**
  (pre-hire placeholder, not an archived-reason indicator) and deliberately **out of scope**
  here; don't conflate the two.

## The unifying design

### 1. One same-shaped Char field per model: `archived_reason_label` (+ `archived_reason_color`)

Each model exposes two plain `Char` fields - the label text and a hex color - both empty/`False`
when there's nothing specific to show (not archived at all, or archived with no specific reason
known):

- **`res.partner`**: `archived_reason_label` needs a real `@api.depends('contact_type')` compute
  - `'alumni'` → `_("Alumni")`, `'withdrawal'` → `_("Withdrawal")`, anything else → `False`.
  **Confirmed with the developer 2026-08-01 this can't be a plain `related=`**: `contact_type` has
  six possible values and only two of them are ribbon-worthy, so something has to decide which -
  a `related=` field always mirrors its target 1:1, it has no way to express "but only for these
  two values, otherwise nothing." `archived_reason_color` is a compute too, returning one of two
  fixed hex constants (see the "Colors" section below) for the same two values.
- **`hr.employee`**: **both** fields can be plain one-line `related=` fields -
  `archived_reason_label = fields.Char(related='departure_reason_id.name')` and
  `archived_reason_color = fields.Char(related='departure_reason_id.color')` (the second needs
  the new `color` field added to `hr.departure.reason` first - see "Teachers' color" below).
  This works cleanly here specifically because *every* departure reason is ribbon-worthy - there's
  no subset-filtering need the way `contact_type` has, which is exactly why `related=` fits one
  model and not the other. Confirm `hr.departure.reason.name`'s exact field name before relying on
  this (expected to be `name`, matching the model's own form view already read 2026-08-01).

Using a compute for one model and a `related=` for the other is fine and expected - what makes
the shared widget possible is that **both fields end up the same shape** (empty vs. a plain hex
string / translated label), not that they're computed the same way.

### 2. One reusable custom **field widget** (not a `<widget name="web_ribbon">` view-widget)

Investigated 2026-08-01: Odoo's built-in `web_ribbon` (`web/static/src/views/widgets/ribbon/ribbon.js`)
takes its `title` as a **static string read at view-compile time** (`extractProps`: `attrs.title
|| attrs.text`) - there is no way to bind it to a field's live value per record. That's fine for
the today's hardcoded Alumni/Withdrawal pair (a fixed, small Selection), but doesn't scale to
`hr.departure_reason_id`, which is a Many2one an admin can keep adding records to - a hardcoded
ribbon per reason would silently stop covering any reason added after the view was last edited.

Instead: build a small **custom field widget** (same category as this project's existing custom
widgets in `static/src/js/backend/`, e.g. `role_color_tags_field.js`) that wraps/reuses
`web.Ribbon`'s template but takes its text from **the field it's bound to**, e.g.:

```xml
<field name="archived_reason_label" widget="ems_archived_reason_ribbon"
       options="{'color_field': 'archived_reason_color'}" invisible="active"/>
```

Because this is a genuine field widget (not the separate `view_widgets` mechanism `web_ribbon`
itself uses), the exact same `<field .../>` declaration works **unmodified** in a `<form>`'s
`<sheet>` and inside a `<kanban>` view's `<templates>` block - Odoo's field-widget rendering
isn't view-type-specific the way the current `view_widgets`-registry ribbon is. This is what
directly answers "que aplique al kanban y a la ficha" with one implementation, not two.

Sketch (not yet written/tested):

```js
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class EmsArchivedReasonRibbon extends Component {
    static template = "ems.ArchivedReasonRibbon"; // reuse web.Ribbon's own template/markup, or a
                                                    // near-identical local one if reuse proves awkward
    get text() {
        return this.props.record.data[this.props.name];
    }
    get colorHex() {
        const colorField = this.props.colorField; // from options.color_field
        return colorField ? this.props.record.data[colorField] : null;
    }
}
EmsArchivedReasonRibbon.props = { ...standardFieldProps, colorField: { type: String, optional: true } };

registry.category("fields").add("ems_archived_reason_ribbon", {
    component: EmsArchivedReasonRibbon,
});
```

Exact shape (reusing `web.Ribbon`'s OWL component/template directly vs. a near-duplicate local
one, how `bg_color` is decided, whether the widget itself checks `active` or callers must add
`invisible="active"` explicitly as shown above) needs actually prototyping against a real
form+kanban pair before calling the sketch final - treat the above as a starting point, not a
spec to copy verbatim.

### 3. Colors - always a hex string, never a Bootstrap `text-bg-*` class

Settled 2026-08-01: the widget always applies its color as an **inline hex background**
(`archived_reason_color`), never a Bootstrap contextual class - this is what lets one mechanism
serve both a couple of fixed constants (students) and a genuinely admin-configurable per-record
color (teachers) without the widget needing two different code paths.

**Students - CONFIRMED 2026-08-01, final:**
- **Alumni** - `#4C7A5D` (muted, dark-leaning green).
- **Withdrawal** - `#C97B3D` (the burnt-orange option; the light-purple alternative went to
  teachers' "Transfer" instead, see below).
- **Expulsion** - a **new** outcome, see "New: student Expulsion" section below - uses the same
  default/generic red as a plain archived record (no separate hex constant needed; this is
  exactly the widget's own no-color-set fallback, see next paragraph). Developer's own reasoning
  for reusing that specific red: *"que te despidan es bastante bestia, ese color estará bien
  justificado... nosotros podríamos llegar a expulsar a un alumno, así que vamos a usar ese rojo
  para un alumno expulsado."*

No fallback-ribbon color question for `family`/`provider`/`applicant`: the native "Archived"
ribbon already covers those untouched (still Bootstrap `text-bg-danger`) - only
alumni/withdrawal/expulsion route through the new field+widget.

**The widget needs a built-in default red** (e.g. `#dc3545`, Bootstrap's own `--bs-danger`) for
when `archived_reason_label` has a value but `archived_reason_color` doesn't - this is what makes
"Fired" (teachers, below) and "Expulsion" (students, above) work with **zero extra color
configuration**: leave the per-record `color` empty (teachers) / don't define a separate
constant (students, compute returns `False` for color but a real label), and the widget's own
fallback renders the same red the plain "Archived" ribbon already uses everywhere else - visually
consistent, and the one case where "no specific color chosen" is a deliberate, correct outcome
rather than a config gap to fill in.

**Teachers - CONFIRMED 2026-08-01, final** (add a `color` field to `hr.departure.reason` via EMS
`_inherit`, reusing the **exact same hex color-picker widget already established in this
codebase** for other simple config models - e.g. `ems.attendance_status`'s `<field name="color"
widget="color" class="ems_color_swatch"/>`, `models/attendance/attendance_status.py`;
`hr.departure.reason` today, native Odoo, only has `sequence`/`name`/`reason_code`, so this is a
clean addition, no conflict with anything native):

| Reason | Color | Hex |
|---|---|---|
| Transfer (new, see original ask #1) | Light lavender purple | `#B8A1D9` |
| Retired | "Elegant blue" - proposed, confirm before implementing | `#2E6C8E` (refined steel/teal blue) |
| Resigned | Same orange as students' Withdrawal | `#C97B3D` |
| Fired | Leave `color` **empty** on this record | Falls back to the widget's default red - *"dejemos el rojo predeterminado (que te despidan es bastante bestia, ese color estará bien justificado)"* |

## New: student "Expulsion" as a distinct archival outcome (raised 2026-08-01, expands scope beyond the ribbon)

While finalizing colors, the developer realized the same "severity deserves the harsh red"
reasoning that justifies Fired (teachers) applies to an analogous case for students - being
**expelled**, which today has **no distinct representation at all**: archiving a student only
ever produces `contact_type` = `'alumni'` (graduation) or `'withdrawal'` (leaving/withdrawn) via
`res.partner._ems_convert_to_ex_student()` - there is no "this student was expelled" outcome to
select today.

**Do not confuse this with the existing, unrelated `kicked_out` field** (see
`project_strike_kicked_out.md` memory / `models/coexistence/strike.py`) - that's a per-session
disciplinary action tied to a single strike/class session, not a permanent institutional
archival outcome. This new "Expulsion" is a third, permanent sibling to Alumni/Withdrawal - a
different scope entirely, even though the everyday word ("expulsado"/"kicked out") overlaps.

**Requested behavior, verbatim:** *"cuando archivamos a un alumno, aparece el formulario con los
motivos y se debe permitir escoger entre withdrawal (que puede ser voluntaria o de oficio, eso lo
pondremos en los comentarios) o expulsión. Ojo, que el texto del botón debería adaptarse a la
opción escogida."* Breaking that down:

1. **A new selectable outcome** on `ems.withdrawal_wizard`'s form - a choice between "Withdrawal"
   and "Expulsion" (needs its own field on the wizard, e.g. `exit_kind` `Selection` -
   `[('withdrawal', 'Withdrawal'), ('expulsion', 'Expulsion')]` - naming TBD when implemented).
2. **Voluntary vs. administrative ("de oficio") withdrawal is explicitly NOT a separate field or
   state** - the developer was clear this distinction belongs in the wizard's free-text
   notes/comments only, not modeled data. Don't over-engineer this into a second Selection.
3. **The confirm button's label must change based on the choice** - e.g. "Confirm withdrawal" vs
   "Confirm expulsion". Odoo buttons don't support a fully dynamic `string=` bound to a field
   expression - the standard, native way to do this is **two buttons**, each with its own fixed
   label, mutually `invisible` on the `exit_kind` value (e.g. `invisible="exit_kind !=
   'withdrawal'"` / `invisible="exit_kind != 'expulsion'"`), same pattern already used elsewhere
   in this codebase for state-dependent buttons (e.g. `ems.attendance_correction`'s Accept/Reject
   in `views/attendance/attendance_correction/form.xml`) - not a hack, the idiomatic Odoo answer
   to "the button text should adapt to the option chosen."
4. **Full-scenario exploration required before implementing** (per `CLAUDE.md`'s standing rule,
   this is a real model change, not cosmetics): whatever the new outcome ends up being modeled as
   (most likely a third `contact_type` value, e.g. `'expelled'`, mirroring how `'alumni'`/
   `'withdrawal'` already work) - grep and read **every** place `contact_type` is filtered/branched
   on before adding it (portal-access domains, security rules, other wizards, reports) to make
   sure a new value doesn't silently fall into an "else" branch that assumed only the current six
   values exist. This is exactly the kind of change CLAUDE.md's "full-scenario exploration before
   implementing" rule exists for - do not guess which branches need updating, trace them all.
5. Once modeled, `res.partner`'s `archived_reason_label`/`archived_reason_color` computes (see
   above) need a third branch: `'expelled'` → label `_("Expelled")` (or whatever final English
   wording is chosen - not decided here), color `False` (→ widget's default red fallback).

### 4. Apply it in all four places - confirmed 2026-08-01, both models, both view types

*"Lo quiero en profesores y alumnos, tanto en kanban como en ficha (veo que el kanban de los
profesores no lo muestra ahora mismo)."* - settled, no longer an open question:

- `views/community/contact/form.xml`: replace the current 3-ribbon block with one
  `<field name="archived_reason_label" widget="ems_archived_reason_ribbon"
  options="{'color_field': 'archived_reason_color'}" invisible="active"/>` (dropping the now-
  redundant hardcoded Alumni/Withdrawal/native-Archived trio built this session - this plan
  **supersedes** that implementation, not just adds to it).
- `views/community/contact/kanban.xml`: same field+widget, inside the kanban `<templates>` block
  - answers ask #2. Will need `archived_reason_label`/`archived_reason_color` added to the
    `<field>` list at the top of the kanban's own `<xpath expr="//kanban" position="inside">`
    block (same "must be declared as a kanban field to be usable" rule already hit earlier this
    session for `hr.employee`'s kanban).
- `views/community/employee/form.xml`: replace the plain `invisible="active or
  pending_identification"` ribbon with the same field+widget pattern, still excluding the
  unrelated "Pending identification" ribbon via the same mutual-exclusion condition.
- `views/community/employee/kanban.xml`: same field+widget added here too (currently shows
  nothing for archived state at all, per the developer's own observation above) - alongside the
  existing "Pending identification" badge already there (different concept, same mutual-exclusion
  logic as the form).

## New "Transfer" departure reason (ask #1, still pending regardless of the widget design)

Unchanged from the original narrower plan: add a new `hr.departure.reason` record (suggested
English label "Transfer"; ca "Trasllat" / es "Traslado" as natural translations, confirm wording
with the developer first). Likely `data/main/` per `CLAUDE.md`'s data-folder conventions (general
EMS feature, not one centre's own config) - confirm this reasoning still holds when picked up.

## Rough shape of the work, once the design above is confirmed

This is now really two coupled pieces of work - the ribbon/widget/colors (mostly settled) and the
new student Expulsion outcome + wizard UX (needs the full-scenario exploration above before any
code is written). Suggest doing the exploration + wizard change first (it changes what
`archived_reason_label`'s compute needs to branch on), then the shared widget, so the widget
isn't built against an incomplete picture of the values it needs to render.

1. **D (Spec):** update `docs/en/developers/contacts/contact.md` (or wherever `res.partner` is
   documented) and `docs/en/developers/employees/employee.md` with the shared field+widget
   design and the new Expulsion outcome; admin doc updates wherever these models' manuals live
   (the withdrawal wizard's admin doc needs the new choice + adapting button documented too).
2. **T (Red):** backend tests for the `contact_type` full-scenario exploration findings (whatever
   it turns up), for both `archived_reason_label`/`archived_reason_color` computes (empty when
   active/no-reason, correct text+color per case including the new expulsion branch), for the
   wizard's new field + button-label switching; a browser tour per model covering **both** form
   and kanban ribbon rendering, plus a tour step exercising the withdrawal wizard's new
   Withdrawal/Expulsion choice and confirming the right button shows (a clean `./upgrade.sh`
   proves the arch is valid, not that a custom OWL field widget or a conditional button actually
   renders correctly in the browser - exactly the gap this project's tour-coverage convention
   exists to catch).
3. **T (Green):** the full-scenario-informed model change (new `contact_type` value or
   equivalent), the wizard's new field + two mutually-`invisible` confirm buttons, the
   `archived_reason_label`/`archived_reason_color` fields, the shared widget, the four view
   changes above, the new "Transfer" data record + `hr.departure.reason.color` field.
4. **N:** i18n for "Transfer"/"Trasllat"/"Traslado", "Expulsion" (or whatever final wording),
   the wizard's new button labels, and any new widget-related translatable strings, verified via
   `psql`.
5. **Close:** changelog entry, delete this plan file once implemented.
