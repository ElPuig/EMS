# Changes

## Guard board proposals only when they improve the day (#711):

- The arrangement planner used to keep every plan no worse than doing nothing (same lessons lost,
  same hours needing a guard, same notices). So it offered moving a lesson into the gap when that
  only moved the gap to another hour where a guard was still needed, or only turned a late entry
  into an early leave. Now a plan must be strictly better than leaving the day as it is in lessons
  lost, hours without class, guards or notices to the families (`ArrangementPlanner.plans()`).
- Tests adapted to the new rule, and a new one with a gap in the middle of the day: moving the
  first or the last lesson into it (the group comes in later or leaves earlier) is offered, moving
  another middle lesson into it is not, however many plans are asked for.
- Developer doc and teachers' manual (ca/es/en) say so.
