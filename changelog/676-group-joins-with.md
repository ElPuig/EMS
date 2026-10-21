# What's new

## Groups: say which groups are halves of a split group (issue #676):

- New "Joins with" field on the group form: the other half of a split group (e.g. AIF2B on AIF2A). It
  is always mutual: setting it on one half sets it on the other, and removing it removes it from both.
- The guard duty board's "Joined groups" arrangement (issue #660) now only joins groups set as halves
  this way, instead of any two groups sharing a lesson in the weekly timetable, which also paired groups
  like DAM2A and DAM2B that share some lessons without being halves.
- Halves must be of the same type and share their tutor, delegate and sub-delegate: linking copies the
  edited group's onto the other half (keeping the half's own where the edited group has none), any later
  change on either half is copied to the other, and delegates are chosen among the students of both. The
  form asks for confirmation before replacing a half's own tutor, delegate or sub-delegate.
- Once released, nothing is joined until the halves are set on the group forms.
- Group and guard duty board tests, a browser tour of the field (as Department Chief), admin and teacher
  manuals (ca/es/en), developer docs and translations.

# Fixes

## A Department Chief can change a group's tutor (issue #676):

- Saving a group with a new tutor as a Department Chief failed with an access error on employees, since
  the Tutor role sync ran with the user's rights; it now runs as superuser.
