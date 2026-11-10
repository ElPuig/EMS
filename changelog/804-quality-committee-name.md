# Fixes

## Quality committee workgroup keeps the name the centre gives it:
- The "Quality Comission" workgroup (ems.quality) lived in data/cat/, the catalogue re-applied on every upgrade, so any rename made from the app was reverted on the next update. It now lives in data/main/ems.workgroup.xml under noupdate, named "Comissió de Qualitat" on new installations.
- Migration 18.0.0.48.0 (pre-migrate, raw SQL) sets noupdate on the existing record's xmlid and renames it to "Comissió de Qualitat" only if it still carries the original "Quality Comission".
