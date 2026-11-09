# Changes:

## Erasmus+ call notices reach each audience the right way (#802):
- The notice of an open staff call and the reminder before it closes no longer go out as separate emails: they are queued for each person's next daily summary (`ems.info_notice` on the call), in their language, with the closing date and where to apply, following the daily summary rule (a notice to staff that asks for no action and isn't urgent is never sent on the spot). The summary's link opens the call in the staff's own form. The count, the chatter line and the Quality diffusion action stay.
- Every Erasmus+ email to a student goes to their school address (`student_email`), never the personal one (adriamt, 2026-11-09): the call's notice and reminder, receipts, results, place offers, claims, mobility documents and reminders, group mobilities and the satisfaction survey, through one helper (`res.partner._ems_erasmus_email`). Students without it get nothing (noted on the application, counted in the notify dialog as "Without a school email address"); families keep getting their copies at their own address. The only exception is the electronic signature request, which OCA's signature module always sends to the contact's main address (the student can also sign from the portal). On the dev database 169 of 1,173 students had only the school address and were left out before.
- The notify dialog explains, for each audience, how the notice is delivered. The staff paragraph of the open-call email template is gone (staff no longer get that email).

## Erasmus+ staff application shows where to write (#802):
- Applying to a staff call (or opening an application still empty) opens the form's dialog straight away while the application can be changed; saving it opens the application. Until something is answered, the application hides its empty "Form" tab, and its "what to do now" box says where to fill it in (Actions > Fill in the form). The entry stays in the Actions dropdown.

# Related with:
- Closes #802
