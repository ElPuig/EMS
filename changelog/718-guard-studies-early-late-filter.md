# Breaking changes

## Coming in later and leaving earlier now need the studies that may have them:

- The guard duty board only proposes coming in later (or no classes) and leaving earlier for the groups of the studies listed in the new setting **Settings > EMS > Guard Duty Board Settings > Studies that may come in later or leave earlier** (issue #718): some studies' students, minors for instance, can never go home early. It is an allowlist on purpose: while it is empty no group gets either proposal, even with the switches on, so after deploying it has to be filled in with every study that may have them. The longer break does not depend on it (the students stay in the centre).

# Internal changes

## Department and Seminar Chiefs get their own user manuals section:

- New `docs/{en,ca,es}/department_chiefs/` section, linked from the main docs index, the teachers' index and the Head of Studies' index. "Organising an absence" and "Entering a detected absence" moved out of the teachers' Guard Duty Schedule manual into a new "Organising Absences" manual there, and the notices manual for chiefs moved from `teachers/` to `department_chiefs/`; the section's index also points to the chief-specific parts of the teachers' manuals (minutes, attendance records, private notes, absence emails). CLAUDE.md lists the new role folder.
- `_enabled_absence_changes()` now returns the allowed change types per group, and the arrangement planner receives that dict instead of reading the settings itself. Test fixtures switch every change on through a shared `allow_every_absence_change()` helper.
