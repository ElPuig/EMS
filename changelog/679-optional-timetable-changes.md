# Breaking changes

## Guard duty board: timetable changes are now opt-in, and all of them start switched off:

- Three new company settings (Settings > EMS Management > Guard Duty Board Settings): "Come in later" (late entry, and no classes at all), "Leave earlier" and "Longer break". The guard duty board and the arrangement planner only propose the kinds of change switched on there; with one off, its empty lessons are covered with a guard like any other.
- All three are off by default, on new and existing installations alike: after upgrading, the board stops proposing late entries, early leaves and longer breaks until an administrator switches them on (requested by the centre, issue #679).
- What was already communicated keeps counting, and its correction is still offered if the absences change afterwards, whatever the setting says now.

# Changes

## Guard duty board: a longer break is told to the students only and still needs a guard:

- Students under 18 cannot leave the centre, so a longer break no longer counts as "no guard needed": the lessons it takes in stay on the absences table (not struck out, with the break shown as a tag), a guard can still be sent, and the arrangement planner counts them as needing one.
- A notice that only changes a break (a longer one, or its correction back to the usual one) goes to the group's students only, opens with "Dear students," and reminds those under 18 that they cannot leave the centre during the break. A notice that also changes when the group comes in or leaves still goes to students and families, break included.
- The board's wording follows: a plan's notice step for a break reads "Notice to the students of ...", a break correction says the students (not the families) were told, and a group whose only proposals are longer breaks shows them under "Only tell the students" instead of "Only tell the families".
- New browser tour for a communicated longer break; backend tests for each switch, the recipients and the guard still being needed. Technical and user documentation (teachers, Head of Studies, administrator) updated in the three languages, with the Catalan/Spanish translations.
