# What's new

## Centre language setting:

- New required setting *Centre language* (Settings > EMS Management > Center Data, `res.company.ems_lang`): the language EMS writes in by itself, whoever triggers it. The codes of minutes and agreements, the minutes and their calls, the convalidation resolutions and the public group schedules now read it instead of Catalan hardcoded in several places (`SCOPE_CODE_LANG`, `PUBLIC_SCHEDULE_LANG`, the resolution's own `'ca_ES'`).
- Saving it also sets Odoo's own default language of new contacts and users (`ir.default` of `res.partner.lang`, until now only set by hand in developer mode) and marks the public group schedules for regeneration.
- Catalan on every installation: `post_init_hook` (installing Catalan, which a clean install did not have) and a migration (`migrations/18.0.0.45.0/post-migrate.py`) for existing ones; the migration runs when the release bumps the version.
- Tests (`TestCentreLanguage`), clean install checked on a throwaway database; admin manual (ca/es/en) and developer docs.
