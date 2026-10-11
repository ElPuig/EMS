# Fixes

## Answering a guard duty notice reaches whoever sent it (not the EMS mailbox):
- A direct notice sent on someone's behalf (the "you have been sent to cover this class" message of the guard duty board, its "no longer needed" counterpart, and any other `message_notify()`, Odoo's own apps included) now carries that person as `Reply-To`. Until now the answer went to the company's catchall address (`ems@elpuig.xeill.net`), where nobody but the mailbox's manager saw it (issue #607).
- A notice nobody caused (a scheduled action) keeps the EMS mailbox as its reply address.
- Implemented once, in a `mail.thread.message_notify()` override (`models/shared/mail_thread.py`), not per call site, so the timetable-arrangement notices of #605 are covered as well.
- The emails sent with a template on someone's request (convalidation resolution and request for documentation, new authorizations to answer, contact data request) are now answered to whoever sent them, instead of to the company's general address. A reminder a scheduled action sends keeps the company's address. The templates that already named a person (notices, strikes, attendance issues) are unchanged.
- One shared rule decides what "a person" is, `res.partner._ems_reply_to()`: an internal user other than OdooBot, never a portal user.
- New developer doc `docs/en/developers/shared/mail_reply_to.md` (which `Reply-To` each kind of EMS email gets); teachers' guard duty manual updated in the three languages.

# Related with

- Closes #607
