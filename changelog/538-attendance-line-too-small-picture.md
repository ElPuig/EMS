# What's new

## Enlarged student photo on the roll-call (hover or tap):
- On the roll-call screen (Student's Attendances → Current), hovering a student's photo shows it enlarged (3x, loaded at a higher resolution so it stays sharp) with the student's name underneath, growing out of the thumbnail with a short animation; moving the mouse away closes it. On a tablet/touch screen, tapping the photo toggles it (issue #538).
- Opens after a short hover delay so running the mouse down the list doesn't flash a photo per row; no animation when the OS asks for reduced motion.
- Rendered through Odoo's popover service, so it is never clipped by the scrolling table nor hidden under its sticky header. Built as a reusable `useAvatarZoom()` hook, ready for the other screens with student photos (grade matrices) if wanted.
- Teacher-login browser tour (hover, leave, tap, tap again), teacher manual (en/ca/es) and developer doc. The roll-call tours' repeated slot-selection code was extracted into a shared helper.
