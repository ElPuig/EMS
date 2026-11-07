# Changes

## A level's schedule declaration code is now catalog data (read-only):

- The code of each official level in the schedule declaration's summary table (ESO, BTX to BAT, CFGB, CFGM, CFGS, EFPS to CEFP, PFI) is set by the Departament, like the level's educational stage, so it now lives in EMS's catalog (`data/cat/ems.level.csv`), is re-applied on every upgrade and is read-only on the level's form. The one-time seed (`LEVEL_DECLARATION_SEED`, `ems.level._ems_seed_declaration_codes()`) is gone; the non-teaching types' codes are still the centre's and keep their one-time seed.
- A level created by the centre has no code, so its classes go to *Altres*, as the manual says.
- The admin manual (ca/es/en) and its level form screenshot describe the new behaviour; the screenshot now shows the whole form (it still showed the field in the old "Main data" group).
