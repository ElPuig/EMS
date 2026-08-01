**Status: not yet implemented — design note only, picked up 2026-08-01, still current as of that date.**

# New "Transfer" departure reason + reason-aware "Archived" ribbon for teachers

## Request (verbatim context)

The developer, right after this session's ribbon rollout (which added a generic "Archived"
ribbon to `hr.employee`'s form): *"Cuando archivo se me pide el motivo, necesito uno nuevo:
'Traslado' porque a los profesores se les puede asignar un centro distinto cada curso... en el
ribbon de archivado, haremos como con los alumnos: pondremos como texto el motivo del archivado.
Nos irá genial para ver rápido si el profesor se ha jubilado (retired) o si ya estuvo con
nosotros y ahora vuelve (traslado)."*

Two distinct asks:

1. **A new `hr.departure.reason` record**, English label suggestion: **"Transfer"** (reads
   naturally alongside Odoo's existing native reasons - see below; ca "Trasllat" / es "Traslado"
   read naturally too, but confirm wording with the developer before finalizing, since they
   explicitly invited a better word if one exists).
2. **The employee form's "Archived" ribbon should show the actual departure reason as its
   text** (e.g. "Retired", "Transfer"), the same idea as this session's `res.partner` fix
   (Alumni/Withdrawal instead of a generic "Archived", based on `contact_type`).

## What already exists (native Odoo, unmodified by EMS)

- `hr.departure.reason` (`hr/models/hr_departure_reason.py`) — a plain configurable model, no
  EMS customization found (`grep`-confirmed 2026-08-01: no `departure_reason`/`hr.departure.reason`
  hits anywhere in `models/`, `views/`, or `data/`).
- Native seed data (`hr/data/hr_data.xml`): `hr.departure_fired` ("Fired"),
  `hr.departure_resigned` ("Resigned"), `hr.departure_retired` ("Retired").
- `hr.departure.wizard` (`hr/wizard/hr_departure_wizard.py`) is what already asks for the reason
  when an employee is archived (confirmed this is the existing flow the developer means by
  "cuando archivo se me pide el motivo" - not something EMS built, native Odoo behavior already
  in place for `hr.employee`).
- This session added a plain, non-reason-aware ribbon to `hr.employee`'s form
  (`views/community/employee/form.xml`, mutually exclusive with the existing "Pending
  identification" one via `invisible="active or pending_identification"`) - this is the ribbon
  that needs to become reason-aware.

## Key technical wrinkle to resolve before implementing

Unlike `res.partner.contact_type` (a fixed `Selection` with exactly two archived-relevant values,
which is why two hardcoded `<widget name="web_ribbon" invisible="contact_type != 'alumni'"/>` /
`'withdrawal'` variants worked cleanly), **`departure_reason_id` is a `Many2one` to a
model an admin can add records to** (this very request adds one: "Transfer"). Read
`web/static/src/views/widgets/ribbon/ribbon.js`'s `extractProps` (checked 2026-08-01): the
`title` attribute is read as a **literal static string** at view-compile time
(`attrs.title || attrs.text`), not evaluated as a per-record field expression - there is no
built-in "bind the ribbon's text to a field's current value" option.

Two ways to actually get the reason's own name to show, worth deciding when this is picked up
(not decided here):

- **(a) One hardcoded ribbon widget per current reason**, `invisible="departure_reason_id != id"`
  for each (mirroring the `res.partner` approach) - simple, zero new code, but silently stops
  covering a *future* new departure reason someone adds later without a matching view update.
  Given this model is meant to be admin-extensible, this brittleness is a real downside to weigh.
- **(b) A small custom OWL widget** (a thin wrapper reusing `web.Ribbon`'s template/component but
  accepting a field name and rendering that record's current value as the ribbon text) - more
  code up front, but automatically covers any reason an admin adds later, no view maintenance
  needed per new reason. Given this codebase already has several custom JS widgets in
  `static/src/js/backend/` (e.g. `role_color_tags_field.js`, `hex_color_tags_list.js`), this is a
  realistic, consistent option, not exotic for this project.

Recommend (b) given the model's extensibility, but this is exactly the kind of tradeoff to
confirm with the developer before writing code, per this project's standing practice of not
guessing on ambiguous design calls.

## Where the new "Transfer" reason record should live

Per `CLAUDE.md`'s data-folder conventions: this isn't a one-centre customization (any school using
EMS could have teachers move between centres), so it likely belongs in `data/main/` (EMS-owned,
`ems.` prefix) rather than `data/custom/` - but confirm this reasoning holds before committing to
it; if a specific centre's existing `data/custom/hr.departure.reason.csv` (or similar) already
exists it should go there instead. (2026-08-01 grep found no existing `data/` file for this model
at all - would be a new file either way.)

## Rough shape of the work, once design questions above are resolved

1. **D (Spec):** stub/update `docs/en/developers/employees/employee.md` (or wherever
   `hr.employee` is documented) and the relevant admin doc(s) - likely `docs/{en,ca,es}/admin/`
   (whoever manages teacher records; check the existing employee docs' role table).
2. **T (Red):** a `TransactionCase` test confirming the "Transfer" reason record exists and is
   selectable; a browser tour opening an archived teacher with each reason and confirming the
   ribbon shows the right text (mirroring `test_group_tour.py`'s pattern for the group ribbon, or
   `res.partner`'s Alumni/Withdrawal if a tour already exists for that).
3. **T (Green):** the new data record + whichever ribbon approach (a/b above) was chosen.
4. **N:** i18n (`i18n/{ca,es}_ES.po`) for the new reason's name and any new ribbon-widget label
   text, verified via `psql` per `CLAUDE.md`'s i18n verification method.
5. **Close:** changelog entry, delete this plan file once implemented.
