# What's new

## Meetings page for the computers with an NFC reader:

- A fixed public address, `/ems/meetings`, that a computer with an NFC reader can keep as its home page, with no login. It reads tags like the meeting kiosk: passing a tag lists the meetings its owner can open today (started and not ended yet), with their times, room and whether they are in progress; clicking one opens its kiosk, and the kiosk shows a "Meetings" link to go back. The list clears itself after 30 seconds if nobody picks a meeting, and an unknown tag or one with nothing to open today gets a clear message.
- A meeting attendance now records its **Convener** (by default whoever creates it, editable) and optional **Managers**. A tag opens the meetings it convened or manages, the ones convened by anyone below its owner in the chain of command (a Department or Seminar Chief sees their staff's, the Head of Studies or Deputy their whole area's), and the Director's opens every meeting.

# Internal changes

## Meetings page routes and shared tag reader:

- New public routes `/ems/meetings` (OWL public component) and `/ems/meetings/scan`; who can open a meeting reuses the tutor scope's chain of command (`tutor_scope_user_ids`) from the convener upwards, plus the managers and the Director. The kiosk takes `?back=1` to show the way back.
- The keyboard-wedge reader handling of the kiosk moved to a shared `useTagReader()` hook used by both pages.
- Backend, controller and browser-tour tests (the tour plays a real reader in production mode), manual screenshots updated.

# Related with

- Closes #526
