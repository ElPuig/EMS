# What's new

## Guard duty board on a real time axis, with an area filter (#637):
- Both views of the board (timetable and absences table) are laid out on a real time axis: the rows are the stretches between every start and end time of the shift, and each lesson, absence, break or guard spans the stretches it lasts, with its own start and end time in every cell. Areas whose time frameworks differ (ESO/BTX have their break at 10:00, vocational training at 11:00) line up by clock without bending anybody's lessons, and a longer stretch is a taller row.
- The timetable groups its columns by area, under a header band per area; the absences table has one absences column per area. Guard duties are listed by their own time, side by side when two overlap.
- Each group's or area's break shows as a block of its own, with its time, the "Break" label and a brown accent; break-time guard duties carry the same accent.
- An absent WC or break guard post (it belongs to no group or area) is covered from the guard column of the absences table, under the guards of its own block.
- The level filter is replaced by an area filter (the top-level department above the department that manages each study). Reinforcement groups now follow their main groups' area, so they show when filtering.
- The PDF prints the same layout as the screen, for both views; the layout is computed once on the server for both.
- The areas' names (ESO / BTX, VET, ASP) get their Catalan and Spanish translations (ESO / BTX, FP, PAS), on new installations and by migration on existing ones, unless the centre already renamed them.

# Fixes

## Break guards offered against another area's lessons (#637):
- A shorter period was folded into whichever longer one contained it, even across areas: the ESO break guards (10:00-10:25) were listed against a 10:00-11:00 vocational-training lesson as if they could cover it, and vocational-training break guards against an ESO lesson. A period of some schedule framework (a lesson or a break of some level) is now never folded into another one, with or without a filter.

## Guard duty board loading much faster (#637):
- Each cell of the board looked its lessons up by going through every lesson of the shift (rows x groups x lessons), which made the board's data take over a second on a real centre's timetable (more than ten under the dev debugger). Lessons are now indexed once by group and period, filtered in the database instead of in Python, and the names on the board are read in one go: about ten times faster (around 0.2s on a real centre's timetable).

# Internal changes

## Guard duty board grid (#637):
- New `BoardTimeGrid` (models/attendance/guard_duty_board.py) builds both views' grids; `get_guard_duty_board_lines()`/`get_guard_duty_board_data()` take `area_ids` instead of `level_ids` and return `schedule_grid`/`absence_grid`; `get_guard_duty_board_areas()` replaces `get_guard_duty_board_levels()`. The PDF context key is `guard_duty_area_ids`, the board's URL keeps `areas`.
- Migration 18.0.0.38.0 (post): translates the areas' names.
- Tours locate a lesson or absence by its block's own time instead of its row's, since a row is now a stretch of time.
