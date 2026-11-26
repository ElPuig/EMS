# What's new

## Space reservation:

Teachers can reserve a free space for a time span from Educational Community > Spaces > Space reservations. New opens a window that first asks how to search: by date (a day, a start and an end give the free spaces, a list that follows every change without a search button, one of which is chosen) or by space (choosing the space draws its week as a grid with what holds it and a dotted red line at the current time, and a free time is chosen by dragging over it; a day and time typed by hand that have already begun are refused on the spot). Space types can be marked as not reservable (WC is not), and so can a single space. Saving a reservation over a taken space is refused with who holds it and when.
A space counts as taken when it is in a teacher's weekly timetable (classes and duties), when it has another reservation, or when a meeting is held in it. A meeting minute's room now makes (and keeps up to date) its own reservation, so a meeting and a teacher asking for the same room go through the same check, and a minute whose room is taken cannot be saved.
A teacher changes only their own reservations; the secretariat and the administrators change any.

## Meetings already scheduled in a room:

A migration (18.0.0.53.0) gives their reservation to the upcoming in-person and hybrid meetings that already have a room, oldest first. One whose room is taken by an earlier meeting or a timetable block is left without it and logged, never failed.

## Warehouse and WC space types:

Both join the catalogue so they translate (Warehouse was shown untranslated); an installation that already had them keeps its own, which are matched by name.

# Internal changes

## Single availability check for spaces:

One method (`ems.space._get_space_conflicts`) decides whether spaces are free for any number of spaces in two searches, plus one per calendar day. Modelled in-house because Odoo Community has no room booking and OCA `resource_booking` would need a mirrored calendar per space (see the developer doc).

# Related with

- Closes #475
