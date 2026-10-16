[Català](../../ca/teachers/guard-duty-schedule.md) | [Castellano](../../es/teachers/guard-duty-schedule.md) | [English](guard-duty-schedule.md)

---

# Guard Duty Schedule

See where every teacher is, and who is on guard duty, in each time block of the week — not just your own schedule.

**Required role:** Teacher (read-only; schedules are configured by a Department Chief or above from the corresponding teacher's own weekly schedule). Organising an absence from the Absences table is up to the absent teacher's Department or Seminar Chief and those above them (see [Organising an absence](#organising-an-absence)), who can also enter an expected absence for a teacher of their department (see [Entering an expected absence](#entering-an-expected-absence)); a teacher on guard duty can also take a class left without a teacher themselves (see [Covering a class yourself](#covering-a-class-yourself)). When the group's study has a department that manages it, that department's chiefs can organise it too.

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

An absence their chief or the Head of Studies already knows about, but the teacher has not requested yet (an *expected absence*, see below), is also shown as awaiting approval.

A teacher on an ordinary guard duty who is away is marked in the Guard duty column, and produces no line in the Absences column: they have no class of their own for anyone to cover. A guard duty that is a fixed post, like the WC or the break guard, is different: somebody has to be there, so when its teacher is away it gets its own line in the **Guard duty** column of the Absences table, under the guards of its own block, with the guard duty's name (for example **Guard (WC)**) where a class shows its group, to be covered like a class (see [Covering a WC or break guard](#covering-a-wc-or-break-guard)).

Only the fact that somebody is away is shown here. The type of absence, its reason and any supporting document are not.

---

## Covering a class yourself

If you are on guard duty in a time block, you don't have to wait for somebody to send you: you can take a class that is still left without a teacher yourself.

1. In the **Absences table**, click the line of the class (lines you can take show a hand pointer and the tooltip **Click to cover this class yourself**).
2. Click **Cover it** to confirm.

The class is then struck through with your name next to it, the same as when you are sent to it. Nobody receives a message: the board itself shows who covers what. If your guard duty only coincides with part of the class, you take that part (the dialog tells you which), and someone else can cover the rest. Only a class, or your part of it, with no guard yet can be taken, and only in a time block you are on an ordinary guard duty (not a WC or break guard, and not while you are away yourself). The same goes for the line of a WC or break guard who is away: you can take it yourself the same way.

If you change your mind, click the line again and then **Stop covering this class**: the class is left without a guard again. You can only do this with a class you took yourself; if somebody sent you to it, ask them to change it. Whoever organises the absence can still change or remove a guard who took a class on their own.

## Entering an expected absence

Who can do this: **Seminar Chiefs** and **Department Chiefs**, for the teachers of their own department, as well as the Head of Studies or Deputy, Direction and the administrator. They can also do it for a teacher of another department who teaches a group their department manages, or who names their department in the **Also managed by the departments** field (see [Organising an absence](#organising-an-absence)).

The normal way is always that the teacher requests the absence themselves. Use this only for the exceptional case of a teacher who phones or writes to warn they will be away and cannot use EMS: entering it puts their classes on the schedule straight away, so you can organise the cover.

1. Go to **Employee Attendances > Absences > Management > Expected absences** and click **New**.
2. Choose the **Teacher**. Only the teachers of your own department are offered.
3. Set **From** and **To**, date and time. They start out as today, 08:00 to 15:00. An absence can span several days.
4. Optionally, add **Notes** for your own reference. The teacher never sees this entry.
5. Save.

The absence then appears on the schedule as awaiting approval (lighter italic red), and you can organise it as described below. When the teacher requests the absence themselves, the expected absence is linked to it automatically and whatever you organised stays as it is. If the teacher turns out not to be absent after all, delete the entry.

---

## Organising an absence

Who can do this: the absent teacher's **Seminar Chief** or **Department Chief**, and those above them in the hierarchy (Head of Studies or Deputy, and Direction), as well as the administrator. What counts is the department the teacher teaches in: its chiefs and the manager of the area it belongs to organise the absences of everyone in it, members of the management team (such as the Secretary) included. Everybody else sees the result but cannot change it, and the absent teacher cannot organise their own absence. It makes no difference whether the absence was requested by the teacher or entered by their chief or the Head of Studies as an expected absence: both are handled the same way. When the teacher later requests an absence that was expected, whatever was already organised stays as it is, and only the extra days or hours of the request appear as new lines to decide on. **Teachers shared between departments:** besides whoever answers for the teacher, a class can also be organised by whoever answers for the students who lose it: when the group's study names a department that manages it (the **Managed by the department** field on the study's form), that department's Department Chief and Seminar Chief, and those above them, can organise the classes of its groups, whatever department the teacher belongs to. For example, if a teacher of the Foreign Languages department misses a lesson with a Computer Science group, the Computer Science chiefs can assign the guard; if she misses a lesson with an Administration group, the Administration chiefs can; and in both cases so can her own Department Chief. A reinforcement group follows the studies of its main groups. For a teacher who in practice works for another department or area than their own, their form lets you say so in the **Also managed by the departments** field (below **Manager**): the chiefs of those departments, and those above them, can organise everything of theirs, fixed guard duties included (toilets, break), which have no students.

> The **Managed by the department** and **Also managed by the departments** fields were introduced in version 18.0.0.36.2. Nobody who could already organise an absence has lost that.

Everything is done from the **Absences table**, and nothing happens on its own: each step waits for you to press its button. A day that is already over can no longer be changed.

![Absences table as a Department Chief: the proposals for a group, ending with only telling the families, and two classes covered by two guards, each in its own colour](../../assets/teachers/guard-duty-03-organitzar.png)

### Sending a guard to a class

1. Click the line of the class to cover (lines you can organise show a hand pointer).
2. If the dialog offers possible arrangements (see [Rearranging the lessons instead of sending a guard](#rearranging-the-lessons-instead-of-sending-a-guard)), choose **Send a guard teacher**. Then choose the **Guard teacher**. Only the teachers on an ordinary guard duty during the class are offered (never those on a WC or break guard, who are needed at their post), except those who are away themselves. Those who can cover the whole class come first, then those who can only cover part of it, with the part they would cover (see [Covering a class between several guards](#covering-a-class-between-several-guards)). Next to each name you see how many classes they have covered this course, so you can choose whoever has covered the fewest.
3. Optionally, write a **message**: what the students have to work on, where the materials are...
4. Click **Assign and notify**.

![Sending a guard teacher to a class: the guards on duty and a message for them](../../assets/teachers/guard-duty-04-enviar-guardia.png)

The guard teacher receives an Odoo message (in their inbox, or by email, depending on their own notification preference) with the date, time, group, subject, classroom, the absent teacher and your message. If they reply to that email, the answer reaches you.

The class is then struck through, the guard's name appears next to it, and the line and the guard's box in the Guard duty column share the same colour. The colour belongs to the class covered: when several guards cover different classes at the same time, each class has its own colour, so you can see at a glance who is covering what. A guard can cover more than one class: all of them take the same colour.

To change the guard, click the line and then **Change or remove the guard** (only shown to whoever organises the absence), and choose another one: the previous guard is told they are no longer needed. To write a new message to the same guard, choose them again and click **Assign and notify**. To take a guard off the class, click **Remove assignment** next to their name, at the top of the dialog: they are told so.

### Covering a class between several guards

When the areas run different timetables, no guard may coincide with a whole class. For example, an ESO class from 10:25 to 11:25 and two VET guards, one from 10:00 to 11:00 and the other from 11:00 to 12:00. The dialog then also offers those who coincide with part of the class, with the part they would cover (*"… - 10:25-11:00, part of the class"*), and each guard covers exactly that part.

While a part is still missing, the line is not struck through: it shows the guard with their part and a dashed red tag with what is missing (*"Missing 11:00-11:25"*), so you can send someone else. Once together they cover the whole class, the line is struck through.

Every guard covering the same class shares its colour. A dotted border (on the line, the tag and the guard's box) means a partial cover; a solid one, a class covered in full.

![A class covered in part: the guard with their part and the part still missing, with dotted borders](../../assets/teachers/guard-duty-08-cobertura-parcial.png)

### Covering a WC or break guard

When the teacher of a WC or break guard is away, their guard duty appears as a line in the **Guard duty** column of the Absences table, under the guards of its own block, with the guard duty's name instead of a group. It is covered exactly like a class: click it, choose one of the teachers on an ordinary guard duty in that time block, and click **Assign and notify**. The message they receive says it is a guard duty to cover. If the absence is cancelled afterwards, the guard is offered for release like any other.

### Rearranging the lessons instead of sending a guard

Often no guard is needed, because the teachers can rearrange their lessons that day. The board works this out for every class still left without anybody and proposes it in the **Proposals for the absences** box, above the table (only visible to whoever can organise the absence); those lines also show a tag such as **3 possible arrangements**.

The box has one section per group, headed with its name. Groups that share a lesson that day (two groups taught together) share their section, because rearranging a shared lesson changes all their days. In each section come first what is waiting (an arrangement waiting for its notice, a notice to correct), then the proposals, numbered from the best one, and last **Only tell the families** (see [Late entry, early leave or no classes](#late-entry-early-leave-or-no-classes)).

![Proposals for the absences box: the section of two groups, with three numbered proposals, each a list of steps with its checkbox and, in orange, the entry and exit times they change, and last the option of only telling the families](../../assets/teachers/guard-duty-06-reorganitzacions.png)

Each proposal is a list of steps, one per line, always between teachers of those groups and within the same day:

- **Moved lesson**: a teacher who is free at that time teaches then one of their lessons with the group from another time. The lesson they leave becomes a gap, which another step can fill in turn: one teacher brings a lesson forward, another fills the gap it leaves, and so on, until what is left free is at the start or the end of the day (or next to a break).
- **Swap**: another teacher of the group teaches then, and the absent teacher, who is in at another time, teaches that teacher's lesson with the group.
- **Notice to the families**: the group comes in later, leaves earlier or has a longer break, for the lessons left free at the start or the end of the day.

A lesson shared by several groups is moved for all of them, as long as all of them have the same gap, and the notice then goes to each group.

Proposals come in this order: first those where the students lose fewer lessons; among those, the ones where they spend fewer hours in the centre without class (with a guard or in a longer break); then those that need fewer notices and fewer teachers moving lessons, that keep two hours of the same subject together, and that change fewer entry or exit times. Up to three proposals per group are shown.

**Nobody's working day gets longer.** A proposal only includes a step if no teacher involved ends up with a longer day (counted from their first period to their last, lessons, guard duties and any other duty alike): whoever would come in earlier must leave earlier, and whoever would leave later must come in later. When a step changes somebody's entry or exit time, an orange line under it says exactly whose and how (*"… leaves at 20:20 instead of 21:20"*).

**Applying a proposal.** Click **Apply the checked steps** on its right, or click the class and choose the proposal in the dialog, where the proposals that solve that class come first, above sending a guard. Every step starts checked: uncheck those you do not want. A step that needs another one is unchecked along with it (a move into the gap another one leaves, a notice that only makes sense because of a move), and checking a step checks what it needs.

![Dialog of a class: the proposals that solve it, the first one chosen with its steps checked, above sending a guard and the arrangement described by hand](../../assets/teachers/guard-duty-07-aplicar-reorganitzacio.png)

- A **swap**, and a **moved lesson** that does not depend on a notice, take effect at once: the class is struck out with the teacher who is with the group, and the teachers involved receive an Odoo message with the change (and their new entry or exit time, if it changes).
- A **notice** opens its draft for the families straight away (one per group). **The moves it frees the group from only count once it is sent**: until then those classes are not struck out, and the section shows them as waiting for their notice (**Open draft**). The teachers are told when the notice is sent. If you delete the draft, those moves are discarded. Once it is sent, the class shows both tags: who is with the group and, in green, what the families were told (*"Leaves at 12:25"*).
- **If you leave the notice out**, the moves are applied without it, and the lesson a move leaves free appears as one more line of the table, with the tag **Lesson moved to 15:00**: cover it like any other (with a guard, another arrangement or one described by hand), or send the notice later from **Only tell the families**. Whoever organises the original absence organises it too.

Once an arrangement is in effect, the **Guard duty schedule** shows who really teaches each lesson involved, and a teacher who was on guard duty at a time they now teach is struck out of the **Guard duty** column there: they cannot be sent to cover anything else then, and nobody can take that class on their own.

**Other arrangement (described by hand)**, the last option of the dialog, is for whatever the board cannot work out, so that it is on record: two groups joined for the same subject, a teacher of another group... Describe it and, if a teacher is involved, choose them (they receive a message). No guard is then needed for that class.

To change your mind, click the line and then **Change or remove the arrangement**: **Remove arrangement** takes it back (the teachers are told), and choosing a guard or another arrangement replaces it. A lesson moved for several groups is taken back from all of them.

### Late entry, early leave or no classes

When the lessons without a teacher are the first ones of the group's day (one, two or more in a row), the students could come in later; when they are the last ones, they could leave earlier; when every lesson of the day is without a teacher, the group could have no classes. A lesson where somebody is with the students (a co-teacher who is not away, the other half of a split group, an optional subject or a guard already sent) breaks the run.

Those lines show a dashed tag such as **Could start at 10:00**, and the group's section of the **Proposals for the absences** box, above the table (only visible to whoever can organise the absence), offers that change as its last proposal, **Only tell the families**. Sending the notice strikes those lessons off the table, so no guard teacher has to cover them.

The selector next to each proposal lets you tell the families about less than the absences allow: with two lessons without a teacher, you can choose **Starts at 09:00** instead of **Starts at 10:00**. Only the first lesson is then struck out; the second still needs a guard, sent as usual. Choosing the smaller change is your decision: nothing will ask you to correct it.

On the current day, the board only proposes changes still to come: from 09:00 on, it no longer offers **Starts at 09:00** (the families would find out too late), and a proposal or a correction whose time has passed disappears. If the board has been open for a while, reload it to see the current proposals.

**Propose notice** opens a draft notice addressed to that group's students and families, with a suggested text you can change. Send it from that form as any other notice (the groups of a timetable change notice cannot be changed). If you leave it as a draft, the button reads **Open draft** next time.

![Draft notice proposed by the board, with the timetable change and the suggested text](../../assets/teachers/guard-duty-05-comunicat.png)

Once the notice is sent (or scheduled), those lines are struck through with a tag such as **Starts at 10:00**: nobody needs to be sent to them.

### A longer break

When the empty lessons are right before and/or right after a break of the group's level, with class further out on that side, the students could have a longer break instead. With the break at 18:00-18:20 and the 17:00 lesson empty, for example, the break could start at 17:00; with the 18:20 lesson empty, it could end at 19:20. The selector offers every combination (earlier, later, or both, hour by hour), and the notice reads *"…el grup X allargarà el pati de 17:00 a 19:20 el dia …"*. Sending it strikes those lessons off, like any other change.

This is never confused with coming in or leaving: if the empty lessons reach the start of the day, it is a late entry (e.g. coming in after the break, at 18:20); if they reach the end, an early leave (e.g. going home at the break, at 18:00).

### When the absence changes afterwards

If an absence is refused, cancelled or shortened, or a co-teacher turns out to be in, what was organised may no longer be needed. Nothing is undone automatically: the boxes above the table tell you, and you decide.

- **A guard who is no longer needed** (box **Guards no longer needed**): click **Release guard**. They are told they no longer need to cover the class.
- **An arrangement that no longer applies** (same box): the class no longer needs covering, or one of the teachers it relies on is now away at that time. Click **Remove arrangement**; the teachers are told.
- **A notice that no longer matches** (more was told than the absences now allow): a notice already sent cannot be taken back, so the proposals box offers **Propose correction**, a new draft notice for the same group with the corrected situation (a different time, or back to the usual timetable).

---

## Coming Back to Where You Were

The board's address keeps the week, day, shift, view and areas you are looking at. Going back to it from a notice - with the breadcrumbs or the browser's back button - or reloading the page returns you to the same place, and you can copy the address to send a colleague straight there. Opening it from the menu always starts at today's day and shift.

---

## Exporting to PDF

Click **PDF** in the toolbar to download the day and shift currently shown (not the whole week) as a printable document — whatever area filter is currently checked is applied to the PDF too, which uses the same stretches of time and the same columns as the screen. The PDF prints whichever of the two views is on screen: the timetable if **Guard duty schedule** is active, or the Absences table if **Absences table** is active, with its guards, colours and struck-through lines as on screen.

---

[← Back to main index](index.md)
