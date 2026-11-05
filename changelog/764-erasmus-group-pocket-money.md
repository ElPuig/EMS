# What's new

## Erasmus+ group mobilities: pocket money paid to each participant (issue #764):

- Every participant of a group mobility (students and accompanying teachers) now receives their pocket money: their own grant minus their equal share of the group's collective invoices (flights, accommodation...). EMS splits each collective invoice equally among the participants taking part (the cents left over on one of them) and shows, on the Collective expenses tab, each one's grant, share, pocket money, requested, paid and state (models/erasmus/pocket_money.py).
- "Request the pocket money" (group form, Actions; Erasmus team, from Preparation on) creates one grant payment per participant with something to receive; "Pocket money before leaving (%)" (100 by default: a single payment) and "Request the final pocket money" on return for the rest. A participant without a bank account blocks the request, naming them.
- The Secretary pays them like any grant payment (Grant payments menu, with a new Group mobility column, filter and grouping, or "Register the transfer of the whole group" from a payment), with one task per group in their daily summary instead of one per payment, kept up to date as payments are paid or undone.
- "The centre pays nothing directly" option on a group mobility: no collective invoice can be added (blocked, with a notice) and each participant receives their whole grant.
- Bank account for the pocket money: students give it on the group's portal page (or the one of their enrolment is used), teachers from "My bank account" on the group mobility (validated IBAN). The portal shows the student their grant, the centre's share, their pocket money and its payments, with the same table as the individual mobilities.
- The group's economic figures count the pocket money payments together with the collective invoices, nothing counted twice; the project's warnings flag collective invoices above someone's grant and a participant who withdrew after being paid; the Excel export lists the payments as "Pocket money". Closing a group mobility waits until every pocket money payment and every collective invoice is paid.
- The leader teacher now sees the Collective expenses tab (invoices, grants, pocket money and payment states, never the bank accounts): read access to the group's own invoices for its teachers, with an "all" rule so it never narrows the team, the Secretary or the Director.
- Manuals for the Erasmus team, the Secretary, teachers and families (ca/es/en), developer doc (docs/en/developers/erasmus/economy.md), Catalan and Spanish translations; tests in tests/test_erasmus_pocket_money.py with a tour for the mobility technician and the Secretary.

# Internal changes

## Grant payments shared by individual and group mobilities (issue #764):

- New abstract ems.erasmus.payee (models/erasmus/payee.py) with the first/final payment logic, what is left to pay and the portal rows, used by individual mobilities and group participants; ems.erasmus.payment gets group_participant_id/group_mobility_id (mobility_id no longer required, exactly one of the two, checked in SQL), and its participant, call and project are stored computes. Invoice shares and the pocket money use the same split helper. No migration: new columns only.
