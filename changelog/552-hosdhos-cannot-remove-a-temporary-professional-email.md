# Fixes

## Head of Studies could not change a linked teacher's work email or mobile:
- A Head of Studies/Deputy (or TAC, or the secretariat) editing a teacher who already has an EMS
  user got "You are not allowed to modify 'User' (res.users) records" when removing or fixing its
  manual corporate email, or changing its work mobile. Odoo writes both fields to the linked
  user's own contact and demands "Access Rights" for that.
- The employee's work contact is now written as superuser once the employee's own write check
  has passed, so whoever may edit the employee may edit these two fields too. Users holding
  "Access Rights" keep the native guard (their email also receives their password reset).
