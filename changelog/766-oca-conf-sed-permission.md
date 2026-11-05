# Fixes

## update.sh no longer fails adding an OCA folder to odoo.conf when /etc/odoo is root's:

- The v18.0.0.46.0 production deploy stopped in `update.sh` right after cloning OCA/sign: `scripts/oca_repos.sh` edited `odoo.conf` with `sed -i`, which creates a temporary file in `/etc/odoo`, and that folder is root's even though `odoo.conf` is odoo's. The new content is now built under `/tmp` and written over the existing file (through sudo only when the file itself is not writable), so only the file's permission matters and its owner and mode are kept. Reproduced and checked as the `odoo` user against a root-owned folder holding an odoo-owned file, as in production.
