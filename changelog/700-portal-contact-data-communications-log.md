# What's new

## Contact data review logged in the student's Communications, with an activity for the tutor:

- The contact data request (`ems.contact.data.request`) is now a `mail.thread` + `mail.activity.mixin`, with a chatter on its form. Every step of the review is logged on its thread: the request sent by the tutor/secretary/head of studies (the first one, not the reminders), each change sent from the portal (with or without a previous request, summarised per person by field name, photo included, without the values), and the result of the review (approved, or returned with the reason). An answer without changes goes straight to Done and is not logged (agreed with the developer).
- Before this, nothing of the cycle reached the portal: the request email is an `email_outgoing` message that is deleted once sent, and an approval only left an internal note on the student.
- The log uses a new subtype, `ems.mt_contact_data_request` (not default, hidden), so posting it emails no one, and it is written in the language of whoever acts for the student on the portal (the reader), whoever triggers it.
- The portal's Communications page (`/my/comunicaciones`) lists the request's thread, only the messages of that subtype, so the tutor's closed activity never shows to the family.
- When an answer with changes arrives, the student's tutor gets a new activity type, "Review contact data changes" (`ems.mail_activity_contact_data_review`), whoever asked for the data; one per request even if the family sends it again; none if the student has no tutor (a tutor assigned later finds the request in the list). Approving or returning the request marks it as done.
- Measured on the dev DB (warm): about 15 ms for the log and 25 ms for the activity per submission.
