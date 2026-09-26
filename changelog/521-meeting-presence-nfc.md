# What's new

## Meeting attendance with the NFC tag:

A new **Meetings** menu, with an **Attendance** screen, confirms who attends a meeting (a staff meeting, a department meeting, a training) with the same NFC tag the staff already use to clock in, instead of a paper sheet everyone signs. Nothing is written to the clocking-in records: this is not time tracking.

- **A session per meeting**: name, start, duration or end, room, course and who is convened (all teachers, all staff, a department, a workgroup, or chosen by hand). The convened people are loaded when the session is saved, and can be adjusted by hand at any time.
- **A kiosk page for the door**: a laptop with a USB NFC reader keeps it open, with no login. It only takes tags between the meeting's start and end (2 hours by default) and switches on and off by itself, with no need to reload it. Each tag shows the person's name and photo in a colour (registered, already registered, not on the convened list, unknown tag). On the left it lists the convened people who have not registered yet; on the right, the attendees with the time they registered; whoever passes the tag moves from one to the other. The lists show names only, without the last surname when that is safe to tell (the whole name stays in any doubt, and the card in the middle always shows it whole), and they always fit: the font and the number of columns adapt to how many people there are (big for a handful, small and in several columns for a staff meeting's hundred), so nobody ever has to scroll. It works like the clock-in kiosk: there is no box to type in and only keys that come at a reader's speed count as a tag, so typing a code by hand registers nothing. A box for typing a code appears only outside production, as a testing aid.
- **Closing the session** marks everyone who did not pass their tag as absent, keeps the justified ones and locks the list until it is reopened. People can be marked present or justified by hand while it is open.
- **PDF report** with the people present (with the time), justified and absent.
- Manageable by the Director, Head of Studies, Secretariat and academic administration. Teachers only pass their tag.

The **Meetings** root menu, and its `views/` folder, are the ones the quality work's minutes (#497) will also use, so both will share one menu.

# Internal changes

## Meeting attendance model, kiosk and how it joins the minutes:

- New models for the session and its lines, a public token-protected kiosk route (own OWL public component, keyboard capture without the 150 ms barcode-service threshold), and a QWeb PDF report. Technical reference in `docs/en/developers/meetings/meeting_presence.md`.
- The convened list is read through the public employee model and uses the same scope semantics as the minutes' attendee preloading, so #497 can derive a minute's attendees and absentees from a session; the steps are in `plans/meeting_presence_minute_integration.md`.
- Browser tours for the manager screens (as a secretary) and for the anonymous kiosk, backend and controller tests, and a screenshot capture class for the manual.

# Related with

- Closes #521
