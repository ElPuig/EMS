# Changes

## Students' and families' names saved with capital initials:

- A student's or family member's name typed all in capitals or all in lower case ("ASHLEY CRISTINA BUENO", "laila") is now saved with capital initials, whatever the way in: the contact form, the family contact wizard, the importers or an approved contact data request. A name with mixed case was written that way on purpose ("McKenzie", "DiMaria", "E2E Test") and is kept as typed; the decision is taken on the whole value.
- Particles stay in lower case inside a name ("De la Fuente", "Puig i Cadafalch"), and hyphens and apostrophes keep the next letter in capitals ("Pérez-Luna", "D'Amico"). "el" is not a particle: here it mostly starts an Arabic surname ("El Maazouzi").
- A complete name is normalized the way partner_firstname splits it (first word, then the last names), so the last names come out the same whether they are typed on their own or within the complete name.
- A contact data request normalizes the family's names before comparing them with the ones on file, so a name typed in capitals is not a change to review.
- Providers and staff are not touched.

# Fixes

## Names already stored in capitals or lower case (migration):

- `migrations/18.0.0.40.0/post-migrate.py` gives capital initials to the students' and families' names stored before (18 in the dev database: students entered in capitals, family members in lower case). Through the ORM, so the complete name follows and the students' Google accounts are renamed too (#542). Meant for release 18.0.0.40.0, as agreed with the developer.
