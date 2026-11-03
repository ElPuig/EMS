# Changes

## Meetings > Agreements also opens on the agreements where I am involved:

- The staff's agreements screen (Meetings > Agreements) now opens with the facet "Where I am involved" next to "Mine" and "Open": being one of the people involved is enough to find the agreement without touching the filters. Both facets share a filter group, so they add up (responsible or involved).
- Test: the screen's default facets show the agreement to its responsible and involved people, and not to a chief who reads it without owing anything.
- Teachers' minutes manual (ca/es/en) gains a short "My agreements" section; the quality developer overview names the screen's default facets.

# What's new

## An agreement can be closed in the same minute that takes it:

- A new agreement's card in the minute has a **Done** tick, for a decision nobody has to carry out: it adds a closing follow-up entry dated and signed as the minute, so the agreement is closed and is not carried into the next meeting. Unticking it removes that entry. The minute's PDF prints "Done" in its deadline column.
- Tests in `TestQualityMinute` and the minute tour (ticks Done on the card); teachers' minutes manual (ca/es/en) and the quality developer overview explain it.

## Attendees and absentees of a minute exclude each other (drag between them):

- Adding somebody to the absentees of a minute takes them off the attendees and the other way round, and a person can be dragged from one list to the other (new `ems_exclusive_tags` widget, a `many2many_tags` with an `exclusive_with` sibling field). The server refuses a minute with somebody in both lists.
- Test in `TestQualityMinute` and a new minute tour (drag one person, add another by name, save); teachers' minutes manual (ca/es/en) and the quality developer overview explain it.

# Fixes

## Automatic follow-up text of an agreement always in Catalan:

- The follow-up entry EMS writes when a minute reviews an agreement with nothing written about it ("Revisat a la reunió ...") was stored in the language of whoever reviewed it (Spanish for a user working in Spanish). It is now always written in the centre's language, Catalan, like the closing entry of an agreement done in its own minute. A migration (`migrations/18.0.0.45.0/post-migrate.py`) rewrites the entries already stored in Spanish or English; it runs when the release bumps the version.
- Test in `TestQualityMinute` with a writer working in Spanish.
