# What's new:

## Guard duty board: classes whose teacher has not checked in (issue #692):
- Today, as soon as a class starts, if its teacher has not checked in it shows up on the absences table like an absence ("Not checked in" tag), so a guard teacher can cover it. No grace period: any margin delays the reaction. A guard on duty who has not checked in is marked in the guard column and cannot be sent.
- Checking in clears the class in progress and the next ones; classes that ended before the check-in stay, so a guard already sent to them stays valid. An absence (approved, pending or expected) always takes precedence.
- Only a guard is offered for these classes: no proposals to tell the families and no internal arrangements, since the teacher may still be in the building (`board_arrange` refuses them too).
- "The teacher is in the classroom": the guard on duty in that period, or whoever manages the teacher's absences (chain of command, Direction, administrator), can register the teacher's check-in at the current time from the row of the class in progress. The check-in records who registered it (new "Check-in registered by" field, shown on the attendance form only) and the teacher receives a message saying so.
- The board refreshes itself while open, without a spinner and without redrawing when nothing changed, every 30 seconds by default (new setting "Automatic refresh" in Guard Duty Board Settings, 0 = off). It pauses while a dialog is open or the tab is hidden. Measured at 0.15-0.24 s per load on the dev database, the same as before.
- Teacher, Head of Studies and admin manuals (ca/es/en) and the developer doc updated.
