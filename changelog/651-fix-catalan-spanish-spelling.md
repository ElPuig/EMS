# Fixes

## Spelling and grammar in the Catalan manuals and translations:

- Reviewed the findings LanguageTool reports on `docs/ca/` and `i18n/ca_ES.po` and fixed the real errors: typos (Obligatoria, cració, sesió, inmediata, Familia, encuats...), Spanish leftovers in Catalan entries (Recargar destinatarios, Información, más, su plau), Ves, encavalcar instead of solapar, codocència and preinscripció without hyphen, "p. ex.", the comma before "però", "respondre a" and the emphatic "propi".
- Job titles (cap d'estudis, director, adjunt, coordinador...) are lowercase in running text, as the IEC norm says; titles kept in capitals only where they are a bold label that matches the interface.
- Spanish texts (`docs/es/`, `i18n/es_ES.po`) are not part of this pass.

# Internal changes

## LanguageTool ignore list:

- Added to `scripts/i18n/lt_ignore.txt` the acronyms, English interface words and technical terms that are correct in EMS texts, so the check only reports real findings.
