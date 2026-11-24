# Changes

## Portal access wizard simplified (choose who, regenerate credentials):

The portal access window now has three actions: grant, regenerate credentials and revoke. Each recipient has an "Apply" box, ticked by default where the action makes sense, so access can be granted, regenerated or revoked for only some of them. "Regenerate credentials" sends a new password link to anyone who already has access, replacing "Resend invitation" (which only reached people who had never logged in), so families and students (with their personal email) who forgot their password can recover it.

## Clear popup when a portal login is already taken:

When access cannot be granted because another contact already holds that login, a popup lists which contact has it (type, login, active or archived), whether it is assigned to the student, and what to do (merge or archive a duplicate, or give one of them a different email).

## Stricter email rules for students and families:

A family contact can never have a centre (corporate) email, and a student's personal email can never be the same as their family's: the forms refuse to save it. When an import brings a single email shared by both, a minor's stays with the family (the student is reported as needing their own) and an adult's stays with the student.

# Fixes

## Revoking portal access now unchecks it:

A revoked access (archived portal user) was still shown as current access in the wizard.

## Changing the email of a contact whose portal access was revoked:

The form now warns that the access stays revoked and how to grant it again.
