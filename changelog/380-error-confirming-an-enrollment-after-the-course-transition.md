# Fixes

## Confirming an enrollment after the course transition no longer fails with "Only admins can create manual enrollments":

Once the 26-27 transition flipped the current course, `sale.order._ems_placement_is_individual()` became true for every pending enrollment, so confirming one finally ran `_ems_apply_destination_placement()` - the step that moves the student into the destination group and creates one `ems.enrollment` per subject sold by the order. That creation went straight into `ems.enrollment.default_get()`'s "only academic admins may create manual enrollments" guard and aborted the whole confirmation with an invalid-operation dialog, leaving the student unplaced and with no subject enrollments.

The placement had always run the creation under `sudo()` for exactly this reason, but `sudo()` only sets `env.su` - it does not turn `env.user` into the superuser - so the guard kept evaluating `has_group('ems.group_academic_admin')` against the real user behind the request. Nobody who confirms an enrollment is an academic admin: the student confirms it from the portal (`enrollment.sudo().action_confirm()`), the secretary from the backend. The guard now honours `env.su`, which is the only signal that separates a blank form opened by hand from a placement running on somebody's behalf; manual creation stays blocked for tutors and teachers exactly as before.

Regression tests in `tests/test_enrollment_placement.py`: the placement now runs for a portal user and for the secretary, and manual creation without `sudo()` is still refused for a tutor. Verified end to end on the development database: confirming a pending 26-27 order as a portal user converts the applicant into a student, sets the destination group and creates its 11 subject enrollments.

# Internal changes

## Developer documentation of the guard and of the placement condition:

`contacts/enrollment.md` gains the reasoning behind the `env.su` escape hatch (including the `create()` -> `_add_missing_default_values()` -> `default_get()` path that makes a guard in `default_get` fire on programmatic creation too) and an updated flowchart. `enrollment/enrollment.md`'s admission section was still describing the placement as firing only for a study already `transitioned`, predating `_ems_placement_is_individual()`; it now documents both ways of being true. `settings/course_transition_wizard.md` records the incident next to the change that exposed it.
