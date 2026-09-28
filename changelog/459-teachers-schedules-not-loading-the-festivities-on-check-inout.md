# Fixes

## Public holidays always apply to every working schedule (red "absence" attendances on holidays):

- A public holiday tied to one working schedule (the "Working Hours" column of Absences > Configuration > Public Holidays, pre-filled when the list is opened from a schedule's "Public Time Off" button) only applied to the employees on exactly that schedule. Since every teacher has a personal schedule, it applied to nobody: the first Diada was tied to the default schedule framework (no employees), and Odoo's nightly absence detection recorded a red one-second "technical" attendance and negative overtime for ~50 teachers on it. EMS now always empties that field on a public holiday (personal leaves keep theirs) and hides the column.
- Odoo recomputes the overtime when a holiday or absence is entered after the fact, but left the red technical attendance behind. Creating or editing any calendar leave now also deletes the technical attendances of the days it leaves with no expected hours (real check-ins, and days still partly expected, are kept). This also covers a whole-day absence approved late.
- Migration (18.0.0.30.1): public holidays already tied to a schedule are detached, which clears the red attendances and negative overtime they had left behind.
- Admin manual (Absences) now explains which holidays must be entered by hand (national, Catalan, the town's two local ones and the centre's closing days) and why they should be entered in advance.
