# Fixes:

## A repeater's subject pending from an earlier course was placed in the wrong group:

`_ems_apply_destination_placement()` (`models/enrollment/enrollment.py`) resolved a single
destination group for a whole enrollment order and stamped it onto every subject found among
the order's line products - including a subject a repeater is only re-enrolling in because
they failed it in an earlier course (e.g. `Tutoria 1r AD` ending up under group `AD2A`, 2nd
course). D15's own worked example (`docs/en/developers/settings/course_transition_wizard.md`)
already showed this exact mixed-order shape but only fixed the order's own destination group,
not each individual subject's.

- New `ems.study._ems_subject_course(product)` generalizes the lookup
  `_ems_course_from_tutorship()` already did for the tutorship product to any subject: which
  single course's enrolment template (if exactly one) sells it.
- New `ems.group._ems_equivalent_for_course(course)` resolves the group where a subject of a
  different course is actually taught: exact acronym+shift match, falling back to the first
  group of that study+course (by the model's own order) so a pending subject is never left
  unplaced - looser on purpose than the "leave empty" rule used for a student's own main group,
  since this only decides where they attend one class.
- A subject sold by both courses' templates (a real, confirmed case: AIF's own
  `Recursos humans i responsabilitat social corporativa` / `Sostenibilitat aplicada al sistema
  productiu`) is left on the student's own group - genuinely ambiguous, not guessed.
- A one-time migration (`migrations/18.0.0.23.1/post-migrate.py`) reassigned every already
  existing misplaced enrollment using the exact same production methods. Confirmed on this
  environment before/after: 194 active `ems.enrollment` rows across 103 students fixed, 0 left
  mismatched.
- New backend tests (`tests/test_enrollment_placement.py`) covering every branch, plus a new
  browser tour (`enrollment_placement_pending_subject`) confirming an individual repeater
  enrollment confirmation visibly lands the pending subject in its own course's group.
- User docs (admin, 3 languages) and developer docs (D20) updated.
