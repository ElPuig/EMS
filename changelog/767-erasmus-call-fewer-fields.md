# Changes

## Erasmus+ calls: fewer fields when opening a call (#767):

- The four deadlines after closing (corrections, score correction, claims, acceptance) are filled in from the closing date: 7, 14, 19 and 25 days later at 14:00, on the next school day when that day is a weekend, a holiday or a break (`_ems_deadlines()`). They follow the closing date when it changes, except the ones changed by hand, and are shown folded under "Deadlines after closing". The staff call follows the same rule (its panel deadline is the score correction one, no longer exactly 14 days later at the closing hour).
- The call's header is two blocks, "Settings" and "Calendar" (note 2.3 of the 46.0 review); the read-only "Accepting applications" box (note 2.6) and the reminder days (always 3) leave the form.
- Dates out of the process order (e.g. a claims deadline before the applications close) are warned at the top of the call, without refusing to save (note 2.4).
- A students' modality takes its project from its levels (CFGS and specialisation courses on KA131-HED, any other on KA121-VET); the column only shows on a staff call. The modalities' free-text "Period" and "Destinations" are gone: the real destinations are in the Destinations tab.
- The Mobility block of a call shows once the definitive resolution is published. A staff call hides the Documents tab, and the Panel tab until the call is closed.

# Internal changes

## Shared school-day count:

- `_ems_nth_school_day()` moved from the ex officio withdrawal model to `resource.calendar.leaves`, where the call deadlines use it too.
