# What's new

## User menu "Documentation" opens the EMS user manuals:
- The "Documentation" entry in the avatar dropdown (top right) now opens the EMS user manuals
  (https://docs.ems.elpuig.xeill.net/) in the user's own language (Catalan, Spanish or
  English, with English as the fallback) instead of Odoo's developer documentation.
- Implemented by re-registering the native `user_menuitems` "documentation" entry
  (`static/src/js/backend/user_menu_documentation.js`); it keeps the same position and label.
- New tour `TestUserMenuDocumentationTour` (teacher login, ca_ES and fr_FR→en fallback),
  developer doc `docs/en/developers/shared/user_menu_documentation.md`, and a one-line mention
  in the three docs index pages.

# Related with

- Closes #516
