# What's new

## Meetings held by email ("Fil de correu" minute type):

- New minute type of kind "Email thread", seeded as "Fil de correu" (generic scope, anybody can start it). Instead of a time, room and kiosk it asks for "Answers until" (the last day to take part); "Open the thread" emails everybody convened the agenda and the deadline from the minute's own chatter, so answers come back through the catchall address and the existing incoming mail server (issue #586).
- Every answer (by email, or a message written in the minute's history) is filed in a new "Interventions" block (`ems.minute.intervention`) with its author and date and without the quoted text (`data-o-mail-quote`), editable by whoever writes the minute and printed in the PDF. Everybody convened starts among the absentees and moves to the attendees as they answer; an answer from an unknown address is filed but names nobody.
- Every message of the thread reaches each participant by email, also those who read notifications inside Odoo (`_notify_get_recipients`), as in a mailing list.
- The draft goes by the same thread; answers to it are "Amendments to the draft". Approval waits until every amendment is addressed: going back to the meeting marks them addressed, and one that needs no change can be ticked by hand.
- With "No particular scope", whoever writes the thread is proposed as its approver. An opened thread can no longer go back to being prepared, and no call is sent for it.

# Fixes

## Absentees can read the minute they were convened to:

- The read rule of minutes (`rule_minute_teacher`) only let the attendees in, so an absentee of a minute with no particular scope got its draft by email (issue #755) but could not open it. Absentees now read it as attendees do.
