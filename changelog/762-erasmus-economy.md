# What's new

## Erasmus+ economic management of the projects (issue #762):

- Each project now has an Economy tab (its first one) with the grant awarded, its amendments and the final grant, SEPIE's transfers (received and still to receive), what its mobilities and expenses commit, what has been paid, what is pending and what is available, plus the grant agreement and economic documents (category 03 of the project's documents, so they stay in its export). The call year comes from the agreement number and decides the organisational support rates (models/erasmus/economy.py, views/erasmus/economy/).
- Every amount comes from what EMS already holds: a mobility's grant is a forecast while its destination is being defined (a group mobility, until its selection is approved) and committed once confirmed; the grant payments and the invoices paid out of it move it from pending to paid, never as a second expense; a grant change, a cancellation (only what was paid and not given back stays committed) or a change of project just recomputes. In a group mobility each participant, student or accompanying teacher, has their own grant (entered on the group's Collective expenses tab); the group adds them up, each counted once, and its collective invoices are what has been paid of them.
- New project expenses (Financial management > Expenses) outside the participants' grants, in two categories (organisational support, other project expenses), with a reference, receipt and supplier: registered by the Erasmus team or the Secretary, paid by the Secretary with the same transfer wizard as grants and invoices, and once paid only changed through "Correct", which keeps the reason in its history.
- Organisational support calculated participant by participant with the rates of the project's call year (Configuration > Organisational support rates: per action, kind of mobility, band of participants counted per kind of activity in KA121-VET or across the whole project in KA131-HED, and minimum days; the KA121-VET 2025/2026 and KA131-HED 2026 rates are seeded from data/custom/erasmus/ems.erasmus.support.rate.csv; each mobility's kind is worked out from its dates and activity, with the third-country and other special cases set by hand), forecast on the planned mobilities and generated on the completed ones, never counting accompanying teachers; a justified manual correction, the support expenses and the difference between generated and spent, as an internal indicator.
- Economic panel (Financial management > Economic panel): one row per project with awarded, committed, paid, available, support generated and warnings, filters by action and final payment, and a pivot view to compare calls; aggregated figures can be entered for projects managed before EMS. Warnings (never blocking) for commitments above the grant, expenses without receipt, payments to make, changes after payment, cancelled mobilities with money paid and participants without enough data for the organisational support.
- "Export Excel" on each project: summary (the same figures as the panel), grants, payments and invoices with their receipts, expenses, organisational support and the grant's amendments and SEPIE's transfers.
- Permissions enforced in the backend: the Erasmus team manages everything, the Secretary reads the budgets, registers and pays expenses and exports, the Director reads everything (including invoices and grant payments, never the participants' bank accounts) and changes nothing. Manuals for the Erasmus team, the Secretary and the Director, developer doc docs/en/developers/erasmus/economy.md, Catalan and Spanish translations.

# Changes

## Erasmus+ satisfaction surveys visible with names to the whole Erasmus+ team (role review 2026-11-05):

- adriamt decided the answers are not anonymous for the Erasmus+ team: the mobility technician now sees who answered, like the coordinator (models/erasmus/satisfaction.py NAMES_GROUPS). Nobody else does, and the PDF report and the Mobilitat FP ZIP still carry no names. Only the coordinator closes a survey without an answer, writing the reason first (no confirmation dialog).

## Correcting a paid expense upwards leaves the difference to pay (role review 2026-11-05):

- adriamt's decision: what was transferred stays paid and the difference is a new expense (`corrected_from_id`) with a task for the Secretary; corrected downwards, the project keeps counting what was really transferred (`transferred_amount`) and warns to ask for it back. Expense lists total a new "Counted" column (a cancelled expense counts nothing).

## Erasmus+ economy and quality polish from the role review (2026-11-05):

- Expenses: the Secretary pays several from the list ("Register transfer" header button, as the manual said); only the Erasmus team links an expense to a mobility; no Duplicate. Rates: empty limits explained, the overlap error names the other band. Call year shown without a thousands separator, one label for the current grant, the SEPIE transfer column is "Type", the Excel kinds of mobility and transfers translated, the group's participant list no longer totals a withdrawn participant's grant, a negative "to transfer" explained.
- Quality: the panel opens titled "Quality indicators" and explains that a project's interest is that of its calls; the PDF keeps each heading with its table and gets a proper file name; the Mobilitat FP ZIP says why the management folder is empty and writes dates as dd/mm/yyyy; a pending survey shows on the portal's home too and says it is not the EU Survey; reopening an answered survey thanks instead of a silent redirect; the staff to-do is due the day it opens; figures rounded half up; the quality panel counts each call's interest once (faster).

# Fixes

## Erasmus+ economy and quality fixes from the role review (2026-11-05):

- Adding a grant amendment, a SEPIE transfer or a document, or changing the support correction, in the Economy tab of a project with mobilities or expenses crashed (records sorted, and expense references built, from an id they did not have yet in the unsaved form).
- A file uploaded with a new expense, amendment, SEPIE transfer, project document or diffusion action stayed readable only by its uploader, so the team and the Director got an access error opening the expense or the whole project: files now belong to their record (new `ems.attachment_link_mixin`, which `ems.attachment_mixin` builds on).
- The calls' funnel counted a cancelled mobility twice (as renounced and as cancelled).
- The organisational support position shown for whole-project bands (KA131-HED) was the one among the same kind; a missing-rate warning could be lost.
- The survey's improvement action link gave an access error to team members outside the Quality app; it now shows without a link for them. The Secretary got an access error saving an expense linked to a mobility. Spanish "Puntaje" is now "Puntuación".
- New tests for each of these, plus the warnings, a partially given back cancelled mobility and a withdrawn group participant.

# Related with

- Closes #762
