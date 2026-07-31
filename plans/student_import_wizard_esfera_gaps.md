**Status: current, not yet actioned (2026-07-31) — Gap 1 turned out not to be a gap; Gap 2 still open, pending a concrete example from the developer.**

# `ems.student_import_wizard` gaps found against a real Esfera export

While closing the wizard's remaining browser-tour coverage gap (see
`static/tests/tours/student_import_wizard_tour.js`'s `ems_student_import_wizard_success`), the
developer shared a real Esfera/SAGA export (`alumnes_esfera.xlsx`, 119 real students, since
anonymized/inspected and deleted — see chat history 2026-07-31 for the anonymization method:
a script that only ever printed aggregate/non-personal stats, never a real cell value).
Structural inspection (still non-personal: header names, distinct categorical values, format
patterns) surfaced two apparent edge cases in the actual production file shape.

## Gap 1 — `Tipus de document d'identitat` can be `TIS` — NOT ACTUALLY A GAP (corrected 2026-07-31)

Originally reported as unhandled after a too-quick read of `_process_row`'s `student_data`
dict. **Wrong** — the very next line after `document_id`/`passport_id` already handles it:
```python
'document_id': docs.get('DNI') or docs.get('NIE'),
'passport_id': docs.get('PASS') or docs.get('Passaport'),
'medical_id': docs.get('TIS'),
```
`res.partner.medical_id` (`models/contacts/contact.py`) already exists for exactly this -
confirmed correct by the developer's colleague. It had no explicit test locking it in though
(only the DNI/NIE/PASS paths were tested) - added
`test_process_row_tis_document_type_maps_to_medical_id` (also covers the multi-document case:
a student with both a DNI and a TIS in the same row, `' - '`-joined). No code change needed.

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

**Developer asked their colleague 2026-07-31; answer so far:** both readings are plausible and
either would be fine to import — "más contactos" (additional tutors/family members) and "más
teléfonos o correos para un contacto" (multiple channels for the same tutor) were both
confirmed as things worth capturing. This confirms *intent* but not which one the 3rd/4th
`" - "`-joined part in this specific column actually is structurally — those two readings need
different fixes (a new tutor-slot vs. extra fields on the existing family contact), and I have
no way to tell them apart without seeing the real shape (I no longer have the file — deleted
per the developer's own instruction after the anonymization pass).

**Next step, still needed before implementing:** a concrete example with **invented** values
showing what a real 3-4-part `Contacte ... - Valor` cell looks like structurally, e.g.
`"612345678 - tutor@example.com - 934445566 - ???"` — just the shape/pattern, no real numbers
or names needed. That's enough to design the fix without touching real data again.

## Why this is a plan file, not a fix

Per `CLAUDE.md`'s "Full-scenario exploration before implementing" rule: don't guess how to fix
Gap 2 - it needs to know the real shape of a 3-4-part value before a fix can be correctly
designed, not just technically possible. Delete this file once actioned (fixed, or explicitly
deferred with a decision recorded elsewhere) per `plans/`' own lifecycle rule.
