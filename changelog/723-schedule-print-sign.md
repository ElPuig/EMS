# What's new

## Official schedule declaration for teachers (Departament's "Horari professor/a"):

- New PDF "Schedule declaration" that reproduces the teacher's page of the Departament d'Educació i FP's form "Annexos Dades anuals", always printed in Catalan and on one A4 page: header (centre code, name, municipality, course), the teacher's name, NIF (only for whoever can see it, scoped_identification_id) and roles, the same weekly grid as the Working Schedule PDF (now a shared sub-template, report_working_schedule_grid; here with lines drawn and without classrooms, to save height), the "Quadre resum d'hores" by official code, and blank fields and signature boxes to fill in by hand; the form's explanatory sentences are left out. The data boxes and the summary table follow the form's grid, with room to write; summary cells that don't apply are grey and still show any hours landing there, so a wrong code stands out. The existing Working Schedule PDF is unchanged.
- Printed from the teachers' list (Print menu, one page per selected teacher) and from the employee form's Actions dropdown (action_print_schedule_declaration, this teacher only). Only Heads and Deputy Heads of Studies, the Director and the administrators can print it (developer, 2026-10-29), re-checked server-side by the button.
- Summary table (resource.calendar.get_schedule_declaration_summary, sharing _iter_summary_entries with get_schedule_hours_summary): classes go to their group's level code (a split or optative takes its main groups' level, no code goes to Altres); tutorship subjects and the TT non-teaching type go to T-ESO, T-BAT, PFI or T-FP by the tutored level; other non-teaching hours go to their type's code (empty = not declared: break, reduction of working hours); teaching-hour reductions are only given as hours in "Si disposeu de reducció de jornada" and are added to the lective TOTAL (developer, 2026-10-29). Lective vs fixed columns follow the Schedule tab's rule.
- The official codes are configuration: new "Schedule declaration code" on levels and on non-teaching types, seeded once (post_init_hook for clean installs, migrations/18.0.0.43.0 post-migrate for upgrades) with the mapping agreed with the developer, and editable by the centre afterwards. Manifest 18.0.0.43.0.
- Grid on the declaration: hours vertically centred, every block two lines high except breaks (one line); the legal sentence is the page footer, so the signatures get more room.

- Docs: developer doc (working schedules, levels, non-teaching types), user manuals for teachers, administrators and Heads of Studies in ca/es/en; ca/es translations.

# Fixes

## Class blocks named the same way however they were saved:

- The import named a class block "MP 0485: Programació (DAM1A)" and the Schedule tab "MP 0485: Programació: DAM1A", so the PDFs mixed both. Both now write the first one (one shared function, subject_block_name, with its JS twin), a migration rewrote the saved blocks (archived ones included), and the PDFs compose the label from the block's subject, groups and topic instead of the stored name. Also fixes a topic printed twice for a block edited from the Schedule tab.
