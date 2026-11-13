# What's new

## AMPA membership visible to tutors and their hierarchy:

- New "AMPA" indicator on students: a student is an AMPA member when their confirmed enrollment of the running course carries the AMPA fee and the first installment of its invoice (where the fee is billed) has been collected. A sibling (a student sharing a family contact) of a member counts as a member too, since the fee is paid once per family.
- Shown to the student's tutor and the chiefs above them (Department/Seminar Chief, Head of Studies/Deputy, Director), the secretary's office and the administration; empty for anyone else, and not available at all to other roles.
- Educational Community > Students: optional "AMPA" column and "AMPA member" / "Not an AMPA member" filters (scoped to the reader's students server-side); "AMPA" Yes/No badge on the student form.
- Backed by a stored "AMPA fee paid" flag on the enrollment, recomputed on payment, unreconciliation or invoice cancellation; computed for every existing enrollment on upgrade, no migration needed. Reading it for the whole centre takes ~80 ms cold.
- Trilingual tutors' manual (linked from the department chiefs', Head of Studies' and secretary's indexes), developer doc, backend tests and a tutor tour.

# Internal changes

## Shared "installment collected" check:

- The portal's payment block and the AMPA membership use the same `account.move.line._ems_installment_paid()` helper.
