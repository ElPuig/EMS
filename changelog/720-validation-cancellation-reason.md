# What's new:

## Convalidations: a reason is required to cancel a request from the backend:
- Cancelling a convalidation request from its form (Actions > Cancel request; Head of Studies, secretariat, administrator) now opens a dialog with a required Reason, in the same style as the Director's "Return to the Head of Studies". The bare confirmation is gone.
- The reason is stored on the request (`cancel_reason`), shown on the form and on the request's card in the student/family portal, and included in the "Convalidation request cancelled" message on the portal's Communications page. Reopening the request clears it.
- The applicant's own cancellation from the portal is unchanged and asks for nothing (developer's choice for #720).
- The cancellation itself moved to a private `_ems_cancel(reason)`, used by the portal and by the new `ems.convalidation.cancel_wizard`; the public `action_cancel` only checks the state and opens the dialog, so the backend cannot cancel without a reason.
- Tests, a secretary tour of the dialog, developer docs, Head of Studies / secretariat / families manuals (ca/es/en) and ca/es translations updated.
