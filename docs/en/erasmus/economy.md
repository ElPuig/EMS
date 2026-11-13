[Català](../../ca/erasmus/economy.md) | [Castellano](../../es/erasmus/economy.md) | [English](economy.md)

---

# Economic management of the projects

For each Erasmus+ project EMS shows how much grant it has, how much has been received from SEPIE, how much the mobilities and the expenses commit, how much has been paid and how much is still available. Everything is calculated from what is already in EMS: the grant of each mobility, the grant payments, the invoices and the expenses. You don't need to type any amount twice.

**Required role:** Erasmus+ team (the coordination). The Secretary registers and pays expenses; the Director only reads.

---

## The projects

**Erasmus+ > Projects**, its own entry in the bar between Mobilities and Financial management, shows one row per project: *Awarded*, *Committed*, *Paid*, *Available*, *Support generated* and how many warnings it has. You can filter by kind (KA121-VET, KA131-HED), by whether the final payment has been received, or the projects *Above the grant*, and group them by call year. The **pivot** view compares calls and kinds of project side by side: it opens with the grant, what is committed and what is available (the other figures, under **Measures**). To see older, archived projects, use the **Archived too** filter.

Click a project to open its **Economy** tab.

## The Economy tab of a project

The tab reads from top to bottom in the order the money flows. The **Subsidy** block has the centre's subsidy (not a participant's grant): awarded, current, received and to receive, and the final grant and the date of the final payment once that payment arrives. The **Budget** block has the forecast, what is committed with the project's other expenses right below it, what has been paid, what is committed and not paid yet and, last and in bold, what is available.

1. **Grant awarded** is the amount of the agreement. Add each **grant amendment** (date, description, amount; negative if it reduces the grant): the *current grant* is the initial grant plus the amendments.
2. Add each **SEPIE transfer** (date, kind, amount). They tell you what has been *received* and what is still *to receive*. The *Balance* transfer also fills in *Final payment received on*, which sets how long the documents are kept.
3. Attach the **grant agreement and its annexes** in the project's **Documentation** tab, with the category *03 Finances*. They are part of the project's documents and go into the project's export.
4. **Call year** is taken from the agreement number (e.g. 2025-1-ES01-...). Correct it if needed: it decides which organisational support rates apply.

**What each figure means:**

- **Forecast:** the grants of the mobilities whose destination is still being defined, and of the group mobilities before the selection is approved. They don't use any budget yet.
- **Committed:** the grants of the confirmed mobilities (from *Preparation* to *Closed*) plus the project's other expenses.
- **Paid:** what has been transferred to the participants, plus the paid invoices and expenses.
- **Committed, not paid yet:** everything committed that has not been paid yet, whether or not its payment has been requested.
- **Available:** current grant minus committed. It is **not** the money in the bank: a project can have an awarded grant still to be transferred by SEPIE.

**Paying doesn't count twice.** A grant of 1,500 € counts as 1,500 € committed as soon as the mobility is confirmed. When the Secretary pays the advance and then the rest, the 1,500 € only move from *pending* to *paid*. The same goes for an invoice paid out of a participant's grant (flights, accommodation): it is part of their grant, not an extra expense.

## Each mobility

On the **Grant** tab of a mobility, the *economic state* (forecast, committed, partially paid, paid, cancelled) shows as a tag on top, and two blocks read from left to right with the same names as the participant's portal: **Grant** (the grant, what is **Paid directly by the centre** such as the flights or the accommodation, and what is left **To transfer**) and **Payments to the person** (what has been **Transferred**, what is **Pending transfer** and the percentage paid **Before leaving**). Below, the services the centre paid for them and the payments. What the mobility commits of the budget is counted on the project. *Organisational support as* (money for the centre, not for the person) is folded away at the bottom: open it only to correct the kind of mobility by hand. If you change the grant, the commitment changes by the difference. If you move the mobility to another project, its figures move with it.

**A cancelled mobility** only keeps committed what has already been paid. If the participant gives money back, write it in **Given back by the participant**. Until then, the project shows a warning.

**Group mobilities:** each participant, student or accompanying teacher, has their own grant, as calculated in the Beneficiary Module. Enter them on the **Grant and expenses** tab, in *Participants' grants* (once the selection is approved). The group's figures add them up, each one once: the group's grant above the list is the total (a withdrawn participant never counts). What has been spent of them is the group's collective invoices plus each participant's pocket money (their grant minus their equal share of the invoices), requested from the group and paid by the Secretary: nothing is counted twice. See *Grants and pocket money* in [Group mobilities](group-mobilities.md).

## Services paid by the centre

**Financial management > Services paid by the centre** holds the invoices the centre pays for someone: flights, accommodation, course fees... They are deducted from the grant of whoever they are for, so they are not project expenses (an expense that is nobody's goes in *Project expenses*). The Erasmus team and the Secretary both enter them, whoever receives the invoice.

1. Click **New** and fill in the invoice number, the supplier, the concept, the amount and the project.
2. Answer **Who it is for**: *Participants* (choose them: the amount is split equally among them and shows in their *Paid directly by the centre*) or *A group mobility* (choose it: the amount is split among its participants through their pocket money). Only the field of the answer shows. While nobody is chosen, a warning suggests registering it as a project expense instead.
3. The Secretary pays it like a grant payment. Its history, at the bottom of the form, keeps every change, for example a transfer undone with its reason; the grant payments show theirs too.

The project's **Services paid by the centre** tab lists every invoice that touches the project: its own, its participants' and its group mobilities', the same ones its figures count. An invoice for participants of two projects shows in both, with *Various* in its *Project* column (in the column picker); leave its own project empty.

In the list, the **Project** column shows the invoice's project or, for a participants' invoice, their mobilities' one; when they are of different projects it says *Various*.

## Project expenses

**Financial management > Project expenses** (or the project's **Project expenses** tab, next to *Services paid by the centre*) holds the project's expenses that are not part of a participant's grant: working meals, merchandising, dissemination services, language preparation...

1. Click **New** and fill in the project, the concept, the category (*Organisational support* or *Other project expenses*), the date and the amount. Optionally, the supplier, the mobility it is about (only the Erasmus team can choose it) and the invoice or receipt.
2. The expense counts as committed as soon as it is saved, and the Secretary gets a task to pay it. Paying it doesn't take it off the budget again.
3. While it is not paid you can change it. Once paid, its figures only change with **Actions > Correct**: write the new figures and the reason. The reason stays in its history and the project warns that it was changed after payment.
   - **If the new amount is higher than what was transferred**, the expense keeps the amount already paid and EMS creates a new expense for the difference, *to pay*, with a task for the Secretary. Example: a working meal of 75 € was paid, but the real ticket was 80 €. You correct it to 80 €: the original stays at 75 € (paid) and a new expense of 5 € is to pay. The original's history says so.
   - **If the new amount is lower than what was transferred**, the expense takes the new amount, but the project keeps counting what was really transferred and warns: "<reference> was paid X above its corrected amount: ask for it back, then undo the transfer and register the right one."
   The expense lists show one amount per row, **Amount**: the one that counts (a cancelled expense counts 0; a corrected one, what was really transferred). The amount typed in is on the expense, or in the *Amount entered* column of the column selector.
4. An expense that won't be paid: **Actions > Cancel the expense** (it stops counting). **Restore** brings it back.

## Organisational support

The organisational support is money to manage the mobilities, separate from the participants' grants. EMS calculates it per participant with the **rates of the project's call year**, not the current year's. The rates of KA121-VET 2025 and 2026 and KA131-HED 2026 are already in **Erasmus+ > Configuration > Organisational support rates**, grouped by year, the newest year first; when a new call comes, add its year's rates there.

**The 100-participant rule (the "From participant / Up to participant" columns):** some rates drop after the 100th participant. In KA121-VET it counts the participants of the same kind of activity: a short-term student or a job shadowing is 350 € up to the 100th and 200 € from the 101st. In KA131-HED it counts everyone in the project, students and staff together: 400 € for the first 100 and 230 € from the 101st. EMS counts them by start date and fills in who counts (the hidden column **Count the participants of**) from the action; you don't need to do anything.

**Empty means no limit:** an empty *Up to participant* is a band with no end, and an empty *Minimum days* applies to any length of stay. If two bands overlap, EMS tells you which other rate and band they clash with. In the Excel, the *Position* is the one the rate counted: among the same kind of activity or, in KA131-HED, among the whole project.

![The rates of a year: the empty cells mean no limit and any length of stay](../../assets/erasmus/tarifes-suport-organitzatiu.png)

**Which rate each mobility takes:** EMS works it out. A student's stay of 90 days or more is long-term (ErasmusPro), shorter is short-term; a staff member's structured course is *courses and training*, job shadowing or teaching the other one; each student of a group mobility, 100 €. If a mobility is in a third country not associated to the programme, or is a skills competition, an invited expert or a hosted teacher, choose it by hand in **Organisational support as** on its **Grant** tab.

On the Economy tab you see:

- **Organisational support forecast:** for the planned mobilities (for a group still selecting, its student places).
- **Organisational support generated:** for the completed mobilities, with the real participants. Accompanying teachers never count.
- **Organisational support expenses:** the expenses of that category, and the difference between generated and spent.

The difference is an internal indicator, not a certification of SEPIE. The support is part of the grant awarded: it is never added to it. For a particularity of the agreement, enter a **Correction** with its reason. For a project managed before EMS, you can fill in the aggregated **Figures from before EMS** (only shown on projects of calls before 2026, or once they have a figure).


## Warnings

At the top of the Economy tab, EMS warns about anything that may be a mistake, without blocking anything: commitments above the grant, expenses without an invoice or receipt, requested payments still to make (only those already asked of the Secretary and not transferred yet, so the figure can be lower than *Committed, not paid yet*), expenses changed after payment, expenses paid above their corrected amount, a mobility paid above its grant, a cancelled mobility with money paid, and participants without enough information to calculate the organisational support (for example, no rate for their call year, or no dates). If the project has no grant amount yet, the warning only says it is missing (*Grant awarded*), instead of a figure above zero; and if the organisational support rates of its year are missing, a single line says where to add them (**Configuration > Organisational support rates**).

## Excel

**Actions > Download the economy (Excel)** downloads the project's economy: a summary with the same figures as the projects list, each mobility's grant (forecast, committed and paid separately), the payments and invoices with their receipts, the expenses, the organisational support participant by participant, and the grant amendments and SEPIE transfers.

---

[← Back to the Erasmus+ team index](index.md)
