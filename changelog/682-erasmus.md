# Breaking changes

## New dependency on OCA's sign_oca (OCA/sign, branch 18.0):

- EMS now depends on `sign_oca`. Before upgrading production, clone `https://github.com/OCA/sign.git` (branch 18.0) next to `queue` and `partner-contact` (`/root/myModules/sign`) and add it to the `addons_path` of `/etc/odoo/odoo.conf`; the upgrade then installs `sign_oca` on its own. `install.sh`, the CI and `/deploy-check` already include it.

# What's new

## Erasmus+ documents signed electronically in EMS (sign_oca):

- A call document (grant agreement, learning or mobility agreement, certificate of stay, Europass, report) can have a signature template: the SEPIE model with the place of each signer's signature, placed once with one sign role per Erasmus+ signer.
- From the participant's record the Erasmus team clicks Send to sign on the filled-in PDF: EMS prepares the request with whoever still signs (participant, family of a minor, Director, Erasmus coordinator, host entity's contact person), lists anything missing (a signer, an email, a box), and the team checks and sends it.
- Every signer signs from a personal link, without an EMS account (the host entity too); the portal shows Sign it here to the participant. Each signature ticks its line (it can't be unticked) and, once everybody has signed, the signed PDF is added to the document for the team to mark it valid.
- The commitment letter keeps its acceptance on the portal and the sBID documents are still signed in sBID.

# Internal changes

## sign_oca integration details:

- `models/erasmus/electronic_signature.py`; the Erasmus team group implies Sign's "All Documents" and can edit the templates; the sign role names are translatable.
- sign_oca 18.0's Odoo 16-style test tour is removed from `web.assets_tests` (it would fail every tour); the EMS portal landing now has priority 110, above sign_oca's portal home card.
