# Fixes

## Guard duty board on public holidays (issue #740):
- On a public holiday (Absences > Configuration > Public Holidays) the guard duty board marked every teacher as "Not checked in" and asked for guards for every class already started, since nobody checks in that day. It also listed the approved absences falling on the holiday as classes to cover.
- Now the board shows a notice with the holiday's name, the absences table is not shown, nobody is marked as not checked in, and nothing can be covered or organised that day (the server refuses every board action too, not only the hidden buttons). The timetable view still shows the usual timetable. The PDF prints the same notice and leaves the absences table out.
- The holiday check is one shared helper (`resource.calendar.leaves._ems_public_holiday_on`), also used by the detected absences, which already skipped public holidays; two regression tests cover a several-day holiday caught up by the scheduled action and the re-detection after a refused request.
- Hardened an existing PDF test (WC guard marker) that depended on the order of the guards within a period, which is not fixed.
