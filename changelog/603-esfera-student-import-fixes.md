# What's new

## Esfera import can skip Google account creation:
- New "Create Google accounts" option in the Esfera import wizard. Unticked, every imported student without a corporate email is marked "Assign corporate email manually" (new field on the student, same as the one staff already had), so EMS never creates a Google account for them, not even on a later edit of their form. Needed when the accounts were created outside EMS: the automatic creation would otherwise find the address taken and create a second account.
- New "Waiting for the manual corporate email" Google account status for those students; the "Create Google account" action is hidden until the existing address is filled in (by hand or with the student data update wizard).

## Esfera import shows it is working:
- The import wizard now blocks the screen with an "Importing the students…" message while it runs, as the grade and schedule imports already did, instead of only greying the button out (a class of 120 students takes ~20 seconds and looked frozen).

# Fixes

## Esfera import data quality:
- First name and last names are stored separately, so compound first names ("Maria José") are no longer split on the first space (students and family contacts).
- The address street number is read again: Esfera exports two "Número" columns and the importer was taking the empty insurance one.
- Tutor phone and email are told apart by their content, whatever order Esfera exports them in; before, an "email - phone" value stored the email as the phone and lost the family's email.
- No review note is added to the student when the tutor observation is empty (" - ").
- Yes/no columns (emancipated, guardianship, shared custody, tutor notifications...) are only noted when "Sí", avoiding false notes such as "Alumne emancipat legalment: CR".
- A tutor without a country takes the student's, so their province is filled in too.

## Google account no longer "reactivated" for every imported student:
- Re-importing students who are already active used to queue a Google account reactivation for each of them, because the import writes "active" on every existing student to bring back former ones. In production that meant one Google call per student, moving every account to the minors/adults unit, and a refused call made EMS recreate the account. Only a student actually coming back (unarchived, or from ex-student to student) is reactivated now.

