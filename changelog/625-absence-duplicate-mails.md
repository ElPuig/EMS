# Changes:
## The approver's email for a new absence request carries its details (#625):
- Whoever has to approve an absence request used to get Odoo's generic "an activity has been
  assigned to you" email, which named the request and nothing else. They now get the same
  summary the department chiefs do (employee, absence type, dates, hours, status) with "It is
  waiting for your approval.", so the cover can be arranged from the email itself. The approval
  activity is still scheduled on their list; only its email is replaced
  (`hr.leave.activity_update()`).

# Fixes:
## No more two automatic emails for the same absence event (#625):
- Approving an absence emailed every follower twice in the same second: EMS's summary and
  Odoo's own "Status: Pending → Approved" tracking entry. The tracking entry stays on the
  request as a plain note (`_track_subtype()`); only the summary is emailed.
- The report of an overdue supporting document (or ATRI confirmation) reached the Head as a
  note and, on top, as the "assigned to you" email of the overdue activity. The activity is now
  scheduled without its email.
- An approver who is also the employee's department or seminar chief got both the approval
  email and the chiefs' summary when the request was filed; they now get the approver's only.
- A comment somebody writes on a request still arrives as an email of its own, on purpose.
