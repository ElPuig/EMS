[Català](../../ca/secretary/academic-history.md) | [Castellano](../../es/secretary/academic-history.md) | [English](academic-history.md)

---

# Academic history: per-course student records

This guide explains the **academic history**: a permanent, per-course summary of each student (study, group, subjects with their grades per learning outcome, attendance and academic result). It is a **frozen copy** taken from the grades subsystem at the end of each course (or at the moment of a withdrawal), so it stays available after the operational data of the outgoing year is cleaned up during the course transition.

---

## Contents

1. [What the history contains](#what-the-history-contains)
2. [When records are created](#when-records-are-created)
3. [Consulting the history](#consulting-the-history)
4. [Adjusting the academic result](#adjusting-the-academic-result)
5. [Finals pending the work placement](#finals-pending-the-work-placement)

---

## What the history contains

One record per **student and course**, with three levels:

- **Course summary:** study, level, group, tutor and shift of that course, global attendance rate, number of attendance notifications sent to the family, academic result and whether the title was obtained that year.
- **Subjects:** one line per subject taken, with the internal grade, the work placement (EM) grade, the final grade, the state (**Passed / Not passed**) and the frozen grading weights in force that course.
- **Learning outcomes (RA):** inside each subject, the grade of every RA round by round, with its weight.

> The history is a **copy, never recalculated**: the values are the ones the grades subsystem computed while the course was running, frozen with the weights of that year's teaching plan. Grades keep their meaning even if the plan changes in later years.

The state of a subject depends **only on the RAs**: a student with every RA passed has **passed the subject**, even if the work placement is still pending — in that case only the **final grade** stays empty until the placement is graded. A failed placement is repeated; it never fails the subject.

## When records are created

- **On a withdrawal:** the withdrawal wizard freezes the student's history **at that moment**, before detaching them from their group. A student leaving mid-course keeps the record of everything done until that day (subjects, grades, attendance), with the result **Withdrawn**. Once the history is frozen, the withdrawal **removes the student from everything operational**: their subject enrollments, the grade lines of the live sessions, the attendance lines and templates, and the group's delegate if it was them. From that moment they no longer appear in the group, in the evaluation matrix, in the attendance sessions or in the work placement grading — only in their academic history.
- **On the course transition:** the transition wizard (run by the administrator at the end of the course) generates the records of every active student before cleaning up the operational data.

Re-running the generation never duplicates a record: the existing one is refreshed.

## Consulting the history

Two entry points:

- **Per student:** open the student's form — the **Academic history** tab lists their records, ordered by study and course. The tab stays visible for **former students** (alumni and withdrawals): it is their permanent record.
- **Cohort queries:** **Planning and Grading → Grades → Academic history** lists every record. Filter or group by course, study, group or academic result — e.g. "all the students of study X in course Y", or every record with the **Title obtained** mark.

## Adjusting the academic result

The **academic result** (*Fully passed*, *Partially passed*, *Repeating*, *Withdrawn*) is proposed automatically from the grades and the destination enrollment, but it is a plain field: secretariat and administrators can **adjust it by hand** on the record when the automatic proposal does not match reality (e.g. a study without enrollment flow resolved in September).

## Finals pending the work placement

Subjects passed whose final grade is waiting for the work placement (EM) show the **Final pending** mark. The **Finals pending placement** filter of the history list gives the work list of placements still to grade: when the placement is evaluated, the final grade of those archived subjects is completed with the frozen weights.

---

[← Back to main index](index.md)
