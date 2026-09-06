# Fixes

## Reinforcement group not selectable in a student's subject enrollment:
The `group_id` field on the `ems.enrollment` line embedded in the student form's "Studies" tab
(`views/community/contact/form.xml`) had a domain (`[('study_id','=', parent.study_id)]`) meant
to keep the teaching group aligned with the student's own study. Since a reinforcement-type
`ems.group` is constrained by design to always have `study_id = False`, that domain silently
excluded every reinforcement group from the picker - there was no way to enroll a student in a
subject taught by a reinforcement group from their own form, even though the admin/secretary
manual already documented this as expected (e.g. a subject taken in a mixed reinforcement group
rather than the student's own main group). Widened the domain to also allow
`group_type = 'reinforcement'` groups. Covered by a new regression step in the existing
`ems_contact_tabs_and_relation_wizard` tour (`static/tests/tours/contact_tour.js` /
`tests/test_contact_tour.py`), which now adds an enrollment line and picks a reinforcement group
as its teaching group.
