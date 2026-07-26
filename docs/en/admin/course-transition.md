[Català](../../ca/admin/course-transition.md) | [Castellano](../../es/admin/course-transition.md) | [English](course-transition.md)

---

# Setting Up the Next Course

At the end of the school year, one operation closes the outgoing course and opens the next one: **Settings → EMS Management → Set up the next course**.

It archives the year that ends, turns the students already marked as graduated into former students, and moves everyone else into the group they enrolled in for the coming year.

> **Only administrators** see this button, and part of what it does **cannot be undone**. Read this page before using it.

---

## Before you start

Four things have to be in place. The wizard checks the first three itself and refuses to run if any is missing.

1. **The incoming course exists** and is different from the current one.
2. **The evaluations are closed.** The last round of every group in scope must be in the *Finalised* state. If some are still open, the wizard lists them; close them from **Grades → Change grade session state**.
3. **No graduate is enrolled for the next course.** A student cannot both leave and come back in the same run; either the graduation mark or the enrollment is wrong.
4. **A database backup.** The wizard asks you to confirm you have one, and will not apply anything until you tick the box.

Mark the graduating students *beforehand*, with the graduation wizard from the student list. The transition does not decide who graduates — it only executes marks that are already there.

---

## Study by study, not all at once

Studies do not finish at the same time: a vocational cycle may be closed in June while an ESO level is still evaluating. So you choose **which studies** to transition, and you can run the wizard as many times as you need.

The **current course only switches on the run that leaves no study pending**. Until then, everything you have transitioned is already done, and the centre keeps working on the outgoing course for the rest. The preview always tells you which one you are about to trigger.

---

## Step 1 — Preview

Open the wizard, check the incoming course and the studies, and click **Preview**. Nothing is written: it is a rehearsal.

You get a red box if something blocks the run, a blue box with everything worth knowing, a counter panel, and the **list of students one by one** with the action each will receive:

| Action | Meaning |
|---|---|
| **Graduate** | Marked as graduated: becomes a former student and is archived |
| **Place in destination group** | Has a confirmed enrollment with a group: moves there |
| **Enrolled without group** | Confirmed enrollment with no destination group: **will be skipped** |
| **No destination** | No enrollment at all for the next course |

Two of these deserve your attention:

- **Enrolled without group** — the enrollment exists but nobody chose the group, so the student stays where they are. Assign the group (the *Suggest group* action helps) and preview again.
- **No destination** — the student has not enrolled. They are **not** withdrawn: they simply end up with no group. This is deliberate, because in July there is no way to tell someone moving to another school from someone who enrolls late. Keep this list: it is the one you will review afterwards to decide who really left.

---

## Step 2 — Apply

Tick **I have taken a backup** and click **Apply the transition**. You will be asked to confirm once more.

What happens, in order:

1. The **academic history** of every student is frozen. If this fails, nothing else runs.
2. Graduates become **former students**, their portal access is revoked and they are **archived**.
3. The attendance templates of the outgoing year are archived.
4. The **operational records are deleted**: subject enrollments, grades, attendance and evaluation sessions. This is the irreversible part — the academic history, saved in step 1, is what replaces them.
5. Students are placed in their **destination group** and enrolled in its subjects.
6. The studies are marked as transitioned and, if none is left pending, **the current course switches**.
7. The outgoing enrollments are closed: the confirmed ones are locked (they are a legal record and are never cancelled), the ones that never got confirmed are cancelled.

---

## Afterwards

The wizard leaves a **log with the list of students and their destination group**, downloadable at the end and also attached to the company's chatter. Keep it: it is what lets you undo a specific case by hand.

Two loose ends to deal with in the following days:

- **Students with no destination.** Review the list and register the withdrawal of the ones who really left, from the student form. The ones who enroll late need nothing: when their enrollment is confirmed, they are placed in their group automatically.
- **Students enrolled without a group**, if you applied without solving them: assign the group and confirm; they are placed the same way.

---

[← Back to the administrator index](index.md)
