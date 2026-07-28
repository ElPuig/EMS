# PLAN — Two data-quality gaps in the Esfera/SAGA student import

> **Status: flagged during the `ems.student_import_wizard` DTON pass (Phase 5, 2026-07-27/28),
> not implemented.** This is not a design for new work — it's an open question for whoever
> owns the Esfera/SAGA import to answer before any fix is written. Nothing below has been
> built. Verify file/line references against current code before acting, since the branch
> may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> both questions are resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/contacts/student_import_wizard.md`).

## Gap 1 — Family-contact dedup only matches by document number

`_get_or_create_family` (`models/contacts/student_import_wizard.py`) already carries its own
docstring flagging this:

```python
def _get_or_create_family(self, name, doc_num, phone, mobile, email, address_data):
    """Find or create the family contact for a tutor row.

    KNOWN LIMITATION: dedup only matches on doc_num (document_id/passport_id).
    A tutor row with no document number always creates a new family partner —
    there is no name/phone/email fallback match, so re-importing the same file
    for a documentless tutor creates one duplicate family contact per import
    run. Flagged, not fixed, in this DTON pass — see student_import_wizard.md.
    """
```

**What this means concretely:** any tutor row in the Esfera export that has no document
number (`doc_num` falsy) skips the dedup `search()` entirely and always
`self.env['res.partner'].create(...)`s a fresh family contact — every time the same file (or
an updated export covering the same students) is re-imported. A school that re-imports
periodically (start of year, mid-year updates) accumulates one duplicate family-contact
partner per documentless tutor per import run.

Regression test `test_get_or_create_family_without_document_always_creates_new`
(`tests/test_student_import_wizard.py`) locks in the *current* behavior so any future fix is
a deliberate, tested change — not a silent behavior shift.

### Open questions

1. How common are documentless tutor rows in real Esfera exports for this centre? If rare,
   urgency is low; if common, this could already be producing a meaningful number of
   duplicate family contacts in production — worth a query counting family-type partners
   with no `document_id`/`passport_id` and near-duplicate names/phones.
2. If a fallback match is added, what should it match on — exact name + phone? Name +
   email? Any fallback risks **false-positive merges** (two different people who happen to
   share a name), which is arguably worse than a duplicate contact. Needs a real decision on
   acceptable false-positive risk, not just a mechanical "add a name match."
3. Alternative: instead of a fuzzier dedup match, could the import surface documentless
   tutor rows as a warning/report for manual review, leaving auto-creation as the fallback
   only when no manual match is confirmed?

## Gap 2 — Unmatched Esfera group code fails silently into a note, not an error

`_process_row` (same file) searches for the student's group by Esfera's own group code:

```python
group = self.env['ems.group'].search([('external_id', '=', esfera_code)], limit=1)
```

If no `ems.group` has that `external_id`, `group` is simply falsy — the row still proceeds
(student gets created/updated), and `_build_student_notes` appends a note into the student's
`comment` field (`f"Grup Classe (SAGA): {esfera_code}"`) instead of the row being reported in
`stats['errors']` (the result summary the secretary actually reviews after an import).

**What this means concretely:** a student whose Esfera group code doesn't match any
`ems.group.external_id` (typo in the source system, a group not yet created in EMS, a group
whose `external_id` was never set) is silently imported *without* a placement, with the only
trace being a note buried in their `comment` field — easy to miss, since the import's
top-level result summary (what a secretary actually reads) won't flag anything wrong.

### Open questions

1. Was this intentional — i.e. is "import the student anyway, note the mismatch for later
   manual placement" the desired behavior, given that not every group may exist in EMS yet
   at import time? Or should an unmatched group code be a hard error/warning surfaced in
   `stats['errors']` (or a new `stats['warnings']` bucket) so it's visible in the result
   summary without having to open each student's record?
2. If it should surface in the summary: does that change existing operational habits (e.g.
   if secretaries already know to check `comment` fields after an import), or would it be a
   pure improvement with no workflow disruption?

## Where this is also documented

`docs/en/developers/contacts/student_import_wizard.md` — both gaps documented there under
their respective sections — stays even after this plan file is deleted; update it if either
resolution differs from what's written there today.
