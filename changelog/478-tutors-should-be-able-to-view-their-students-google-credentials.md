# What's new

## Tutors can view their students' Google credentials:

- The student form's Documentation tab is now visible to group tutors, showing only the Google Workspace credentials PDF of the students they tutor, so they can download it and hand it over without asking the secretary's office.
- Read only: tutors cannot approve, reject, reopen, create or delete documents, and the review buttons are hidden for them. ID card, IBAN, medical card and benefit documents stay restricted to secretary and admin.
- Secretary and academic admin keep full access even when they also tutor a group (new unrestricted record rules for both, since the academic admin inherits the tutor group).
- New tutor manual "Viewing your students' Google credentials" (ca/es/en).

## Bulk download of Google credentials from the students list:

- New "Download Google credentials" entry in the students list's Actions menu (academic admin, secretary, tutor), next to "Portal access" and "Send authorizations": one ZIP with the latest credentials PDF of each selected student, each file prefixed with the student's name.
- Runs with the user's own rights: tutors only get their own students' PDFs, and the download route re-checks access rather than trusting the ids in its URL. Selecting only students without readable credentials shows a warning instead of an empty download.
- Documented in the tutor and secretary manuals (ca/es/en); the tutor manual has two screenshots, generated from invented data by a new method in the screenshot capture test module.

## Reset a student's Google password:

- New "Reset Google password" button on the student form header, shown while the Google account is active and behind a confirmation. It sets a new random password in Google (forced change at next sign-in) and delivers new credentials exactly like account creation: a new credentials PDF in the Documentation tab and the welcome email to the personal address. The previous credentials PDFs are marked cancelled, and the chatter records who did it.
- Only academic admin and the TAC team (`ems.group_tac`), checked in the method too, not just by the button's groups. The secretary stays out: it only takes part in account creation as a step of enrolling a student. Individual only, no bulk reset.
- The TAC team can now read every student's Google credentials PDF (read only, no other document type) and use "Download Google credentials".
- Requires the service account's Google admin role to include the "Reset password" privilege on the student OUs; a refusal from Google is reported with that hint and leaves the previous credentials untouched.
- New admin manual on the student Google account (ca/es/en, with a screenshot), and the TAC coordinator description in the roles manual now lists this permission.

## TAC team can create and suspend student Google accounts:

- The "Create Google account" and "Suspend Google account" buttons on the student form header are now also available to the TAC team (`ems.group_tac`), alongside secretary and academic admin. Reactivate, delete and cancel-scheduled-deactivation stay with secretary and admin.
- The chatter notes of both actions are now posted with `sudo()` (still authored by the real user), since posting on a student needs write access that the TAC team, who only reads students, does not have.
- The admin manual became "Managing a student's Google account" (create, suspend, reset password, download credentials), with an updated header screenshot, and the TAC coordinator description in the roles manual lists these permissions.

