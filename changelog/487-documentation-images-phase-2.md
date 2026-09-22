# Internal changes

## Guard duty schedule manual screenshot (teachers):

Added the missing screenshots to the Teachers "Guard Duty Schedule" manual (timetable view and
Absences table view), regenerated via the existing `ChromeBrowser`-based docs-screenshot
mechanism with fully fictitious fixture data. Along the way, found and fixed a real privacy gap
in that same mechanism: the guard-duty board is a centre-wide client action with no domain to
scope it by, so the first capture attempt rendered real staff/schedule data before being caught
by visual inspection. The capture now scopes the board's own data-aggregation method to the
test's fixtures only, for the duration of the test.

## Profile picture visibility manual screenshot (teachers):

Added the missing screenshot to the Teachers "Disabling Your Profile Picture" manual, showing
the Preferences tab of "My Profile". Also corrected the manual's own steps, which never mentioned
opening that tab at all - a leftover gap from an earlier restructure of the profile screen into
tabs. The capture needed a short tour to reach the screen, since "My Profile" has no directly
addressable URL of its own.

## Strike dialog manual screenshot (teachers):

Added the missing screenshot to the Teachers "Strikes" manual, showing the strike dialog opened
from the roll-call view with its default state (reason, notice/kicked-out toggle, optional
details field).

## Student academic history manual screenshot (teachers):

Added the missing screenshot to the Teachers "Consulting a Student's Academic Data" manual,
showing the Academic history tab on a student's own file with two example years.

## Student list "My students" filter manual screenshot (teachers):

Added the missing screenshot to the Teachers "Students: your own groups" manual, showing the
Students list with both default filters applied. Also corrected a small, pre-existing wording
mismatch in the Catalan and Spanish versions: the manual described the first filter chip by the
wrong label, not the one actually shown on screen.

## Weekly schedule manual screenshot (teachers) - Teachers manuals now fully illustrated:

Added the last missing screenshot in the Teachers section, showing the weekly schedule grid on
"My Profile" with a teaching block and a break. Also corrected the manual's own access
instructions in all three languages, which pointed at an "Employees" menu a plain teacher doesn't
have - the real path is "My Profile", where the Schedule tab is already active by default. With
this, every Teachers user manual now has at least one screenshot.
