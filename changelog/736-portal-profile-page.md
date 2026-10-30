# What's new

## Portal profile page shows the school data and every reviewable contact detail:

- The read-only Profile page (`/my/account`) of students and families is reorganised in blocks. School details (photo, name, IDALU, birth date, group, study, tutor with their email, corporate email) are marked as corrected only by the secretary's office. The account's own contact details are exactly the fields `/my/dades-contacte` lets it send (mobile, landline, personal email, address, DNI/NIE, passport, TIS, NUSS for a student; name, mobile, email, address, DNI/NIE, passport for a family contact). On the student's own account, the family contacts on file are listed too.
- The contradictory "your personal data is read-only" notice is gone: the page says what only the secretary's office corrects and what can be sent for review, shows whether the school asked for the review, whether the changes are waiting for it or were returned (with the reason), and tells a minor that their family updates the details.
- Fields no portal page can change (VAT, street 2, state, country) are no longer shown.

# Internal changes

## Shared lookup of the running contact data request:

- `res.partner._ems_contact_data_running_request()` replaces the two copies of the "request of the running academic year" search (the home banner and `/my/dades-contacte`), and also feeds the profile's review status.

# Related with

- Closes #736
