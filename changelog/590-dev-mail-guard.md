# Internal changes:

## Development machines never send real email (#590):

- On 2026-10-06 a production dump restored on a development machine (to investigate #588) sent
  412 real attendance notifications to students and families, duplicates of production's own:
  with no `db_name`/`dbfilter` in `odoo.conf`, the Odoo service's queue_job runner and crons
  attached to the restored copy on the next restart and ran the jobs pending in production through
  production's SMTP servers.
- `devel.sh` now pins the Odoo service to `ems` (`db_name = ems`, `dbfilter = ^ems$`), so any
  other database on the box stays inert, and declares the machine with `ems_server_role = dev`.
- New guard on `ir.mail_server._prepare_email_message()` (every real SMTP send): on a machine
  declared dev, an email is refused unless the database went through `devel.sh`
  (`ems.environment_type = dev`) and every recipient (To, Cc, Bcc) is the developer's redirect
  account or one of its `+` aliases (`ems.dev_mail_redirect`, set by `devel.sh`) or in
  `ems.dev_mail_allowlist` (seeded with `ems@elpuig.xeill.net`). A refused email ends in
  "Delivery failed" with the reason. Production and CI never set the role: unchanged there.
- `CLAUDE.md`: lock a restored production copy away from the Odoo service right after restoring
  it; developer doc `docs/en/developers/shared/dev_mail_guard.md`; tests `TestDevMailGuard`.
