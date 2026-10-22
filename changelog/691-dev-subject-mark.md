# Fixes

## Development emails always marked [DEV] (machines prepared before the mail guard):
- A development box whose devel.sh ran before the mail guard (#590) had a development database but no `ems_server_role = dev` in odoo.conf, so its emails (e.g. a failed Google Workspace job's notice) arrived without the `[DEV]` subject prefix and looked like production's.
- The subject is now marked whenever either the machine role or the database (`ems.environment_type = dev`) says development. The recipient check stays tied to the machine role, since such a database may have no redirect address and the check would block the developer's own inbox.
- Such a machine now logs a WARNING at every server start asking to run devel.sh again, which turns the recipient check on.
