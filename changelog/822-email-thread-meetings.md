# What's new

## Meetings held by email ("By email" modality):

- Any meeting minute can be held by email by choosing the new modality "By email" (next to in-person, online and hybrid). The minute keeps its own type, scope and numbering, so it follows on from the earlier minutes of the same scope and stays in the default "Meeting minutes" filter. Instead of a time, room and kiosk it asks for "Answers until"; "Open the thread" emails everybody convened the agenda and the deadline from the minute's own chatter, so answers come back through the catchall address and the existing incoming mail server (issue #586).
- Every answer (by email, or a message written in the minute's history) is written under the "Precs i preguntes" section with its author and date and without the quoted text (`data-o-mail-quote`); everybody convened starts among the absentees and moves to the attendees as they answer. "Precs i preguntes" gets a section kind of its own (`requests`), set on existing installations by a migration; only types with that section can be held by email.
- Participants (even those who can only read the minute) can add interventions from EMS (Actions → Add interventions): one box per item and one for "Precs i preguntes", filled at once; each text is written under its item, and all of them go to everybody in a single email by the thread, saying which item each part is about.
- Every message of the thread reaches each participant by email, also those who read notifications inside Odoo, as in a mailing list; whoever is taken off the lists stops getting it.
- The draft goes by the same thread; whatever is answered to it stays in the minute's history for the writer to apply, without holding the approval. No call is sent for a meeting held by email, and once opened it can no longer go back to being prepared.

## Meeting emails in the EMS card layout:

- The call, the draft for the participants and every message of a meeting held by email (its opening, its draft and the answers relayed to everybody) now use the same card layout as the Google account emails (`ems.mail_layout_minutes`, built on `ems.mail_layout_card`, colours from the company's email colours), with bodies rebuilt from shared pieces (label, title, facts card, note, agenda). Staff get an "Open the minute in EMS" button; guests from outside EMS get none. The footer invites an answer instead of saying none is needed, since these emails are meant to be answered.

## Approved minute emailed to the participants:

- Approving any meeting minute now emails it to everybody convened, whether they came or not: the staff get a link to the approved PDF, guests from outside EMS get it attached, and a meeting held by email gets it by its own thread. It closes the process the call and the draft started.

## "Mine" includes the meetings you were convened to:

- The default "Mine" filter of the minutes list now also covers absentees, so a meeting somebody missed (or one held by email they have not answered yet) is among theirs.

# Fixes

## Absentees can read the minute they were convened to:

- The read rule of minutes (`rule_minute_teacher`) only let the attendees in, so an absentee of a minute with no particular scope got its draft by email (issue #755) but could not open it. Absentees now read it as attendees do.
