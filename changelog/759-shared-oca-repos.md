# Internal changes

## One shared list of OCA repositories (scripts/oca_repos.sh):

- The OCA repositories EMS depends on (`queue`, `partner-contact` and `sign`, needed by v18.0.0.46.0's `sign_oca`) are listed once in `scripts/oca_repos.sh`. `install.sh` and `update.sh` clone the ones missing next to `ems` (through sudo when the folder is not writable, then handed to the owner of the EMS checkout) and add them to the `addons_path` of `/etc/odoo/odoo.conf`, so a new dependency reaches every box, production included, with the next update. `upgrade.sh` is unchanged.
- `/deploy-check` builds its `addons_path` from the PR's list; a repository production does not have yet is cloned next to the PR checkout, never in production's folders.
- The CI's `odoo.conf` no longer lists the OCA folders: `install.sh` adds them, as on any other box.
- Shipped on its own before v18.0.0.46.0 so that, when 46.0 is checked and deployed, `main` already has the new `/deploy-check` (GitHub runs comment-triggered workflows from `main`) and production the new `update.sh` (`deploy.sh` runs the one on disk before pulling).
