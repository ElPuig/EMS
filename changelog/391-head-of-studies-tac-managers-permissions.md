# What's new:

## TAC coordinator role and its own permission block:
- New `role_tac` ("TAC coordinator") entry in the role catalog (`data/cat/ems.role.csv`), non-unipersonal and restricted to teachers, so the post can be held by a team rather than a single person.
- New `TAC` category in the permissions selector (`ems.category_tac`), with its own `group_tac` (Manager) / `group_tac_admin` (Administrator) pair, following the same independent-block pattern already used by Quality, Coexistence and Settings. The category is transversal to the Teacher -> Tutor -> Department Chief -> Head of Studies chain: the coordinator gets the staff-management rights and nothing else from that chain.
- The TAC group inherits the base teacher access, because the post is always held by a teacher, plus the same HR officer group as the Head of Studies.
- Assigning the role adds the holder to the matching security group automatically, and removing it takes the group away again - from either the employee's record or the role's own screen (see the fix below for why the second one did not work before).

## Head of Studies and TAC coordinator can create and edit teachers:
- Until now only the academic Administrator could write to a staff record; the whole tutor / department chief / Head of Studies chain was read-only. The Head of Studies, the Deputy Head of Studies (both inherited by the Director) and the TAC coordinator can now create and edit teachers, managing their records in full - the private information and HR tabs included, since these posts are the ones responsible for that data.
- Both groups get this by inheriting Odoo's own HR officer group rather than through a hand-written list of permissions. Beyond being a single well-understood grant, it is the only thing that opens the personal email field and the private tabs, which carry a field-level restriction that no permission line or record rule can lift. Odoo's own Employees app does not appear as a side effect, since EMS already hides it.
- Two limits are then narrowed back down by record rules: editing and creating only apply to teaching staff, so ASP records stay with the Secretariat, and deleting a staff record remains unavailable to both new groups. Read access is deliberately untouched, so nothing that could be seen before stops being visible.
- The Google Workspace buttons on the employee form (create, suspend and reactivate the account, create the EMS user, mark as identified) come with the same inherited group, so creating a teacher and giving them their corporate account is now a single flow for the same person.

## The personal email is now reachable, which is what makes the Google account work:
- The personal address is where the credentials of a new Google account are delivered: a PDF is attached to the record and a welcome email with the password is sent there. Without it the account is never created.
- The employee form already marked that field required when creating teaching staff, but the field carries a permission restriction of its own, so it was stripped from the form of anyone without the HR group - and the requirement went with it. A Head of Studies could therefore save a new teacher with no personal address, no corporate account, and no way to send them their password: the constraint existed but was invisible to exactly the people creating the records. Inheriting the HR group restores both the field and its requirement.
- The field is now also shown on the main screen of the employee form, last in the right-hand column under Department, Job Position and Manager, while staying in its usual place inside the private information tab. A required field buried in a tab means every new teacher starts with a validation error on a screen that does not show what is wrong. Both are the same field, so filling in either one fills in the other.

# Fixes:

## Roles assigned from the role's own screen now grant their permissions:
- A role that carries a security group only applied it when assigned from the employee's own record. Assigning it from the role's "Assigned to" list wrote the relationship but never granted the group, so the person held the role while none of its permissions worked - and hit an access error the first time they used it. Found with the new TAC coordinator role, but it affected every manually assignable role linked to a group, including the Quality and Coexistence coordinators and the Secretary Administrator.
- Both directions are covered: assigning grants the group, and removing the assignment revokes it.

# Internal changes:

## Creating a teacher writes to five models, not one:
- The employee record itself, plus the resource and personal calendar EMS creates for every new teacher, plus the resume line the native skills module seeds. The inherited HR group covers three of them; the two calendar models keep their own permission lines.
- The resume line is the one that does not follow the pattern, and its failure is misleading: its permissions are already open to any internal user, but a native record rule only lets someone create the resume line of their *own* record, so creating one for a brand-new colleague was refused outright. The inherited group is exempt from that rule, which is another reason it was the right vehicle.
- No job-queue permission was needed even though creating a teacher enqueues the Google Workspace account job: the queue stores its jobs with elevated rights already.

## Deletion is bounded by an unsatisfiable record rule:
- The inherited HR group does grant deletion of staff records, which this issue deliberately keeps out of reach. Record rules only ever grant, never deny, so the way to express "this group never deletes" is a rule whose domain matches nothing: it contributes nothing to the permission check and the operation is refused unless another rule allows it.
- A counterpart rule keeps the two administrator groups exactly where they were on all three operations. Without it they would inherit both restrictions, since the academic Administrator sits above the Head of Studies in the chain.

## Pre-existing limitation found and documented:
- Writing the no-regression tests surfaced that deleting an employee end to end has never been possible below the technical Settings administrator: the delete cascades into the personal calendar, where only that group has deletion rights. It goes unnoticed because the real administrator account holds it. Documented rather than fixed, since it predates this issue and staff are archived rather than deleted in practice.

## Test coverage:
- New backend test class (26 tests) covering both groups: create and edit a teacher, refusal on ASP records, refusal on deletion, no regression for a plain teacher, and the administrators keeping their existing access.
- Also covered: reading and writing the personal email, which no other role may do, and the fact that the account creation refuses to run without it.
- New browser tour driven by a real Head of Studies session (not admin) that edits a teacher and creates a new one, filling in the personal email from the main screen. It is what proves the whole five-model creation chain works end to end through the interface, and it doubles as the regression test for the personal email being reachable without opening a tab.

## Documentation:
- Developer documentation extended with the staff-management design: why the native HR group is the vehicle, what the record rules narrow back down, the full five-model creation chain, and why deletion is bounded the way it is.
- New trilingual manual for the Head of Studies covering how to create and edit teachers, create the corporate Google account, and what the two deliberate limits are (no deletion, no ASP records), linked from the section index in the three languages.
- The teacher roles manual now documents the TAC coordinator post and the fact that the Head of Studies, Deputy and Director can create and edit teachers.
- Fixed a stale reference in the role hierarchy documentation: role-to-group wiring has lived in `data/cat/ems.role.csv`'s own `group_id/id` column for some time, but the document still pointed at a `data/main/ems.role_group_relationship.xml` file that no longer exists.
