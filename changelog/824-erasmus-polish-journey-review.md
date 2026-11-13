# Changes

## Staff application form follows the new annex 1 and 2 of the rules:

- The form (backend dialog and portal) explains the mobility plan in one line ("the training activity, the destination and the dates of your mobility; B is in case A can't be done; in each one, say what you want to learn"). What the teacher wants to learn now goes inside each proposal, with the examples of annex 1 as placeholders; the separate "What to learn and how to apply it" field is gone from the form, the team's record and the panel's rating form (`plan_text` removed; no migration: the 2026-27 staff call was never published in production, Odoo keeps the orphan column).
- First-mobility checkbox reworded "I have not done any Erasmus+ mobility at the Institut Puig Castellar" (ca "No he realitzat cap mobilitat Erasmus+ a l'Institut Puig Castellar"), with a help saying that, as staff, accompanying groups and other programmes don't count (criterion 2). "Centre projects" explains what to write (projects, improvement teams or commissions of this year or the last, one per line, saying which ones you coordinate; criterion 3). Each proposal has a 1,500-character counter on the portal.
- Criterion 1 is now "Mobility plan" with two aspects of up to 1 point, as in annex 2: *Concreteness* (`concreteness`) and *Relevance to the job* (`relevance`), replacing "Relevance and concreteness" and "Application to the job" (`transfer` removed; same selection keys, no migration needed).

## A teacher ticks their steps on return only once the stay has started (P17):

- A step before leaving, while the mobility is open (as before); a step on return, from the phase Stay onwards (Return and Closed too), since the news item is often written on the last day. The Erasmus+ team ticks any step at any time (`RETURN_TICK_PHASES`, `_compute_staff_can_tick`).

## The project's "Services paid by the centre" tab lists its participants' and groups' invoices (C34):

- New non-stored `all_invoice_ids` on the project (`_ems_invoices()`, the same set the figures already count): an invoice for participants with no project of its own now shows on their project, with an optional *Project* column saying *Various* when it covers two. The invoice's project is not filled in and no figure changes.

## Clearer names on the call and the teacher's application:

- The call's last phase is *Places assigned* instead of *Finished* (C23): it only means no offer waits for an answer, while students may still be choosing their destination.
- Once the teacher's application is submitted and can still be changed, its button says *Modify the application* instead of *Fill in the form* (P05, P08).

# Fixes

## Layout and translation fixes from the journey review:

- "Step 6 of 8" on the mobile portal was in English: its "of" had no Catalan/Spanish translation (now "Pas 6 de 8" / "Paso 6 de 8").
- The project's Mobilities tab: the *Open the record* button is an icon with its name as tooltip, so it is no longer cut on the right (C33).
- The call's Destinations tab: the label "Destination choice open" no longer wraps under the table (Odoo's `o_label_nowrap`, C23).
- *Satisfaction surveys* and *Low scores*: course, host entity and comment start hidden in the column picker, so call, participant, type and cycle are no longer cut (C44, C45).
