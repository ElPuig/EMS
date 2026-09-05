Status: not started - found while investigating point 2.3 of a developer bug report on the
"Add contact" wizard (2026-09-05). Developer decided to leave it as-is for now (asked, chose
"Dejarlo como está por ahora" over migrating). Kept here in case it's revisited later.

# Problem

347 of 1168 `res.partner` records with `contact_type='family'` (~30%) in this dev DB have no
`firstname` at all - only a single word stored in `lastname`, e.g. "Rafael", "Mohamed",
"Najoua", "Songbin", "Antonio" - values that read as first names, not surnames, across several
cultures. `firstname IS NULL/'' AND lastname` single word, confirmed via:

```sql
SELECT id, name, firstname, lastname, is_company FROM res_partner
WHERE contact_type='family' AND (firstname IS NULL OR firstname='')
  AND lastname IS NOT NULL AND lastname != '';
```

This is why the "Existing contact" search in `ems.contact.relation.wizard` (the "Add contact"
button on a student's form) often shows only one word instead of "firstname lastname" for these
contacts - `display_name` is correctly showing exactly what's stored; there's no more data to
show. Not a wizard bug, not a search/display bug.

# Root cause of *why* it lands in `lastname` specifically

`partner_firstname`'s own name-splitting heuristic
(`FirstNameMixin._get_inverse_name` in `partner-contact/partner_firstname/models/firstname_mixin.py`)
pads a single-word `name` value as `[word, False]` and returns
`{"lastname": parts[0], "firstname": parts[1]}` - i.e. whenever only one word is known, it
always lands in `lastname`, never `firstname`. This is upstream OCA behavior, not something to
patch in EMS.

# Possible fix (not applied)

A one-off migration script moving `lastname` → `firstname` for exactly these 347 records
(`UPDATE res_partner SET firstname = lastname, lastname = NULL WHERE contact_type='family' AND
(firstname IS NULL OR firstname='') AND lastname IS NOT NULL AND lastname != ''`, or the ORM
equivalent so `name`/`display_name` recompute correctly) - **not run**, since:

- It's a judgment call on 347 real people's personal data, not something to infer purely from a
  column heuristic (a family surname genuinely could be a single word too, in principle).
- The developer was asked directly (2026-09-05) and chose to leave it as-is for now rather than
  migrate.

# How to revisit

If asked again later: re-run the query above to get the current count/sample (the number may
have grown or shrunk since 2026-09-05 as new contacts are added or existing ones corrected by
staff), then re-propose the migration with a fresh sample for confirmation before touching any
real record. Delete this file once resolved either way (migrated, or the developer decides
permanently not to) - see CLAUDE.md's "Design plans" section.
