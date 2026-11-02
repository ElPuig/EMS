[Català](../../ca/teachers/guard-duty-schedule.md) | [Castellano](../../es/teachers/guard-duty-schedule.md) | [English](guard-duty-schedule.md)

---

# Guard Duty Schedule

See where every teacher is, and who is on guard duty, in each time block of the week — not just your own schedule.

**Required role:** Teacher (read-only; schedules are configured by a Department Chief or above from the corresponding teacher's own weekly schedule). Organising an absence from the Absences table is up to the absent teacher's Department or Seminar Chief and those above them (see [Organising an absence](#organising-an-absence)), who can also enter a detected absence for a teacher of their department; a teacher on guard duty can also take a class left without a teacher themselves (see [Covering a class yourself](#covering-a-class-yourself)). When the group's study has a department that manages it, that department's chiefs can organise it too.

---

## Access

Navigate to: **Employee Attendances → Guard schedule**

The board opens on today's own weekday and shift (morning before 15:00, afternoon from 15:00 on) — not always Monday morning — so you land straight on whatever's relevant right now.

---

## Choosing the Day and the Week

Click **Monday** to **Friday** at the top to switch days. Each tab also shows the day of the month it stands for in the week on screen.

Use the **‹** and **›** arrows to move to the previous or next week, or the date box next to them to jump to any date — the tabs move to that date's week and the board opens on its weekday.

Morning and afternoon are different shifts — use the dropdown to switch between them; only one is shown at a time.

---

## The Two Views

The two buttons on the right of the toolbar switch between the two ways of reading the same day and shift. The board opens on the **Absences table**:

- **Absences table** — one row per time block: who is missing and what has to be covered, against who is on guard duty to cover it.
- **Guard duty schedule** — the timetable, with everybody who is away marked on it.

When the board shows today, a **dotted red line** crosses both views at the current time, at its exact height within the time block it falls in (at 16:40, two thirds of the way down the 16:00-17:00 block), so you can see at a glance which classes are on now. It moves down as the time goes by, and is not drawn on another day or outside the shift on screen.

---

## Reading the Timetable

The table's columns are the groups with a class in that shift, grouped by **area** (for example ESO / BTX and VET): each area has its own time framework, and the table's header shows it with one band per area.

Since each area starts and ends its lessons at different times (ESO has its break at 10:00 and VET at 11:00, for example), the table's rows are the stretches between every start and end time of the shift, and each class spans the stretches it lasts: a class from 10:25 to 11:25 spans the 10:25-11:00 and 11:00-11:25 stretches. Both areas line up by clock without bending anybody's lessons, and a longer stretch is a taller row.

Each cell shows its own start and end time, the subject (as its short code, e.g. "MP 0440"), the teacher(s) — more than one if the class is co-taught — and the classroom for that group's class at that time. An empty cell simply means nothing is scheduled there for that group.

The **Guard duty** column on the right lists every teacher on guard duty, grouped by the time of their guard duty (also shown at the top of each block), each in a thin-bordered box. When two guard duties overlap in time (the ESO break guard and a 10:00-11:00 VET guard, for example), they sit side by side. A guard-duty teacher has no group of their own at that moment (that's the whole point of guard duty), so they only ever appear here, never in a group's column. A teacher on a **Guard (WC)** duty specifically shows a **"(WC)"** tag right after their name — worth calling out because, unlike a break-time guard (see below), a WC guard duty can fall at any time of day, so there's no other way to tell it apart from a plain guard duty at a glance.

The small number in a circle after each name is how many classes that teacher has been sent to cover this course (including covers already planned for a coming day). Several groups looked after together in the same room at the same time count as a single cover; groups in different rooms count separately. It helps share the covers out fairly.

Each group's break shows as a block of its own, with its time and a **"Break"** label, and a brown accent on its left edge, so it doesn't read as a gap in the schedule. Break-time guard duties in the Guard duty column carry the same accent.

![Guard duty schedule of two areas whose breaks fall at different times: each group's classes with their time, the break blocks with their brown accent, the plain, WC and break guards, and the absent teachers in red](../../assets/teachers/guard-duty-01-horari.png)

---

## Filtering by Area

Next to the shift dropdown there's an **area filter** button (it reads "All areas" until you check something). Click it to open a checklist of every area — for example ESO / BTX and VET — and check as many as you need. Leave everything unchecked to see every area at once.

Once one or more areas are checked:
- Only the groups of the checked area(s) become columns, including the reinforcement groups of their groups.
- The **Guard duty** column keeps listing every teacher on duty in a visible time block, regardless of what they otherwise teach — being on duty is what matters, not which area a guard happens to teach in that day. A guard duty on another area's break is left out.
- A guard duty on the checked area's own break gets its own "Break" row, even though no group has a class then.

A group's area is that of the study managing it (the **Managed by the department** field on the study's form, or the top-level department above it).

> The area filter replaced the level filter in version 18.0.0.38.0.

---

## Reading the Absences Table

The table uses the same stretches of time as the timetable, with one column per area:

- **One column per area** — one line per class left without a teacher in that area: who is away, and the group, subject and classroom that needs covering, in a block carrying the class's time. The area's break shows as a "Break" block.
- **Guard duty** — the teachers on guard duty, grouped by the time of their guard duty, the same ones the timetable shows.

In the **Guard duty** column, a guard teacher's box looks as usual while they are free to cover a class then; its tooltip reminds you that they are assigned from the line of an absence. It looks greyed out when they cannot cover anything: they are away, have not checked in yet (it also carries a clock icon), or are already with a group (their name is struck through and the tooltip says with which one). Whoever organises absences can also click a free guard's box to send them to support a teacher who is in class (see [Sending a guard as support](../department_chiefs/absences.md#sending-a-guard-as-support)).

So you can see at a glance which guard duties line up with each class to cover, even when the two areas run their lessons at different times. A stretch where nobody is missing has empty area columns.

In a co-taught class (two teachers in the same classroom) where only one of them is away, their line is **struck through**: it stays there so you know who is missing, but no guard is needed because the other teacher is taking the class. Hover over the line or click it to see why; the **ⓘ** icon on its left shows there is an explanation.

Every struck-through line has that icon, whatever the reason: a co-teacher is in the class, a guard teacher has already been sent to it (their name appears next to it), or the families were told the students can stay at home for it (see [Organising an absence](#organising-an-absence)). If both are away, or each teacher has half of the group in a different classroom, the line is not struck through and the class does need covering.

![Absences table of the same day: one column per area with the classes to cover, one already covered by a guard, and an absent teacher's break guard in the Guard duty column](../../assets/teachers/guard-duty-02-absencies.png)

---

## Absences

A teacher who is away is shown in red wherever their name appears — in their own cell on the timetable, and in the Guard duty column when they were the one on guard:

- **Bold red** — the absence is approved.
- **Lighter italic red** — the absence has been requested and is still awaiting approval.

Refused and cancelled requests are not shown.

An absence their chief or the Head of Studies already knows about, but the teacher has not requested yet (a *detected absence*, see below), is also shown as awaiting approval. So is a day already over on which the teacher did not check in, once EMS has detected it.

A teacher on an ordinary guard duty who is away is marked in the Guard duty column, and produces no line in the Absences column: they have no class of their own for anyone to cover. A guard duty that is a fixed post, like the WC or the break guard, is different: somebody has to be there, so when its teacher is away it gets its own line in the **Guard duty** column of the Absences table, under the guards of its own block, with the guard duty's name (for example **Guard (WC)**) where a class shows its group, to be covered like a class (see [Covering a WC or break guard](#covering-a-wc-or-break-guard)).

Only the fact that somebody is away is shown here. The type of absence, its reason and any supporting document are not.

---

## Teachers who have not checked in

Today, as soon as a class starts, if its teacher has not checked in it appears in the **Absences table** like an absence, so a guard teacher can cover it. Their name is shown in red with a dotted underline and the tag **Not checked in**. The same goes for a teacher on guard duty: they are marked in the Guard duty column and cannot be sent to cover anything until they check in.

- The class leaves the table as soon as the teacher checks in, and so do their next classes. The classes that ended before they checked in stay, so a guard already sent to them is still correct.
- An absence (approved, requested or detected) always takes precedence: the line then shows the absence.
- Such a class is only covered with a guard. The schedule does not propose telling the families or rearranging lessons, because the teacher may still be in the centre.
- Only today's classes count. On another day nobody is checked in or out yet.

![Absences table at 10:30: the 8-9 class, already over, and the 10-11 class of a teacher who has not checked in, both tagged Not checked in, with the guard on duty](../../assets/teachers/guard-duty-10-sense-fitxar.png)

### The teacher is in the classroom

Sometimes the teacher is in the classroom and has only forgotten to check in. If you are on guard duty at that time, or you organise that teacher's absences (their department or seminar chief, Head of Studies, Deputy Head of Studies, Direction or the administrator), you can say so:

1. In the **Absences table**, click the line of the class in progress (its tooltip says that the teacher **has not checked in yet. Click if they are in the classroom, or to cover the class.**).
2. Click **They are in the classroom**.

![Dialog of the class in progress: the teacher has not checked in yet, with the buttons They are in the classroom and Cover it myself](../../assets/teachers/guard-duty-11-es-a-l-aula.png)

The teacher's check-in is registered at the current time, the class leaves the table, and the teacher receives a message saying who registered it. On the check-in's own form, **Check-in registered by** shows your name. If the time is not right, the teacher can request a correction as with any other check-in.

The same dialog also offers what you could otherwise do with the line: **Cover it myself** if you are on guard duty (the class is covered in your name straight away, with no further confirmation, as with **They are in the classroom**), or **Send a guard teacher** if you organise the absence. A class that has already ended cannot be resolved this way: checking the teacher in now would not change it.

A guard teacher on duty who has not checked in is resolved the same way, from their box in the **Guard duty** column (its tooltip says **Not checked in: say they are in the centre**): another teacher on guard duty then, or whoever organises their absences, clicks it and then **They are in the centre**. Once checked in, they can be sent to cover a class.

### The schedule updates itself

While it is open, the schedule updates itself, without reloading the page, only when something it shows changes: when a lesson starts or ends, when somebody checks in, sends or releases a guard, or when an absence or a notice to the families changes. So you see at once what a colleague has just organised. If a dialog is open or the browser tab is in the background, it waits and updates as soon as you close it or come back.

---

## Covering a class yourself

If you are on guard duty in a time block, you don't have to wait for somebody to send you: you can take a class that is still left without a teacher yourself.

1. In the **Absences table**, click the line of the class (lines you can take show a hand pointer and the tooltip **Click to cover this class yourself**).
2. Click **Cover it** to confirm.

The class is then struck through with your name next to it, the same as when you are sent to it. Nobody receives a message: the board itself shows who covers what. If your guard duty only coincides with part of the class, you take that part (the dialog tells you which), and someone else can cover the rest. Only a class, or your part of it, with no guard yet can be taken, and only in a time block you are on an ordinary guard duty (not a WC or break guard, and not while you are away yourself). The same goes for the line of a WC or break guard who is away: you can take it yourself the same way.

Lines you cannot take because you are not on guard duty at that time show the hand pointer too, with the tooltip **You cannot cover this teacher: you are not on guard duty at this time** (and the same when you click them), so you know why you cannot take them.

If you change your mind, click the line again and then **Stop covering this class**: the class is left without a guard again. You can only do this with a class you took yourself; if somebody sent you to it, ask them to change it. Whoever organises the absence can still change or remove a guard who took a class on their own.

## Organising an absence

Sending guards to the classes of an absent teacher, rearranging the lessons, telling the families about a timetable change and entering a detected absence are up to the teacher's Department or Seminar Chief and those above them. Everything they can do from the Absences table is explained in [Organising Absences](../department_chiefs/absences.md).

---

## Coming Back to Where You Were

The board's address keeps the week, day, shift, view and areas you are looking at. Going back to it from a notice - with the breadcrumbs or the browser's back button - or reloading the page returns you to the same place, and you can copy the address to send a colleague straight there. Opening it from the menu always starts at today's day and shift.

---

## Exporting to PDF

Click **PDF** in the toolbar to download the day and shift currently shown (not the whole week) as a printable document — whatever area filter is currently checked is applied to the PDF too, which uses the same stretches of time and the same columns as the screen. The PDF prints whichever of the two views is on screen: the timetable if **Guard duty schedule** is active, or the Absences table if **Absences table** is active, with its guards, colours and struck-through lines as on screen.

---

[← Back to main index](index.md)
