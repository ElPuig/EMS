# Fixes

## Presence dot on the Teachers/ASP screens follows check-in and schedule only:

- A teacher no longer shows as Absent (yellow) up to an hour before their first class or in a short gap between two classes: Odoo counted any schedule slot within the next hour as "should be working now"; EMS now only counts a slot that has already started and not yet ended (`_get_employee_working_now` override on `hr.employee.base`).
- Having EMS open in a browser no longer makes someone show as Present (green) without checking in, nor flips them to Absent after 30 minutes idle: the company's login-based presence control (`hr_presence_control_login`) is switched off on fresh installs (`post_init_hook`) and on upgrade (`post-migrate.py`); the dot now follows the attendance check-in/out only.
- The dot's labels are now correctly translated: 'Out of Working hours' had no Catalan translation, 'On leave' read "En sortir" in Catalan and 'Present but on leave' read "...de vacaciones" in Spanish. Odoo's .po loading never overwrites an existing translation, so they are written directly (`post_init_hook` + `post-migrate.py`).
- New teacher manual (ca/es/en) explaining what each colour of the dot means.
