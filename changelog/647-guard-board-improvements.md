# Changes

## Guard duty board (current-time line and aligned action buttons):

- When the board shows today, a red line crosses both views (absences table and timetable) at the current time, at its exact height inside the time block holding it (rows have different heights, so it is measured on the row itself). "Now" is the server's clock in the company's timezone; the line is hidden on any other day or outside the shift on screen, moves once a minute without re-rendering the board, and never takes a click from the cells under it. Each grid row now carries its own `hour_from`/`hour_to` for it.
- In the "Proposals for the absences" box, the "Apply the checked steps" button of each proposal now sits on the right, in the same column as the "Propose notice" buttons of the "Only tell the families" rows, and every action button of the boxes above the table shares one width (one CSS class), so they all line up.
- `shift_ems_clock()` (tests) takes an optional `weekdays`, so a tour can move the clock to a school day; the guard duty board tour uses it (09:30 of a weekday) to check the line on both tabs and its absence on another week, and the arrangement tour checks the apply button's alignment and width.
