# Internal changes

## OdooBot's emails switched off on development machines (on demand):

- On a development machine (`ems_server_role = dev`) with a database prepared by `devel.sh`, `mail.mail.send()` cancels every outgoing email authored by OdooBot (daily summaries, automatic notices) before it reaches the SMTP server, with the reason on the email and its notifications marked as cancelled. A restored production database generated them for every staff member, and all of them landed in the developer's redirected inbox.
- The system parameter `ems.dev_mail_odoobot = True` turns them back on to test a summary or a notice. Production and CI are unaffected; a database `devel.sh` never ran on keeps the existing "Email blocked" refusal.
- Documented in the dev mail guard developer doc and CLAUDE.md; covered by `TestDevMailOdooBot`.
