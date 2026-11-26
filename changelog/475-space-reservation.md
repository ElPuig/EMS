# What's new

## Space reservation:

Teachers can reserve a free space for a time span from Educational Community > Space reservations (calendar, list and form). The Space field of the form only offers the spaces that are free for the start and duration typed, and saving a reservation over a taken space is refused with who holds it and when.
A space counts as taken when it is in a teacher's weekly timetable (classes and duties), when it has another reservation, or when a meeting is held in it. A meeting minute's room now makes (and keeps up to date) its own reservation, so a meeting and a teacher asking for the same room go through the same check, and a minute whose room is taken cannot be saved.
A teacher changes only their own reservations; the secretariat and the administrators change any.

## Meetings already scheduled in a room:

A migration (18.0.0.53.0) gives their reservation to the upcoming in-person and hybrid meetings that already have a room, oldest first. One whose room is taken by an earlier meeting or a timetable block is left without it and logged, never failed.

# Internal changes

## Single availability check for spaces:

One method (`ems.space._get_space_conflicts`) decides whether spaces are free for any number of spaces in two searches, plus one per calendar day. Modelled in-house because Odoo Community has no room booking and OCA `resource_booking` would need a mirrored calendar per space (see the developer doc).

# Related with

- Closes #475
