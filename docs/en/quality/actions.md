[Català](../../ca/quality/actions.md) | [Castellano](../../es/quality/actions.md) | [English](actions.md)

---

# Actions and agreements

A **meeting agreement** and an **improvement action** are the same thing: somebody commits to doing
something, by a date, and somebody has to follow it up. That is why in EMS they are one screen:
**Quality → Actions and agreements**.

It means the question that used to require opening eight documents — **what do I owe and by when** — is
answered in one place.

---

## How the screen opens

With two facets already applied: **Open** and **Current course**. Remove one and you also see closed
items, or earlier years.

Other useful facets: **Overdue** (past their deadline and still open), and by type: meeting agreements,
improvement actions, or corrective and preventive ones.

## Creating an agreement

1. **New**.
2. Fill in the subject: what was agreed.
3. Set the **type**. For a meeting agreement, leave *Agreement*.
4. Set the **responsible post** and, if needed, the **responsible people**. Both can be filled in: the
   centre's records often say "management team and department heads" or "one person plus volunteers", and
   that should not be lost.
5. Set the **scope**: department, workgroup, group, or *Centre-wide* for staff-meeting agreements. The
   scope is what the code is numbered against.
6. The **deadline**: put a date if you have one. If the agreement said "by the final meeting of the
   year", write that in **Deadline (as agreed)** and leave the date empty.
7. Save. The **code** is issued automatically: `ACORD-<scope>-<course>-<number>`.

## The code and the numbering

The counter runs **per scope and course**, so a department's agreements are consecutive: if a
department's list shows 003 and 005, 004 is missing and it shows. That is why there is no global number.

## The state is not edited: it is derived from the follow-up

An agreement's state is **not picked from a dropdown**. It comes from the latest follow-up entry:

| Situation | State |
|---|---|
| No owner and no deadline | New (pending) |
| Owner or deadline, but no follow-up yet | Analysed (planning) |
| With follow-up | The state of the latest entry |

So moving an agreement forward means adding a follow-up entry in the **Follow-up** tab: the date, the
state it leaves it in, and what happened. This is deliberate: it forces the **reason** for the change to
be written down, which is exactly what an audit asks for.

## Closing an agreement

Add a follow-up entry with state **Closed** and say how it was resolved. The **Closure** tab is where the
criteria go beforehand: when it will be considered finished and how efficacy will be measured.
