# Fixes

## Answering a guard duty notice reaches whoever sent it (not the EMS mailbox):
- A direct notice sent on someone's behalf (the "you have been sent to cover this class" message of the guard duty board, its "no longer needed" counterpart, and any other `message_notify()`, Odoo's own apps included) now carries that person as `Reply-To`. Until now the answer went to the company's catchall address (`ems@elpuig.xeill.net`), where nobody but the mailbox's manager saw it (issue #607).
- A notice nobody caused (a scheduled action) keeps the EMS mailbox as its reply address.
- Implemented once, in a `mail.thread.message_notify()` override (`models/shared/mail_thread.py`), not per call site, so the timetable-arrangement notices of #605 are covered as well.
- Email templates were reviewed and left as they are. Those with their own `reply_to` (notices, strikes, attendance issues) name a person; those sent on someone's request without one (convalidations, authorizations, contact data requests) are answered to the company's email address; only the automatic daily attendance summary for tutors is answered to the EMS mailbox, which is fine for an email nobody wrote.
- New developer doc `docs/en/developers/shared/mail_reply_to.md` (which `Reply-To` each kind of EMS email gets); teachers' guard duty manual updated in the three languages.

# Related with

- Closes #607
