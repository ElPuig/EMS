**Status: current, not yet actioned (2026-07-31).**

# `ems.student_import_wizard` gaps found against a real Esfera export

While closing the wizard's remaining browser-tour coverage gap (see
`static/tests/tours/student_import_wizard_tour.js`'s `ems_student_import_wizard_success`), the
developer shared a real Esfera/SAGA export (`alumnes_esfera.xlsx`, 119 real students, since
anonymized/inspected and deleted — see chat history 2026-07-31 for the anonymization method:
a script that only ever printed aggregate/non-personal stats, never a real cell value).
Structural inspection (still non-personal: header names, distinct categorical values, format
patterns) surfaced two real, currently-unhandled edge cases in the actual production file
shape. Neither raises an error today — both fail silently, losing data rather than crashing.

## Gap 1 — `Tipus de document d'identitat` can be `TIS`, not just `DNI`/`NIE`/`PASS`

`_parse_documents` (`models/contacts/student_import_wizard.py`) builds `dict(zip(types,
numbers))` from the raw column pair, then `_process_row` only reads it via:
```python
'document_id': docs.get('DNI') or docs.get('NIE'),
'passport_id': docs.get('PASS') or docs.get('Passaport'),
```
The real file has rows with `TIS` (Targeta d'Identificació Sanitària, presumably a healthcare-
system ID used as a fallback when a student has no DNI/NIE/passport yet - plausible for a
recently-arrived student). A student whose only document is `TIS` gets **neither**
`document_id` nor `passport_id` set — the document is parsed into the `docs` dict but then
silently dropped.

**Not yet decided:** should `TIS` map to `document_id` (alongside DNI/NIE), to a new/different
field, or be surfaced as a warning (matching the existing `stats['warnings']` pattern already
used for the "no matching group"/"tutor without document number" cases)? Ask the developer
before picking one — this needs to know what `TIS` actually represents in this centre's real
population before deciding where it belongs.

## Gap 2 — `Contacte ... - Valor` can have more than 2 " - "-joined parts

`_parse_contact_value` only reads `parts[0]` (phone) and `parts[1]` (email):
```python
def _parse_contact_value(self, raw):
    if not raw:
        return None, None
    parts = [p.strip() for p in raw.split(' - ')]
    phone = parts[0] if parts else None
    email = parts[1] if len(parts) > 1 else None
    return phone, email
```
The real file has rows with **3 and 4** `" - "`-joined parts in this column (confirmed via
aggregate part-count stats, never the actual values). Whatever is in parts 3+ is silently
discarded today - unknown what it actually represents (a second phone number? an extension?
a third contact channel?) without looking at a real example, which needs the developer's
involvement since it requires reading real personal data.

**Not yet decided:** needs the developer to identify what a 3-4-part value actually represents
in a real row (with the file back in hand, or a fresh anonymized sample) before any fix can be
designed - could be "ignore extra parts is fine, they're redundant," or "parts 3+ carry real
data currently being lost."

## Why this is a plan file, not a fix

Per `CLAUDE.md`'s "Full-scenario exploration before implementing" rule: don't guess whether a
found gap is worth fixing or how - both of these need the developer's domain knowledge (what
`TIS` means locally, what a 3rd/4th contact-value part represents) before a fix can be
correctly designed, not just technically possible. Delete this file once actioned (fixed, or
explicitly deferred with a decision recorded elsewhere) per `plans/`' own lifecycle rule.
